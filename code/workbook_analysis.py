"""Analyse completed human-coding workbooks against the model codings.
Usage (from the repository root):
  python code/workbook_analysis.py workbook/completed_coder1.xlsx [workbook/completed_coder2.xlsx]
Writes workbook/human_validation_results.json and prints agreement tables."""
import json, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agreement as ag

def load(path):
    x = pd.read_excel(path, sheet_name=None, dtype=str)
    c = x["Coding"].fillna("")
    c["codes_H"] = [("|".join([v for v in (a.strip(), b.strip()) if v])) or None for a, b in zip(c.code_1, c.code_2)]
    s = x["Semantic"].fillna(""); s["verdict_H"] = s.verdict.str.strip().str.lower().replace("", None)
    i = x["Implicit"].fillna(""); i["agree_H"] = i.agree_disagree_unsure.str.strip().str.lower().replace("", None)
    return c[["unit_id", "codes_H"]], s[["pair_id", "verdict_H", "divergence_type"]], i[["row_id", "agree_H"]]

def main(paths):
    keyc = pd.read_csv("workbook/workbook_key_coding.csv"); keys = pd.read_csv("workbook/workbook_key_semantic.csv")
    codes = set(pd.read_csv("data/slot_catalogue.csv").slot) | {"WIRE", "SCAF", "META"}
    out = {}
    H = []
    for k, p in enumerate(paths, 1):
        c, s, i = load(p)
        bad = sorted({x for v in c.codes_H.dropna() for x in v.split("|")} - codes)
        m = keyc.merge(c, on="unit_id")
        res = {"n_coded": int(m.codes_H.notna().sum()), "invalid_codes": bad}
        for col in ["codes_A", "codes_B", "codes_C"]:
            r = ag.pairwise(m, "codes_H", col)
            res[f"vs_{col[-1]}"] = {kk: (float(v) if not isinstance(v, int) else v) for kk, v in r.items()}
            r2 = ag.pairwise(m[m.disagree], "codes_H", col)
            res[f"vs_{col[-1]}_model_disagreement_units"] = {kk: (float(v) if not isinstance(v, int) else v) for kk, v in r2.items()}
        ms = keys.merge(s, on="pair_id")
        mm = ms.dropna(subset=["verdict_H"])
        res["semantic_n"] = int(len(mm))
        for col in ["j1_verdict", "j2_verdict"]:
            q = mm.dropna(subset=[col])
            res[f"semantic_vs_{col[:2]}"] = dict(n=len(q), agree=float((q.verdict_H == q[col]).mean()) if len(q) else None,
                                                 kappa=float(ag.cohen(q.verdict_H, q[col])[1]) if len(q) > 1 else None)
        res["semantic_by_consensus"] = mm.groupby("consensus").verdict_H.value_counts().unstack(fill_value=0).to_dict()
        res["implicit_agreement"] = i.agree_H.value_counts().to_dict()
        out[f"coder{k}"] = res
        H.append((c, s))
    if len(H) == 2:
        c1, c2 = H[0][0].rename(columns={"codes_H": "h1"}), H[1][0].rename(columns={"codes_H": "h2"})
        m = c1.merge(c2, on="unit_id")
        out["human_vs_human"] = {k: (float(v) if not isinstance(v, int) else v) for k, v in ag.pairwise(m, "h1", "h2").items()}
        s1, s2 = H[0][1].rename(columns={"verdict_H": "v1"}), H[1][1].rename(columns={"verdict_H": "v2"})
        q = s1.merge(s2, on="pair_id").dropna(subset=["v1", "v2"])
        out["human_vs_human_semantic"] = dict(n=len(q), kappa=float(ag.cohen(q.v1, q.v2)[1]) if len(q) > 1 else None)
    json.dump(out, open("workbook/human_validation_results.json", "w"), indent=1, default=str)
    for k, v in out.items():
        print(k, json.dumps(v, default=str)[:600])

if __name__ == "__main__":
    main(sys.argv[1:])
