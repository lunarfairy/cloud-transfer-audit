"""Prototype fault-tolerant, address-agnostic grader for the transfer task (held-out providers: Azure, Google Cloud).
Each top-level block is parsed independently, so a syntax error costs only the requirements that depend on that block.
Requirements R01-R13 mirror the reference-architecture conformance suites (ra/*/tests/conformance.tftest.hcl) but are
evaluated on functional properties located by resource type and followed through references, not on resource names.
Usage: python code/grader.py <dir-with-.tf-files> <azure|gcp>  -> JSON {requirement: 0/1, score, parse_errors}"""
import json, os, re, sys

HDR = re.compile(r'^\s*(resource|data|provider|variable|locals|output|terraform|module)\b(?:\s+"([\w-]+)")?(?:\s+"([\w-]+)")?\s*\{\s*$')

def split_blocks(text):
    """Yield (kind, type, name, body_lines, ok). Recovers at the next top-level header after an unbalanced block."""
    lines = text.splitlines()
    i, out = 0, []
    while i < len(lines):
        m = HDR.match(lines[i])
        if not m:
            i += 1; continue
        depth, j, body, ok = 1, i + 1, [], False
        while j < len(lines):
            if HDR.match(lines[j]) and depth > 0 and not lines[j].startswith((" ", "\t")):
                break  # next top-level header before this block closed: block is malformed
            s = re.sub(r'"(?:\\.|[^"\\])*"', '""', lines[j])
            depth += s.count("{") - s.count("}")
            if depth <= 0:
                ok = True; j += 1; break
            body.append(lines[j]); j += 1
        out.append((m[1], m[2] or "", m[3] or m[2] or "", body, ok))
        i = j
    return out

def parse_body(lines):
    """Tiny HCL subset parser: attributes (raw RHS text, multi-line lists/maps joined) and nested blocks (lists of dicts)."""
    root = {}; stack = [root]; buf = None
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        if buf is not None:
            buf[1].append(s)
            joined = " ".join(buf[1]); t = re.sub(r'"(?:\\.|[^"\\])*"', '""', joined)
            if t.count("[") - t.count("]") <= 0 and t.count("{") - t.count("}") <= 0:
                stack[-1][buf[0]] = joined; buf = None
            continue
        m = re.match(r'^([\w-]+)\s*\{\s*\}$', s)
        if m:
            stack[-1].setdefault(m[1], []).append({}); continue
        m = re.match(r'^([\w-]+)\s*\{$', s)
        if m:
            d = {}; stack[-1].setdefault(m[1], []).append(d); stack.append(d); continue
        m = re.match(r'^([\w-]+)\s*=\s*(.*)$', s)
        if m:
            v = m[2]; t = re.sub(r'"(?:\\.|[^"\\])*"', '""', v)
            if t.count("[") - t.count("]") > 0 or t.count("{") - t.count("}") > 0:
                buf = (m[1], [v])
            else:
                stack[-1][m[1]] = v
            continue
        if s == "}":
            if len(stack) > 1: stack.pop()
    return root

def load(dirpath):
    res, errors, text = {}, [], ""
    for f in sorted(os.listdir(dirpath)):
        if f.endswith(".tf"):
            text += open(os.path.join(dirpath, f), encoding="utf-8").read() + "\n"
    for kind, rtype, name, body, ok in split_blocks(text):
        if not ok:
            errors.append(f"{kind} {rtype}.{name}: unbalanced block skipped"); continue
        if kind in ("resource", "data"):
            b = parse_body(body)
            if strv(b.get("count")) == "0":
                continue  # resource disabled
            res[(rtype, name)] = b
        elif kind == "locals":
            res[("locals", f"locals{len(res)}")] = parse_body(body)
    return res, errors

def strv(v):
    if v is None: return None
    m = re.match(r'^"(.*)"$', v.strip())
    return m[1] if m else v.strip()

def num(v):
    try: return float(strv(v))
    except Exception: return None

def lst(v):
    if v is None: return []
    return re.findall(r'"((?:\\.|[^"\\])*)"', v)

def refs(v, rtype=None):
    if v is None: return []
    pat = r'\b((?:google|azurerm)_[a-z0-9_]+)\.([\w-]+)'
    return [(t, n) for t, n in re.findall(pat, v) if rtype is None or t == rtype]

def of(res, rtype):
    return [(n, b) for (t, n), b in res.items() if t == rtype]

def blk(b, *path):
    cur = [b]
    for p in path:
        nxt = []
        for c in cur:
            nxt += c.get(p, []) if isinstance(c.get(p), list) else []
        cur = nxt
    return cur

def any_(xs): return any(bool(x) for x in xs)

# ---------------- Google Cloud ----------------
def gcp_checks(R):
    c = {}
    nets = [n for n, b in of(R, "google_compute_network") if strv(b.get("auto_create_subnetworks")) == "false"]
    subs = [(n, b) for n, b in of(R, "google_compute_subnetwork") if any(t == "google_compute_network" and m in nets for t, m in refs(b.get("network")))]
    c["R01"] = bool(nets and subs)
    migs = of(R, "google_compute_region_instance_group_manager")
    sqls = of(R, "google_sql_database_instance")
    c["R02"] = bool(migs) and any_(len(lst(b.get("distribution_policy_zones"))) != 1 for n, b in migs) and \
        any_(strv(s.get("availability_type")) == "REGIONAL" for n, b in sqls for s in blk(b, "settings"))
    fr = of(R, "google_compute_global_forwarding_rule") + of(R, "google_compute_forwarding_rule")
    def has80(pr):
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", (pr or "").strip())
        return bool(m) and int(m[1]) <= 80 <= int(m[2] or m[1])
    c["R03"] = any_(has80(strv(b.get("port_range"))) and (strv(b.get("load_balancing_scheme")) or "EXTERNAL").startswith("EXTERNAL") for n, b in fr)
    tmpls = of(R, "google_compute_instance_template") + of(R, "google_compute_region_instance_template")
    nat = of(R, "google_compute_router_nat")
    app_subs = set(m for n, b in tmpls for ni in blk(b, "network_interface") for t, m in refs(ni.get("subnetwork"), "google_compute_subnetwork"))
    def nat_covers(b):
        mode = strv(b.get("source_subnetwork_ip_ranges_to_nat")) or ""
        if mode.startswith("ALL_SUBNETWORKS"): return True
        return bool(app_subs & set(m for s in blk(b, "subnetwork") for t, m in refs(s.get("name"), "google_compute_subnetwork")))
    c["R04"] = any_(nat_covers(b) and refs(b.get("router"), "google_compute_router") for n, b in nat) and bool(tmpls) and \
        all(len(blk(b, "network_interface", "access_config")) == 0 for n, b in tmpls)
    tags = set(t for n, b in tmpls for t in lst(b.get("tags")))
    lbsrc = {"35.191.0.0/16", "130.211.0.0/22"}
    def allows80(b): return any("80" in lst(a.get("ports")) and strv(a.get("protocol")) == "tcp" for a in blk(b, "allow"))
    fws = of(R, "google_compute_firewall")
    ok_lb = any_(allows80(b) and set(lst(b.get("source_ranges"))) <= lbsrc and set(lst(b.get("source_ranges"))) and
                 (not lst(b.get("target_tags")) or set(lst(b.get("target_tags"))) & tags) for n, b in fws)
    open_world = any_("0.0.0.0/0" in lst(b.get("source_ranges")) and (strv(b.get("direction")) or "INGRESS") == "INGRESS" for n, b in fws)
    c["R05"] = ok_lb and not open_world
    sas = of(R, "google_service_account")
    tsa = [r for n, b in tmpls for s in blk(b, "service_account") for r in refs(s.get("email"), "google_service_account")]
    iam = of(R, "google_storage_bucket_iam_member") + of(R, "google_storage_bucket_iam_binding")
    good_roles = {"roles/storage.objectUser", "roles/storage.objectAdmin", "roles/storage.objectViewer", "roles/storage.objectCreator"}
    c["R06"] = bool(sas and tsa) and any_(strv(b.get("role")) in good_roles and
                                          any(r in tsa for r in refs((b.get("member") or "") + " " + (b.get("members") or ""), "google_service_account")) for n, b in iam)
    buckets = of(R, "google_storage_bucket")
    public_iam = any_("allUsers" in ((b.get("member") or "") + (b.get("members") or "")) for n, b in iam)
    c["R07"] = bool(buckets) and all(strv(b.get("public_access_prevention")) == "enforced" for n, b in buckets) and not public_iam
    def startup(b):
        txt = (b.get("metadata_startup_script") or "") + " " + (b.get("metadata") or "")
        return txt
    loc = " ".join(str(v) for (t, n), b in R.items() for v in b.values() if isinstance(v, str))
    c["R08"] = any_(re.search(r"health", startup(b) + (loc if "local." in startup(b) else "")) and
                    re.search(r"apache2|nginx|httpd|python3? -m http", startup(b) + (loc if "local." in startup(b) else "")) for n, b in tmpls)
    asc = of(R, "google_compute_region_autoscaler") + of(R, "google_compute_autoscaler")
    def asc_ok(b):
        for p in blk(b, "autoscaling_policy"):
            mn, mx = num(p.get("min_replicas")), num(p.get("max_replicas"))
            tg = [num(u.get("target")) for u in p.get("cpu_utilization", [])]
            if mn and mx and mn >= 2 and mx >= mn and tg and tg[0] is not None and 0 < tg[0] <= 1:
                return True
        return False
    c["R09"] = any_(asc_ok(b) and refs(b.get("target")) for n, b in asc)
    hcs = [n for n, b in of(R, "google_compute_health_check") if any_(strv(h.get("request_path")) == "/health" for h in blk(b, "http_health_check"))]
    bes = [(n, b) for n, b in of(R, "google_compute_backend_service") if any(t == "google_compute_health_check" and m in hcs for t, m in refs(b.get("health_checks")))
           and any(refs(g.get("group")) for g in blk(b, "backend"))]
    um = [n for n, b in of(R, "google_compute_url_map") if any(t == "google_compute_backend_service" and m in [x for x, _ in bes] for t, m in refs(b.get("default_service")))]
    px = [n for n, b in of(R, "google_compute_target_http_proxy") + of(R, "google_compute_target_https_proxy") if any(m in um for t, m in refs(b.get("url_map")))]
    c["R10"] = any_(any(m in px for t, m in refs(b.get("target"))) for n, b in fr)
    def sql_ok(b):
        if not (strv(b.get("database_version")) or "").startswith("MYSQL_8"): return False
        for s in blk(b, "settings"):
            ip = blk(s, "ip_configuration"); bk = blk(s, "backup_configuration")
            if ip and strv(ip[0].get("ipv4_enabled")) == "false" and ip[0].get("private_network") and bk and strv(bk[0].get("enabled")) == "true":
                return True
        return False
    c["R11"] = any_(sql_ok(b) for n, b in sqls)
    c["R12"] = any_(strv(b.get("enable_cdn")) == "true" for n, b in of(R, "google_compute_backend_service")) or any_(strv(b.get("enable_cdn")) == "true" for n, b in of(R, "google_compute_backend_bucket"))
    def alert_ok(b):
        for cd in blk(b, "conditions"):
            for ct in blk(cd, "condition_threshold"):
                th = num(ct.get("threshold_value"))
                f = ct.get("filter") or ""
                if "cpu/utilization" in f and "instance_group" in f and th is not None and 0 < th <= 1 and strv(ct.get("comparison")) == "COMPARISON_GT":
                    return True
        return False
    c["R13"] = any_(alert_ok(b) for n, b in of(R, "google_monitoring_alert_policy"))
    return c

# ---------------- Azure ----------------
def az_checks(R):
    c = {}
    vnets = of(R, "azurerm_virtual_network"); subs = of(R, "azurerm_subnet")
    c["R01"] = bool(vnets) and len(subs) >= 3
    vmss = of(R, "azurerm_linux_virtual_machine_scale_set")
    agw = of(R, "azurerm_application_gateway"); my = of(R, "azurerm_mysql_flexible_server")
    c["R02"] = any_(len(lst(b.get("zones"))) >= 2 for n, b in vmss) and \
        any_(strv(h.get("mode")) == "ZoneRedundant" for n, b in my for h in blk(b, "high_availability"))
    pips = [n for n, b in of(R, "azurerm_public_ip")]
    nat_ips = set(m for n, b in of(R, "azurerm_nat_gateway_public_ip_association") for t, m in refs(b.get("public_ip_address_id"), "azurerm_public_ip"))
    c["R03"] = any_(any(m in pips and m not in nat_ips for t, m in refs(f.get("public_ip_address_id"), "azurerm_public_ip")) for n, b in agw for f in blk(b, "frontend_ip_configuration"))
    app_sub = set(m for n, b in vmss for ni in blk(b, "network_interface") for ip in blk(ni, "ip_configuration") for t, m in refs(ip.get("subnet_id"), "azurerm_subnet"))
    nat_assoc = of(R, "azurerm_subnet_nat_gateway_association")
    c["R04"] = any_(set(m for t, m in refs(b.get("subnet_id"), "azurerm_subnet")) & app_sub for n, b in nat_assoc) and \
        all(strv(b.get("default_outbound_access_enabled")) == "false" for n, b in subs if n in app_sub)
    rules = of(R, "azurerm_network_security_rule")
    assoc = of(R, "azurerm_subnet_network_security_group_association")
    nsg_of_sub = {}
    for n, b in assoc:
        for t, m in refs(b.get("subnet_id"), "azurerm_subnet"):
            nsg_of_sub[m] = set(x for _, x in refs(b.get("network_security_group_id"), "azurerm_network_security_group"))
    def sub_prefix(m):
        b = R.get(("azurerm_subnet", m), {}); p = lst(b.get("address_prefixes")); return p[0] if p else None
    db_sub = set(m for n, b in my for t, m in refs(b.get("delegated_subnet_id"), "azurerm_subnet"))
    gw_sub = set(m for n, b in agw for g in blk(b, "gateway_ip_configuration") for t, m in refs(g.get("subnet_id"), "azurerm_subnet"))
    def tier_ok(sub_set, port, src_subs):
        for s in sub_set:
            nsgs = nsg_of_sub.get(s, set())
            rs = [b for n, b in rules if set(x for _, x in refs(b.get("network_security_group_name"), "azurerm_network_security_group")) & nsgs]
            srcp = {sub_prefix(x) for x in src_subs}
            allow = [num(b.get("priority")) for b in rs if strv(b.get("access")) == "Allow" and strv(b.get("direction")) == "Inbound"
                     and strv(b.get("destination_port_range")) == port and strv(b.get("source_address_prefix")) in srcp]
            deny = [num(b.get("priority")) for b in rs if strv(b.get("access")) == "Deny" and strv(b.get("direction")) == "Inbound"
                    and strv(b.get("source_address_prefix")) in ("VirtualNetwork", "*", "0.0.0.0/0")]
            if not (allow and deny and min(allow) < min(deny)): return False
        return bool(sub_set)
    c["R05"] = tier_ok(app_sub, "80", gw_sub) and tier_ok(db_sub, "3306", app_sub)
    uai = [n for n, b in of(R, "azurerm_user_assigned_identity")]
    vm_ids = set(m for n, b in vmss for i in blk(b, "identity") for t, m in refs(i.get("identity_ids"), "azurerm_user_assigned_identity"))
    cont = [n for n, b in of(R, "azurerm_storage_container")]
    good = {"Storage Blob Data Contributor", "Storage Blob Data Reader"}
    c["R06"] = any_(strv(b.get("role_definition_name")) in good and set(m for t, m in refs(b.get("principal_id"), "azurerm_user_assigned_identity")) & vm_ids
                    and refs(b.get("scope"), "azurerm_storage_container") for n, b in of(R, "azurerm_role_assignment"))
    sa = of(R, "azurerm_storage_account")
    c["R07"] = bool(sa) and all(strv(b.get("allow_nested_items_to_be_public")) == "false" for n, b in sa) and \
        all(strv(b.get("container_access_type")) in (None, "private") for n, b in of(R, "azurerm_storage_container")) and bool(cont)
    loc = " ".join(str(v) for (t, n), b in R.items() for v in b.values() if isinstance(v, str))
    def cd(b):
        x = (b.get("custom_data") or "") + " " + (b.get("user_data") or "")
        return x + (" " + loc if "local." in x else "")
    c["R08"] = any_(re.search(r"health", cd(b)) and re.search(r"apache2|nginx|httpd|python3? -m http", cd(b)) for n, b in vmss)
    def as_ok(b):
        if not any(t == "azurerm_linux_virtual_machine_scale_set" for t, m in refs(b.get("target_resource_id"))): return False
        for p in blk(b, "profile"):
            cap = blk(p, "capacity")
            if not cap or (num(cap[0].get("minimum")) or 0) < 2: return False
            for r in blk(p, "rule"):
                for mt in blk(r, "metric_trigger"):
                    th = num(mt.get("threshold"))
                    if strv(mt.get("metric_name")) == "Percentage CPU" and th is not None and 1 < th <= 100 and \
                            any(strv(sa_.get("direction")) == "Increase" for sa_ in blk(r, "scale_action")):
                        return True
        return False
    c["R09"] = any_(as_ok(b) for n, b in of(R, "azurerm_monitor_autoscale_setting"))
    def agw_ok(b):
        pr = [p for p in blk(b, "probe") if strv(p.get("path")) == "/health"]
        st = [s for s in blk(b, "backend_http_settings") if strv(s.get("probe_name")) in {strv(p.get("name")) for p in pr}]
        fp = [f for f in blk(b, "frontend_port") if num(f.get("port")) == 80]
        return bool(pr and st and fp)
    pool_link = any_(refs(ip.get("application_gateway_backend_address_pool_ids"), "azurerm_application_gateway")
                     for n, b in vmss for ni in blk(b, "network_interface") for ip in blk(ni, "ip_configuration"))
    c["R10"] = any_(agw_ok(b) for n, b in agw) and pool_link
    mysql_deleg = set(n for n, b in subs if any(strv(sd.get("name")) == "Microsoft.DBforMySQL/flexibleServers" for d in blk(b, "delegation") for sd in blk(d, "service_delegation")))
    c["R11"] = any_((strv(b.get("version")) or "").startswith("8.0") and set(m for t, m in refs(b.get("delegated_subnet_id"), "azurerm_subnet")) & mysql_deleg
                    and num(b.get("backup_retention_days")) and any(strv(h.get("mode")) == "ZoneRedundant" for h in blk(b, "high_availability")) for n, b in my)
    agw_ip = set(m for n, b in agw for f in blk(b, "frontend_ip_configuration") for t, m in refs(f.get("public_ip_address_id"), "azurerm_public_ip"))
    c["R12"] = any_(set(m for t, m in refs(b.get("host_name"), "azurerm_public_ip")) & agw_ip for n, b in of(R, "azurerm_cdn_frontdoor_origin"))
    def alert_ok(b):
        if not refs(b.get("scopes"), "azurerm_linux_virtual_machine_scale_set"): return False
        return any(strv(cr.get("metric_name")) == "Percentage CPU" and (num(cr.get("threshold")) or 0) > 1 and strv(cr.get("operator")) == "GreaterThan" for cr in blk(b, "criteria"))
    c["R13"] = any_(alert_ok(b) for n, b in of(R, "azurerm_monitor_metric_alert"))
    return c

def grade(dirpath, provider):
    R, errs = load(dirpath)
    ch = gcp_checks(R) if provider == "gcp" else az_checks(R)
    ch = {k: int(bool(v)) for k, v in sorted(ch.items())}
    return dict(requirements=ch, score=sum(ch.values()) / len(ch), parse_errors=errs)

if __name__ == "__main__":
    print(json.dumps(grade(sys.argv[1], sys.argv[2]), indent=1))
