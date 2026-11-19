"""Core computations for the cross-provider correspondence audit.
All functions are pure; inputs are the CSV tables in data/."""
import re
from collections import Counter, defaultdict
import numpy as np
import pandas as pd

PROVS = ["aws", "azure", "gcp", "openstack"]
HYPER = ["aws", "azure", "gcp"]
PMAP = {"aws": "aws", "azure": "azurerm", "gcp": "google", "openstack": "openstack"}
SPECIAL = {"WIRE", "SCAF", "META"}
PREFIX = {"net": "K01", "sub": "K02", "inet": "K03", "nat": "K04", "fw": "K05", "id": "K06", "obj": "K07",
          "tmpl": "K08", "pool": "K09", "lb": "K10", "db": "K11", "cdn": "K12", "mon": "K13"}
GENERIC = {"id", "name", "arn", "type"}
SERVICE_TOKENS = {"compute", "networking", "cdn", "frontdoor", "monitor", "monitoring", "storage", "sql", "iam", "db",
                  "objectstorage", "cloudwatch", "cloudfront", "vpc", "service", "linux", "region", "regional", "global",
                  "images", "identity", "private", "lb", "network"}


def norm_type(rtype):
    return re.sub(r"_v\d$", "", re.sub(r"^(aws|azurerm|google|openstack|provider)_", "", rtype))


def leaf(path, rtype):
    return "T:" + norm_type(rtype) if path == "<type>" else path.split(".")[-1]


def strip_service(label):
    if not label.startswith("T:"):
        return label
    toks = label[2:].split("_")
    while len(toks) > 1 and toks[0] in SERVICE_TOKENS:
        toks = toks[1:]
    return "T:" + "_".join(toks)


def tokens(label):
    return {t for t in re.split(r"[_\.]", label.replace("T:", "")) if t and t not in GENERIC}


def explode(dec, code_col="codes", drop_type=False):
    z = dec.dropna(subset=[code_col]).copy()
    if drop_type:
        z = z[z.path != "<type>"]
    z["leaf"] = [leaf(p, r) for p, r in zip(z.path, z.rtype)]
    z["k"] = z[code_col].str.split("|").map(len)
    z = z.assign(code=z[code_col].str.split("|")).explode("code")
    z["w"] = 1.0 / z["k"]
    return z[~z.code.isin(SPECIAL)]


def load_sem_documented(df):
    sem = {}
    for r in df.itertuples():
        sem.setdefault(r.slot, {})[r.provider] = r.semantics
    return sem


def documented_divergent(sem, s, h, t):
    a, b = sem.get(s, {}).get(h), sem.get(s, {}).get(t)
    return a is not None and b is not None and a != b


def compute(dec, sem_doc, code_col="codes", identity="exact", drop_type=False, sem_mode="documented", adj=None,
            drop_concept=None, implicit=None, weights="slot", granularity="slot", provs=PROVS):
    """Slot-level categories for all ordered pairs.
    identity: exact (any leaf label shared) | strict (identical label sets) | token | prefix (service tokens stripped)
    sem_mode: none | documented | adjudicated (documented OR both judges divergent) | lower (documented only, = documented)
              | upper (documented OR any judge divergent/uncertain)
    adj: dict (slot, frozenset({a,b})) -> 'E' | 'D' | 'U' consensus, plus key ('any', slot, pair) for upper bound
    implicit: set of (provider, slot) realised by default/composition (T39 variant)
    weights: slot | decision | concept;  granularity: slot | concept"""
    z = explode(dec, code_col, drop_type)
    if granularity == "concept":
        z = z.assign(code=z.code.map(lambda c: PREFIX[c.split(".")[0]]))
    if drop_concept:
        z = z[z.code.map(lambda c: c if c.startswith("K") else PREFIX[c.split(".")[0]]) != drop_concept]
    lab = {p: z[z.provider == p].groupby("code").leaf.apply(set).to_dict() for p in provs}
    wt = {p: z[z.provider == p].groupby("code").w.sum().to_dict() for p in provs}
    rows, cats = [], []
    for h in provs:
        for t in provs:
            if h == t:
                continue
            SH, ST = lab[h], lab[t]
            recs = []
            for s in sorted(set(SH) | set(ST)):
                if s in ST and s not in SH:
                    c = "Rd" if (implicit and (h, s) in implicit) else "N"
                elif s in SH and s not in ST:
                    c = "D"
                else:
                    A, B = SH[s], ST[s]
                    if identity == "prefix":
                        A, B = {strip_service(x) for x in A}, {strip_service(x) for x in B}
                    if identity in ("exact", "prefix"):
                        same = len(A & B) > 0
                    elif identity == "strict":
                        same = A == B
                    else:
                        same = len(set().union(*[tokens(x) for x in A]) & set().union(*[tokens(x) for x in B])) > 0
                    dv = False
                    if granularity == "slot" and sem_mode != "none":
                        dv = documented_divergent(sem_doc, s, h, t)
                        key = (s, frozenset((h, t)))
                        if sem_mode == "adjudicated" and adj is not None:
                            dv = dv or adj.get(key) == "D"
                        elif sem_mode == "upper" and adj is not None:
                            dv = dv or adj.get(("any",) + key, False)
                    c = ("F" if dv else "I") if same else ("Rd" if dv else "R")
                concept = s if s.startswith("K") else PREFIX[s.split(".")[0]]
                recs.append((s, concept, c))
                cats.append(dict(home=h, target=t, slot=s, concept=concept, cat=c))
            tgt = [(s, k, c) for s, k, c in recs if c != "D"]
            if weights == "slot":
                w = {s: 1.0 for s, k, c in tgt}
            elif weights == "decision":
                w = {s: wt[t][s] for s, k, c in tgt}
            else:
                nk = Counter(k for s, k, c in tgt)
                w = {s: 1.0 / nk[k] for s, k, c in tgt}
            W = sum(w.values())
            sh = {c: sum(w[s] for s, k, cc in tgt if cc == c) / W for c in ["I", "R", "F", "Rd", "N"]}
            cnt = Counter(c for s, k, c in recs)
            rows.append(dict(home=h, target=t, n_target_slots=len(tgt), **{c: cnt.get(c, 0) for c in ["I", "R", "F", "Rd", "N", "D"]},
                             surface=sh["I"], abstraction=sh["I"] + sh["R"], divergent=sh["F"] + sh["Rd"], novel=sh["N"]))
    return pd.DataFrame(rows), pd.DataFrame(cats)


def summarise(pair, provs=None):
    q = pair if provs is None else pair[pair.home.isin(provs) & pair.target.isin(provs)]
    out = {f"{m}_mean": q[m].mean() for m in ["surface", "abstraction", "divergent", "novel"]}
    out.update({f"{m}_min": q[m].min() for m in ["surface", "abstraction"]})
    out.update({f"{m}_max": q[m].max() for m in ["surface", "abstraction"]})
    # micro average: pooled slot counts across pairs
    n = q.n_target_slots.sum()
    out["surface_micro"] = q.I.sum() / n
    out["abstraction_micro"] = (q.I.sum() + q.R.sum()) / n
    return out
