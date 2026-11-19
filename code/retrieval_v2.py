"""Tie-aware lexical retrieval benchmark."""
import re
from collections import Counter
from math import comb, log
import numpy as np
import pandas as pd
from audit_core import PROVS, PMAP, SPECIAL, norm_type

STOP = set()

def stem(t):
    for suf in ("ies", "es", "s"):
        if len(t) > 4 and t.endswith(suf):
            return t[:-len(suf)] + ("y" if suf == "ies" else "")
    return t

def name_tokens(rt):
    return [x for x in norm_type(rt).split("_") if x and x not in STOP]

def attr_tokens(blk):
    toks = []
    for a, spec in blk.get("attributes", {}).items():
        if not spec.get("computed") or spec.get("optional") or spec.get("required"):
            toks += a.split("_")
    for b in blk.get("block_types", {}):
        toks += b.split("_")
    return toks

def desc_tokens(blk):
    txt = " ".join([blk.get("description", "") or ""] + [(s.get("description") or "") for s in blk.get("attributes", {}).values()])
    return [w for w in re.findall(r"[a-z]{3,}", txt.lower())]

def char_ngrams(toks, lo=3, hi=5):
    s = " " + " ".join(toks) + " "
    return [s[i:i + n] for n in range(lo, hi + 1) for i in range(len(s) - n + 1) if not s[i:i+n].isspace()]

def tfidf_index(docs):
    df = Counter(t for d in docs for t in set(d))
    N = len(docs)
    idf = {t: log((N + 1) / (c + 1)) + 1 for t, c in df.items()}
    vecs = []
    for d in docs:
        c = Counter(d)
        v = {t: (1 + log(n)) * idf[t] for t, n in c.items()}
        nrm = np.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / nrm for t, x in v.items()})
    return idf, vecs

def score(q_toks, idf, vecs):
    c = Counter(q_toks)
    q = {k: (1 + log(n)) * idf.get(k, 0.0) for k, n in c.items()}
    nq = np.sqrt(sum(x * x for x in q.values())) or 1.0
    q = {k: x / nq for k, x in q.items() if x}
    return np.array([sum(q.get(k, 0.0) * v for k, v in vec.items()) for vec in vecs])

def tie_stats(scores, rel_idx, eps=1e-12):
    """Best-relevant rank statistics under uniformly random tie-breaking."""
    rel = np.zeros(len(scores), bool); rel[list(rel_idx)] = True
    sstar = scores[rel].max()
    g = int((scores > sstar + eps).sum())
    tied = np.abs(scores - sstar) <= eps
    e = int(tied.sum()); r = int((tied & rel).sum())
    tot = comb(e, r)
    pmin = {g + j: comb(e - j, r - 1) / tot for j in range(1, e - r + 2)}
    exp_rank = sum(k * p for k, p in pmin.items())
    mrr = sum(p / k for k, p in pmin.items())
    hit = lambda k: sum(p for kk, p in pmin.items() if kk <= k)
    # recall@10 over all relevant items
    rec = []
    for i in np.where(rel)[0]:
        gi = int((scores > scores[i] + eps).sum()); ei = int((np.abs(scores - scores[i]) <= eps).sum())
        rec.append(min(max((10 - gi) / ei, 0.0), 1.0))
    N = len(scores); R = int(rel.sum())
    chance_hit = lambda k: 1 - comb(N - R, k) / comb(N, k)
    return dict(best_score=float(sstar), zero_overlap=bool(sstar <= eps), rank_opt=g + 1, rank_pess=g + e - r + 1,
                rank_exp=exp_rank, hit1=hit(1), hit10=hit(10), rr=mrr, recall10=float(np.mean(rec)), n_rel=R, N=N,
                tied_block=e, chance_hit1=chance_hit(1), chance_hit10=chance_hit(10), chance_rank=(N + 1) / (R + 1),
                pct_rank=exp_rank / N)

def run(dec, schemas, slot_defs):
    PS = {k.split("/")[-1]: v["resource_schemas"] for k, v in schemas["provider_schemas"].items()}
    z = dec.assign(code=dec.codes.str.split("|")).explode("code")
    typ = z[(z.path == "<type>") & (~z.code.isin(SPECIAL)) & (z.kind == "resource")][["provider", "rtype", "code"]].drop_duplicates()
    cues = {
        "name": lambda p, rt, blk: name_tokens(rt),
        "name_stem": lambda p, rt, blk: [stem(t) for t in name_tokens(rt)],
        "name_char": lambda p, rt, blk: char_ngrams(name_tokens(rt)),
        "name_args": lambda p, rt, blk: name_tokens(rt) + attr_tokens(blk),
        "name_args_desc": lambda p, rt, blk: name_tokens(rt) + attr_tokens(blk) + desc_tokens(blk),
    }
    out = []
    for cue, f in cues.items():
        idx = {}
        for p in PROVS:
            types = sorted(PS[PMAP[p]].keys())
            idf, vecs = tfidf_index([f(p, rt, PS[PMAP[p]][rt]["block"]) for rt in types])
            idx[p] = (types, idf, vecs)
        for h in PROVS:
            for t in PROVS:
                if h == t:
                    continue
                types, idf, vecs = idx[t]
                pos = {rt: i for i, rt in enumerate(types)}
                Hs, Ts = typ[typ.provider == h], typ[typ.provider == t]
                for rt, gq in Hs.groupby("rtype"):
                    targets = sorted(set(Ts[Ts.code.isin(set(gq.code))].rtype))
                    if not targets:
                        continue
                    q = f(h, rt, PS[PMAP[h]][rt]["block"])
                    sc = score(q, idf, vecs)
                    st = tie_stats(sc, [pos[x] for x in targets])
                    out.append(dict(cue=cue, home=h, target=t, home_type=rt, targets="|".join(targets), **st))
    # vendor-neutral role-description cue against name+args documents
    idx = {}
    for p in PROVS:
        types = sorted(PS[PMAP[p]].keys())
        docs = [name_tokens(rt) + attr_tokens(PS[PMAP[p]][rt]["block"]) for rt in types]
        idx[p] = (types,) + tfidf_index(docs)
    for h in PROVS:
        for t in PROVS:
            if h == t:
                continue
            types, idf, vecs = idx[t]
            pos = {rt: i for i, rt in enumerate(types)}
            Hs, Ts = typ[typ.provider == h], typ[typ.provider == t]
            for rt, gq in Hs.groupby("rtype"):
                targets = sorted(set(Ts[Ts.code.isin(set(gq.code))].rtype))
                if not targets:
                    continue
                words = " ".join(slot_defs[c] for c in sorted(set(gq.code)))
                q = [w for w in re.findall(r"[a-z]+", words.lower()) if len(w) > 2]
                st = tie_stats(score(q, idf, vecs), [pos[x] for x in targets])
                out.append(dict(cue="role_description", home=h, target=t, home_type=rt, targets="|".join(targets), **st))
    return pd.DataFrame(out)

def summary(res):
    return res.groupby("cue").agg(n=("rr", "size"), hit1=("hit1", "mean"), hit10=("hit10", "mean"), mrr=("rr", "mean"),
                                  med_rank=("rank_exp", "median"), zero=("zero_overlap", "mean"), recall10=("recall10", "mean"),
                                  chance_hit10=("chance_hit10", "mean"), pct_rank=("pct_rank", "median"),
                                  tied_gt1=("tied_block", lambda x: (x > 1).mean()))
