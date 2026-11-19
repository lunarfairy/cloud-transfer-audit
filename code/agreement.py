"""Agreement statistics for multi-label coding."""
import itertools
import numpy as np
import pandas as pd
from audit_core import SPECIAL, PREFIX

def cls(c): return c if c in SPECIAL else "SLOT"
def con(c): return c if c in SPECIAL else PREFIX[c.split(".")[0]]

def cohen(a, b):
    a, b = pd.Series(list(a)), pd.Series(list(b))
    po = (a.values == b.values).mean()
    pa, pb = a.value_counts(normalize=True), b.value_counts(normalize=True)
    pe = sum(pa.get(c, 0) * pb.get(c, 0) for c in set(a) | set(b))
    return po, (po - pe) / (1 - pe)

def masi(A, B):
    A, B = set(A), set(B)
    j = len(A & B) / len(A | B)
    m = 1 if A == B else (2 / 3 if (A <= B or B <= A) else (1 / 3 if A & B else 0))
    return 1 - j * m

def kripp_alpha(units, dist):
    """units: list of lists of values (one per coder present, >=2); dist: distance function."""
    units = [u for u in units if len(u) >= 2]
    vals = [v for u in units for v in u]
    n = len(vals)
    Do = sum(sum(dist(a, b) for a, b in itertools.permutations(u, 2)) / (len(u) - 1) for u in units) / n
    # expected disagreement over all pairable values
    from collections import Counter
    cnt = Counter(frozenset(v) if not isinstance(v, str) else v for v in vals)
    keys = list(cnt)
    De = sum(cnt[a] * cnt[b] * dist(a, b) for a in keys for b in keys if a != b) / (n * (n - 1))
    return 1 - Do / De

def pairwise(dfx, ca, cb):
    q = dfx.dropna(subset=[ca, cb])
    A, B = q[ca].str.split("|"), q[cb].str.split("|")
    out = dict(n=len(q))
    out["primary_agree"], out["kappa_primary"] = cohen(A.str[0], B.str[0])
    out["kappa_class"] = cohen(A.str[0].map(cls), B.str[0].map(cls))[1]
    out["kappa_concept"] = cohen(A.str[0].map(con), B.str[0].map(con))[1]
    sa, sb = A.map(frozenset), B.map(frozenset)
    out["set_exact"] = (sa.values == sb.values).mean()
    out["any_overlap"] = np.mean([len(x & y) > 0 for x, y in zip(sa, sb)])
    out["jaccard"] = np.mean([len(x & y) / len(x | y) for x, y in zip(sa, sb)])
    out["primary_mismatch"] = int((A.str[0].values != B.str[0].values).sum())
    out["set_disagree"] = int((sa.values != sb.values).sum())
    out["mismatch_but_same_set"] = int(((A.str[0].values != B.str[0].values) & (sa.values == sb.values)).sum())
    out["same_primary_diff_set"] = int(((A.str[0].values == B.str[0].values) & (sa.values != sb.values)).sum())
    out["alpha_masi"] = kripp_alpha([[x, y] for x, y in zip(sa, sb)], masi)
    return out
