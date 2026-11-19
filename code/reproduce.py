"""Reproduce all metrics and LaTeX macros reported in the manuscript. Run from the repository root:
  python code/reproduce.py
Writes summary CSV/JSON outputs in data/ and tex/results_macros.tex, asserting consistency with ra/*/main.tf."""
import gzip, json, os, re, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_core as ac
import retrieval_v2 as rv
import agreement as ag

KEY = ["provider", "rtype", "rname", "path"]
AB = {"aws": "AWS", "azure": "Az", "gcp": "GCP", "openstack": "OS"}
VALUE_TYPES = {"units_or_scale", "default_behaviour", "scope_or_granularity", "value_vocabulary", "lifecycle_or_ordering", "other"}


def extract(path, provider):
    rows, stack, cur, skip = [], [], None, 0
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if skip:
            skip += s.count("{") - s.count("}"); continue
        m = re.match(r'^(resource|data)\s+"([\w-]+)"\s+"([\w-]+)"\s*\{$', s)
        if m:
            cur, stack = dict(kind=m[1], rtype=m[2], rname=m[3]), []; continue
        m = re.match(r'^(provider)\s+"([\w-]+)"\s*\{$', s)
        if m:
            cur, stack = dict(kind="provider", rtype="provider_" + m[2], rname=m[2]), []; continue
        if re.match(r"^(terraform|variable|locals|output)\b.*\{$", s) and not stack:
            cur, skip = None, s.count("{") - s.count("}"); continue
        if cur is None:
            continue
        m = re.match(r"^([\w]+)\s*\{\s*\}$", s)
        if m:
            rows.append(dict(provider=provider, **cur, path=".".join(stack + [m[1]]))); continue
        m = re.match(r"^([\w]+)\s*\{$", s)
        if m:
            if m[1] in {"count", "depends_on", "lifecycle", "for_each", "provider"}: skip = 1
            else: stack.append(m[1])
            continue
        m = re.match(r"^([\w]+)\s*=\s*(.*)$", s)
        if m:
            if m[1] in {"count", "depends_on", "lifecycle", "for_each", "provider"}:
                v = m[2].strip()
                if v.endswith("[") or v.endswith("{"):
                    skip = v.count("{") + v.count("[") - v.count("}") - v.count("]")
                continue
            if m[2].endswith("{"): skip = 1
            rows.append(dict(provider=provider, **cur, path=".".join(stack + [m[1]]))); continue
        if s == "}":
            if stack: stack.pop()
            else: cur = None
    return pd.DataFrame(rows)


def summ(pair, tag, out):
    a, b = ac.summarise(pair), ac.summarise(pair, ac.HYPER)
    aw = pair[pair.home == "aws"]
    out.update({f"sur{tag}Mean": a["surface_mean"], f"abs{tag}Mean": a["abstraction_mean"], f"div{tag}Mean": a["divergent_mean"],
                f"nov{tag}Mean": a["novel_mean"], f"abs{tag}HypMean": b["abstraction_mean"], f"sur{tag}HypMean": b["surface_mean"],
                f"abs{tag}AwsMin": aw.abstraction.min(), f"abs{tag}AwsMax": aw.abstraction.max(),
                f"sur{tag}AwsMin": aw.surface.min(), f"sur{tag}AwsMax": aw.surface.max()})


def main():
    V = {}
    dec = pd.read_csv("data/coded_decisions.csv")
    D = pd.concat([extract(f"ra/{p}/main.tf", p) for p in ac.PROVS], ignore_index=True)
    args = dec[dec.path != "<type>"]
    assert len(D) == len(args) and set(map(tuple, D[KEY].values)) == set(map(tuple, args[KEY].values)), "decision table does not match ra/*.tf"
    decA = dec.rename(columns={"codes_A": "codes"})
    sem = ac.load_sem_documented(pd.read_csv("data/semantic_divergence_table.csv"))
    cat = pd.read_csv("data/slot_catalogue.csv")
    schemas = json.load(gzip.open("schemas/schemas.json.gz", "rt", encoding="utf-8"))
    PS = {k.split("/")[-1]: v["resource_schemas"] for k, v in schemas["provider_schemas"].items()}
    # ---------- counts and reconciliation ----------
    V.update(nDecRows=len(dec), nArgs=int((dec.path != "<type>").sum()), nTypeDec=int((dec.path == "<type>").sum()),
             nUnits=len(dec.drop_duplicates(KEY)), nSlots=len(cat))
    V["nDupPaths"] = V["nDecRows"] - V["nUnits"]
    z = ac.explode(decA)
    for p in ac.PROVS:
        q = dec[dec.provider == p]
        V["args" + AB[p]] = int((q.path != "<type>").sum())
        V["blocks" + AB[p]] = int(q[q.kind.isin(["resource", "data"])].drop_duplicates(["rtype", "rname"]).shape[0])
        V["types" + AB[p]] = int(q[q.kind.isin(["resource", "data"])].rtype.nunique())
        V["typesSlot" + AB[p]] = int(z[(z.provider == p) & (z.path == "<type>")].rtype.nunique())
        V["slots" + AB[p]] = int(z[z.provider == p].code.nunique())
        V["schema" + AB[p]] = len(PS[ac.PMAP[p]])
    V["nBlocks"] = sum(V["blocks" + AB[p]] for p in ac.PROVS)
    V["nProvBlocksCoded"] = int(dec[dec.kind == "provider"].provider.nunique())
    V["nRequests"] = V["nBlocks"] + V["nProvBlocksCoded"]
    ud = dec.drop_duplicates(["provider", "rtype", "path"]).copy()
    ud["cls"] = [c.split("|")[0] if c.split("|")[0] in ac.SPECIAL else "SLOT" for c in ud.codes_A]
    gl = ud.groupby(["provider", "cls"]).size().unstack(fill_value=0)
    for p in ac.PROVS:
        V["glue" + AB[p]] = (gl.loc[p, "WIRE"] + gl.loc[p, "SCAF"]) / gl.loc[p, ["SLOT", "WIRE", "SCAF"]].sum()
    sp = z.groupby("code").provider.nunique()
    V["nSharedSlots"] = int((sp >= 2).sum()); V["nSingleSlots"] = int((sp == 1).sum())
    pd.DataFrame([
        dict(quantity="decision rows", value=V["nDecRows"], definition="configured argument paths plus one type choice per resource/data block"),
        dict(quantity="configured arguments", value=V["nArgs"], definition="argument paths of resource, data and provider blocks (meta-arguments excluded)"),
        dict(quantity="type choices", value=V["nTypeDec"], definition="one per resource or data block (provider blocks have none)"),
        dict(quantity="coding units", value=V["nUnits"], definition=f"unique (provider, type, block name, path); {V['nDupPaths']} repeated paths in Azure autoscale rule blocks are coded once"),
        dict(quantity="configuration blocks", value=V["nBlocks"], definition="resource and data blocks"),
        dict(quantity="coder requests", value=V["nRequests"], definition="blocks plus provider blocks with at least one configured argument"),
    ] + [dict(quantity=f"distinct types {p}", value=V["types" + AB[p]], definition=f"resource+data types; {V['typesSlot' + AB[p]]} of them coded to a slot")
         for p in ac.PROVS]).to_csv("data/count_reconciliation.csv", index=False)
    # ---------- primary indices and variants ----------
    imp = pd.read_csv("data/implicit_realisation.csv"); impset = set(zip(imp.provider, imp.slot))
    V["nImplicit"] = len(imp)
    J = pd.read_csv("data/semantic_adjudication.csv")
    adj_cons, adj_val, adj_any = {}, {}, {}
    for r in J.itertuples():
        k = (r.slot, frozenset((r.prov_a, r.prov_b)))
        adj_cons[k] = r.consensus
        adj_val[k] = "D" if (r.consensus == "D" and (r.j1_divergence_type in VALUE_TYPES or r.j2_divergence_type in VALUE_TYPES)) else "E"
        adj_any[("any",) + k] = bool(r.any_div_or_unc)
    pair, cats = ac.compute(decA, sem)
    pair.to_csv("data/pair_indices.csv", index=False); cats.to_csv("data/slot_categories_by_pair.csv", index=False)
    for r in pair.itertuples():
        t = AB[r.home] + AB[r.target]
        V["sur" + t], V["abs" + t], V["div" + t], V["nov" + t] = r.surface, r.abstraction, r.divergent, r.novel
        V["corr" + t] = 1 - r.novel; V["drop" + t] = r.D; V["dropsh" + t] = r.D / V["slots" + AB[r.home]]
        V["ntgt" + t] = r.n_target_slots
    summ(pair, "", V)
    V.update(surMin=pair.surface.min(), surMax=pair.surface.max(), absMin=pair.abstraction.min(), absMax=pair.abstraction.max(),
             corrMean=1 - pair.novel.mean(), corrMin=1 - pair.novel.max(), corrMax=1 - pair.novel.min(),
             absMicro=ac.summarise(pair)["abstraction_micro"], surMicro=ac.summarise(pair)["surface_micro"])
    variants = {
        "primary": {}, "coder B codes": dict(code_col="codes_B"), "coder C codes": dict(code_col="codes_C"),
        "strict identity (all labels identical)": dict(identity="strict"), "token identity (lenient)": dict(identity="token"),
        "service prefixes stripped": dict(identity="prefix"), "arguments only": dict(drop_type=True),
        "divergence ignored": dict(sem_mode="none"), "decision-weighted": dict(weights="decision"),
        "concept-balanced": dict(weights="concept"), "concept granularity": dict(granularity="concept"),
        "implicit realisation counted": dict(implicit=impset),
        "semantic: + consensus value divergence": dict(sem_mode="adjudicated", adj=adj_val),
        "semantic: + consensus any divergence": dict(sem_mode="adjudicated", adj=adj_cons),
        "semantic: + any judge non-equivalent": dict(sem_mode="upper", adj=adj_any)}
    tags = {"coder B codes": "CB", "coder C codes": "CC", "strict identity (all labels identical)": "Strict", "token identity (lenient)": "Tok",
            "service prefixes stripped": "Pre", "arguments only": "Arg", "divergence ignored": "NoDiv", "decision-weighted": "DecW",
            "concept-balanced": "ConB", "concept granularity": "ConG", "implicit realisation counted": "Imp",
            "semantic: + consensus value divergence": "Val", "semantic: + consensus any divergence": "Any",
            "semantic: + any judge non-equivalent": "Up"}
    rows = []
    for name, kw in variants.items():
        dd = decA.rename(columns={"codes": "codes_primary", kw.get("code_col", "codes"): "codes"}) if "code_col" in kw else decA
        kw2 = {k: v for k, v in kw.items() if k != "code_col"}
        pv, cv = ac.compute(dd, sem, **kw2)
        pv.assign(variant=name).to_csv(f"data/pair_indices_variant_{tags.get(name, 'primary')}.csv", index=False)
        a, b = ac.summarise(pv), ac.summarise(pv, ac.HYPER); aw = pv[pv.home == "aws"]
        rows.append(dict(variant=name, surface_mean=a["surface_mean"], abstraction_mean=a["abstraction_mean"], divergent_mean=a["divergent_mean"],
                         novel_mean=a["novel_mean"], abstraction_hyper_mean=b["abstraction_mean"], surface_aws_min=aw.surface.min(),
                         surface_aws_max=aw.surface.max(), abstraction_aws_min=aw.abstraction.min(), abstraction_aws_max=aw.abstraction.max()))
        if name in tags:
            summ(pv, tags[name], V)
        if name.startswith("semantic"):
            for r in pv[pv.home == "aws"].itertuples():
                V["abs" + tags[name] + "AWS" + AB[r.target]] = r.abstraction
                V["div" + tags[name] + "AWS" + AB[r.target]] = r.divergent
    pd.DataFrame(rows).to_csv("data/robustness_variants.csv", index=False)
    # jackknife
    jk = [ac.compute(decA, sem, drop_concept=k)[0] for k in sorted(set(ac.PREFIX.values()))]
    V["jkAbsMin"] = min(p[p.home == "aws"].abstraction.min() for p in jk); V["jkAbsMax"] = max(p[p.home == "aws"].abstraction.max() for p in jk)
    V["jkSurMin"] = min(p[p.home == "aws"].surface.min() for p in jk); V["jkSurMax"] = max(p[p.home == "aws"].surface.max() for p in jk)
    # ---------- concept profiles from AWS ----------
    def profile(c):
        q = c[(c.home == "aws") & (c.cat != "D")]
        g = q.groupby("concept").cat.value_counts().unstack(fill_value=0).reindex(columns=["I", "R", "F", "Rd", "N"], fill_value=0)
        n = g.sum(1)
        return pd.DataFrame(dict(n=n, surface=g.I / n, abstraction=(g.I + g.R) / n, divergent=(g.F + g.Rd) / n, novel=g.N / n))
    prof = profile(cats)
    prof_val = profile(ac.compute(decA, sem, sem_mode="adjudicated", adj=adj_val)[1])
    prof_any = profile(ac.compute(decA, sem, sem_mode="adjudicated", adj=adj_cons)[1])
    prof = prof.join(prof_val[["abstraction", "divergent"]].add_suffix("_val")).join(prof_any[["abstraction", "divergent"]].add_suffix("_any"))
    prof["gap"] = prof.abstraction - prof.surface
    prof.to_csv("data/concept_profile_from_aws.csv")
    for k, r in prof.iterrows():
        V["surc" + k], V["absc" + k], V["divc" + k], V["novc" + k], V["gap" + k] = r.surface, r.abstraction, r.divergent, r.novel, r.gap
        V["abscval" + k], V["abscany" + k], V["nc" + k] = r.abstraction_val, r.abstraction_any, int(r.n)
    # ---------- agreement ----------
    U = dec.drop_duplicates(KEY)
    agr = {}
    for a, b, t in [("codes_A", "codes_B", "AB"), ("codes_A", "codes_C", "AC"), ("codes_B", "codes_C", "BC")]:
        s = ag.pairwise(U, a, b); agr[t] = s
        for k2, v in s.items():
            V[f"{k2}{t}"] = v
    units = [[frozenset(x.split("|")) for x in r if isinstance(x, str)] for r in U[["codes_A", "codes_B", "codes_C"]].values]
    V["alphaMasiThree"] = ag.kripp_alpha(units, ag.masi)
    unitsP = [[x.split("|")[0] for x in r if isinstance(x, str)] for r in U[["codes_A", "codes_B", "codes_C"]].values]
    V["alphaNomThree"] = ag.kripp_alpha(unitsP, lambda a, b: float(a != b))
    # conditional concept kappa (both coders slot)
    for a, b, t in [("codes_A", "codes_B", "AB"), ("codes_A", "codes_C", "AC")]:
        q = U.dropna(subset=[a, b]); pa, pb = q[a].str.split("|").str[0], q[b].str.split("|").str[0]
        m = ~pa.isin(ac.SPECIAL) & ~pb.isin(ac.SPECIAL)
        V[f"kappaConceptCond{t}"] = ag.cohen(pa[m].map(ag.con), pb[m].map(ag.con))[1]; V[f"nConceptCond{t}"] = int(m.sum())
    pd.DataFrame(agr).T.to_csv("data/agreement.csv")
    # baseline coding comparison
    v1 = pd.read_csv("data/coded_decisions_v1.csv").dropna(subset=["codes2"]).drop_duplicates(KEY)
    s1 = ag.pairwise(v1, "codes", "codes2")
    V.update(voneN=s1["n"], voneAgree=s1["primary_agree"], voneKappa=s1["kappa_primary"], voneMismatch=s1["primary_mismatch"],
             voneNoOverlap=int(round(s1["n"] * (1 - s1["any_overlap"]))), voneSetDis=s1["set_disagree"], voneOverlap=s1["any_overlap"])
    pa, pb = v1.codes.str.split("|").str[0], v1.codes2.str.split("|").str[0]
    m = ~pa.isin(ac.SPECIAL) & ~pb.isin(ac.SPECIAL)
    V["voneConceptCond"] = ag.cohen(pa[m].map(ag.con), pb[m].map(ag.con))[1]
    V["voneConceptUncond"] = ag.cohen(pa.map(ag.con), pb.map(ag.con))[1]
    # ---------- semantic judges ----------
    both = J.dropna(subset=["j1_verdict", "j2_verdict"])
    V.update(nSemPairs=len(J), judgeN=len(both), judgeAgree=(both.j1_verdict == both.j2_verdict).mean(),
             judgeKappa=ag.cohen(both.j1_verdict, both.j2_verdict)[1], jOneDiv=int((J.j1_verdict == "divergent").sum()),
             jTwoDiv=int((J.j2_verdict == "divergent").sum()), jTwoMissing=int(J.j2_verdict.isna().sum()),
             consD=int((J.consensus == "D").sum()), consE=int((J.consensus == "E").sum()), consU=int((J.consensus == "U").sum()),
             jOneQuoteOk=int((J.j1_quote_ok == True).sum()), jOneQuoteN=int(J.j1_quote_ok.notna().sum()),
             jTwoQuoteOk=int((J.j2_quote_ok == True).sum()), jTwoQuoteN=int(J.j2_quote_ok.notna().sum()),
             nDocDivPairs=int(J.documented_div.sum()), docDivConsD=int((J.documented_div & (J.consensus == "D")).sum()),
             docDivConsE=int((J.documented_div & (J.consensus == "E")).sum()), nSem=len(sem))
    dtype = J[J.consensus == "D"].apply(lambda r: "value" if (r.j1_divergence_type in VALUE_TYPES or r.j2_divergence_type in VALUE_TYPES) else "composition", axis=1)
    V["consDvalue"], V["consDcomp"] = int((dtype == "value").sum()), int((dtype == "composition").sum())
    tc = J[J.consensus == "D"].j1_divergence_type.value_counts()
    for k2 in ["composition", "value_vocabulary", "scope_or_granularity", "units_or_scale", "default_behaviour"]:
        V["consDtype" + re.sub(r"[^A-Za-z]", "", k2.title())] = int(tc.get(k2, 0))
    # ---------- false friends ----------
    ff = pd.read_csv("data/lexical_false_friends.csv")
    V["nFF"], V["nFFaws"] = len(ff), int((ff.home == "aws").sum())
    ffu = ff.assign(pair=[tuple(sorted((a, b))) for a, b in zip(ff.home, ff.target)]).drop_duplicates(["pair", "label"])
    V["nFFu"] = len(ffu)
    for k2, n in ffu.kind.value_counts().items(): V["nFF" + k2.replace("_", "").title()] = int(n)
    # ---------- retrieval ----------
    slot_defs = dict(zip(cat.slot, cat.definition + " " + cat.concept_name))
    R = rv.run(decA, schemas, slot_defs); R.to_csv("data/retrieval_tie_aware.csv", index=False)
    S = rv.summary(R); S.to_csv("data/retrieval_summary.csv")
    cue_tag = {"name": "Name", "name_stem": "Stem", "name_char": "Char", "name_args": "Arg", "name_args_desc": "Desc", "role_description": "Role"}
    for cue, r in S.iterrows():
        t = cue_tag[cue]
        V.update({f"ret{t}N": int(r.n), f"ret{t}Hitone": r.hit1, f"ret{t}Hitten": r.hit10, f"ret{t}MRR": r.mrr, f"ret{t}Med": r.med_rank,
                  f"ret{t}Zero": r.zero, f"ret{t}Recall": r.recall10, f"ret{t}Pct": r.pct_rank, f"ret{t}Tied": r.tied_gt1, f"ret{t}Chance": r.chance_hit10})
    nm = R[R.cue == "name"]
    V["retNameZeroN"] = int(nm.zero_overlap.sum())
    V["retNameChanceOne"] = nm.chance_hit1.mean()
    # tie-bound check against catalogue-order ranking
    v1dec = pd.read_csv("data/coded_decisions_v1.csv")
    Rv1 = rv.run(v1dec, schemas, slot_defs)
    o = Rv1[Rv1.cue.isin(["name", "name_args"])].copy(); o["cue"] = o.cue.map({"name": "name only", "name_args": "name+arguments"})
    old = pd.read_csv("data/retrieval_results_v1.csv")
    mrg = o.merge(old, on=["cue", "home", "target", "home_type"], how="outer", indicator=True)
    assert (mrg._merge == "both").all(), "baseline query set mismatch"
    inside = ((mrg.best_rank >= mrg.rank_opt) & (mrg.best_rank <= mrg.rank_pess))
    assert inside.all(), "a catalogue-order rank lies outside its tie bounds"
    V["voneRetN"] = int(len(mrg)); V["voneRetInside"] = int(inside.sum())
    V["voneRetNameMed"] = float(old[old.cue == "name only"].best_rank.median())
    # ---------- conformance, grader, trial ----------
    mt = pd.read_csv("data/conformance_mutation_results.csv")
    V["nMut"], V["nMutDet"] = len(mt), int(mt.detected.sum())
    gv = json.load(open("data/grader_validation_summary.json"))
    V.update(graderN=gv["n_mutants"], graderDet=gv["detected"], graderSame=gv["same_as_tofu"], syntaxN=gv["syntax_n"],
             syntaxMean=gv["syntax_mean"], syntaxMin=gv["syntax_min"], syntaxFull=gv["syntax_full"])
    ho = pd.read_csv("data/grader_validation_holdout.csv")
    V.update(holdN=len(ho), holdGrader=int(ho.grader_detected.sum()), holdSuite=int(ho.tofu_detected.sum()),
             holdGraderAny=int((ho.grader_fails.fillna("") != "").sum()), holdSuiteAny=int((ho.tofu_exit != 0).sum()))
    if os.path.exists("data/trial_simulation_grid.csv"):
        tg = pd.read_csv("data/trial_simulation_grid.csv")
        for _, r in tg.iterrows():
            t = f"J{int(r.J)}r{int(round(r.rho * 100)):02d}a{int(round(r.attrition * 100)):02d}"
            for c in ["power_H1_holm", "power_H3_holm", "power_H2", "power_H4", "typeI_H1", "typeI_H3", "H2_slope_ci_halfwidth"]:
                V[f"sim{c.replace('_', '')}{t}"] = r[c]
        V["simTypeIMax"] = float(tg[["typeI_H1", "typeI_H3"]].max().max()); V["simTypeIMin"] = float(tg[["typeI_H1", "typeI_H3"]].min().min())
    json.dump({k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int)) else v) for k, v in V.items()},
              open("data/results_values.json", "w"), indent=1, sort_keys=True)
    write_macros(V)
    print("decision rows", V["nDecRows"], "| abstraction mean", round(V["absMean"], 3), "| bounds", round(V["absValMean"], 3), round(V["absAnyMean"], 3), round(V["absUpMean"], 3))
    print("all checks passed")


WORD = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}

def mname(k):
    return "v" + "".join(WORD.get(ch, ch) for ch in k if ch.isalnum())

PCT_PREFIX = ("sur", "abs", "div", "nov", "corr", "dropsh", "glue", "gap", "ret", "jk", "judgeAgree", "voneAgree", "voneOverlap",
              "primary_agree", "set_exact", "any_overlap", "syntax", "sim", "agree")

def fmt(k, v):
    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        return f"{v:,}".replace(",", "{,}")
    if k.startswith(("kappa", "alpha", "voneKappa", "voneConcept", "judgeKappa", "jaccard")):
        return f"{v:.3f}"
    if k.startswith("ret") and k.endswith("Med") or k == "voneRetNameMed":
        return f"{v:.0f}"
    if k.startswith("simH2slopecihalfwidth"):
        return f"{v:.2f}"
    if k.startswith(("simpower", "simtypeI", "simTypeI")):
        return f"{v:.2f}".lstrip("0") if v < 1 else "1.00"
    if k.endswith("MRR"):
        return f"{v:.2f}"
    if k.startswith(PCT_PREFIX) or k.startswith(("prim", "set")):
        return f"{100 * v:.1f}\\%"
    return f"{v:.3f}"

def write_macros(V):
    lines = ["% generated by code/reproduce.py -- do not edit"]
    seen = set()
    for k, v in sorted(V.items()):
        n = mname(k)
        if n in seen: raise ValueError("macro collision " + n)
        seen.add(n)
        lines.append(f"\\newcommand{{\\{n}}}{{{fmt(k, v)}}}")
    os.makedirs("tex", exist_ok=True)
    open("tex/results_macros.tex", "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
