"""Generate supplementary LaTeX tables from data/. Run from the repository root:
python code/make_supplement_tables.py  -> tex/supp_*.tex"""
import json, os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_core as ac
NAME = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud", "openstack": "OpenStack"}
SH = {"aws": "AWS", "azure": "Az", "gcp": "GC", "openstack": "OS"}
def esc(x):
    x = "" if (x is None or (isinstance(x, float) and np.isnan(x))) else str(x)
    for a, b in [("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("$", "\\$"), ("#", "\\#"), ("_", "\\_"), ("{", "\\{"), ("}", "\\}"), ("~", "\\textasciitilde{}"), ("^", "\\textasciicircum{}")]:
        x = x.replace(a, b)
    return x
def longtable(name, spec, header, rows, caption, label, note=""):
    s = "\\begin{footnotesize}\n\\begin{longtable}{" + spec + "}\n\\caption{" + caption + "}\\label{" + label + "}\\\\\n\\toprule\n" + header + " \\\\ \\midrule\n\\endfirsthead\n\\toprule\n" + header + " \\\\ \\midrule\n\\endhead\n\\bottomrule\n\\endfoot\n"
    s += "\n".join(" & ".join(r) + " \\\\" for r in rows) + "\n\\end{longtable}\n\\end{footnotesize}\n"
    if note: s += "\\noindent{\\footnotesize " + note + "}\n\n"
    os.makedirs("tex", exist_ok=True)
    open(f"tex/{name}.tex", "w", encoding="utf-8").write(s)

def catalogue():
    cat = pd.read_csv("data/slot_catalogue.csv"); d = pd.read_csv("data/coded_decisions.csv")
    z = ac.explode(d.rename(columns={"codes_A": "codes"}))
    real = z.groupby("code").provider.apply(lambda s: ", ".join(SH[p] for p in ac.PROVS if p in set(s)))
    rows = [[esc(r.slot), r.concept, esc(r.definition), real.get(r.slot, "")] for r in cat.itertuples()]
    longtable("supp_catalogue", "p{3.3cm}lp{6.6cm}p{2.2cm}", "Slot & Concept & Definition & Realised by", rows,
              "Slot catalogue: 139 vendor-neutral configuration roles.", "tab:s-catalogue")

def mutations():
    m = pd.read_csv("data/conformance_mutation_results.csv")
    rows = [[NAME[r.provider], r.mutation_target, "\\texttt{" + esc(str(r.mutation)[:95]) + "}", esc(r.failed_reqs), "yes" if r.detected else "no"] for r in m.itertuples()]
    longtable("supp_mutations", "llp{7.4cm}ll", "Provider & Target & Injected fault (before $\\rightarrow$ after) & Failed & Detected", rows,
              "Mutation testing of the offline conformance suites.", "tab:s-mutations",
              "One AWS R06 fault (an added wildcard IAM statement) was missed by the initial suite; the assertion was tightened and the fault re-tested (detected). Two cross-wiring faults and a route-table fault were missed before per-instance mock identifiers and route-table assertions were added.")

def semantic():
    J = pd.read_csv("data/semantic_adjudication.csv")
    g = J.groupby("slot")
    rows = []
    for s, q in g:
        rows.append([esc(s), str(len(q)), str(int((q.j1_verdict == "divergent").sum())), str(int((q.j2_verdict == "divergent").sum())),
                     str(int((q.consensus == "D").sum())), str(int((q.consensus == "E").sum())), str(int((q.consensus == "U").sum())),
                     esc(", ".join(sorted(set(q[q.consensus == "D"].j1_divergence_type.dropna())))), "yes" if q.documented_div.any() else ""])
    longtable("supp_semantic", "p{3.0cm}rrrrrrp{3.4cm}l", "Slot & Pairs & J1 div. & J2 div. & D & E & U & J1 types (consensus D) & Doc.", rows,
              "Semantic adjudication by slot (both judges; D/E/U = consensus divergent/equivalent/uncertain).", "tab:s-semantic",
              "Per-pair verdicts, divergence types, rationales and evidence quotes (with verbatim check) are in \\texttt{data/semantic\\_adjudication.csv}.")

def implicit():
    I = pd.read_csv("data/implicit_realisation.csv")
    rows = [[NAME[r.provider], esc(r.slot), r.kind, esc(r.basis)] for r in I.itertuples()]
    longtable("supp_implicit", "llp{1.8cm}p{8.6cm}", "Provider & Slot & Kind & Basis", rows,
              "Author-judged implicit realisations (function provided by default or by composition, without a coded decision).", "tab:s-implicit")

def falsefriends():
    F = pd.read_csv("data/lexical_false_friends.csv")
    F["pair"] = [tuple(sorted((a, b))) for a, b in zip(F.home, F.target)]
    U = F.drop_duplicates(["pair", "label"])
    rows = []
    for r in U.itertuples():
        a, b = r.pair
        ca = r.home_codes if r.home == a else r.target_codes
        cb = r.target_codes if r.home == a else r.home_codes
        rows.append([f"{SH[a]}--{SH[b]}", "\\texttt{" + esc(r.label) + "}", esc(ca), esc(cb), r.kind.replace("_", " ")])
    longtable("supp_falsefriends", "lp{2.2cm}p{3.4cm}p{3.4cm}l", "Pair & Label & Codes (first) & Codes (second) & Kind", rows,
              "Lexical false friends (unordered pairs): argument names shared by two providers with disjoint codes.", "tab:s-ff")

def retrieval():
    R = pd.read_csv("data/retrieval_tie_aware.csv"); R = R[R.cue.isin(["name", "name_args", "role_description"])]
    g = R.groupby(["home", "target", "cue"]).agg(n=("rr", "size"), hit10=("hit10", "mean"), zero=("zero_overlap", "mean"), med=("rank_exp", "median"), N=("N", "first")).reset_index()
    rows = []
    for (h, t), q in g.groupby(["home", "target"]):
        q = q.set_index("cue")
        rows.append([f"{NAME[h]} $\\rightarrow$ {NAME[t]}", str(int(q.loc['name'].N)), str(int(q.loc['name'].n))] +
                    [f"{100 * q.loc[c].hit10:.1f}" for c in ["name", "name_args", "role_description"]] +
                    [f"{100 * q.loc['name'].zero:.1f}", f"{q.loc['name'].med:.0f}", f"{q.loc['name_args'].med:.0f}"])
    longtable("supp_retrieval", "lrrrrrrrr", "Pair & $N$ & $n$ & H@10 N & H@10 NA & H@10 R & Zero N & Med N & Med NA", rows,
              "Tie-aware retrieval by provider pair ($N$ = catalogue size; H@10 = expected hit@10, percent; N = type name, NA = name + arguments, R = role description; Zero = zero-overlap share; Med = median expected rank).", "tab:s-retrieval")

def variants():
    tags = {"primary": "Primary", "CB": "Coder B", "CC": "Coder C", "Arg": "Args only", "DecW": "Decision-wt", "ConB": "Concept-bal.", "Val": "+Value", "Any": "+Struct.", "Up": "Any judge"}
    T = {k: pd.read_csv("data/pair_indices.csv" if k == "primary" else f"data/pair_indices_variant_{k}.csv").set_index(["home", "target"]) for k in tags}
    rows = []
    for h in ac.PROVS:
        for t in ac.PROVS:
            if h != t:
                rows.append([f"{SH[h]} $\\rightarrow$ {SH[t]}"] + [f"{100 * T[k].loc[(h, t)].abstraction:.1f}" for k in tags])
    longtable("supp_variants", "l" + "r" * len(tags), "Pair & " + " & ".join(tags.values()), rows,
              "Role-overlap index (percent) by ordered pair under selected sensitivity variants.", "tab:s-variants")

def grader():
    V = pd.read_csv("data/grader_validation_mutants.csv")
    rows = [[NAME[r.provider], r.set.replace("_", " "), r.target, "\\texttt{" + esc(str(r.mutation)[:80]) + "}", esc(r.grader_fails), esc(r.tofu_fails)] for r in V.itertuples()]
    longtable("supp_grader", "llp{0.6cm}p{5.4cm}p{1.3cm}p{2.3cm}", "Provider & Set & Target & Fault & Grader fails & Conformance suite fails", rows,
              "Prototype grader validation on injected faults.", "tab:s-grader")
    S = pd.read_csv("data/grader_validation_syntax_faults.csv")
    rows = [[NAME[r.provider], "\\texttt{" + esc(r.block) + "}", f"{r.score:.2f}", esc(r.fails)] for r in S.itertuples()]
    longtable("supp_syntax", "lp{6.0cm}rp{3.8cm}", "Provider & Block with deleted closing brace & Score & Requirements lost", rows,
              "Fault tolerance: grader score with one block made syntactically invalid (\\texttt{tofu validate} rejects every such configuration).", "tab:s-syntax")

def holdout():
    H = pd.read_csv("data/grader_validation_holdout.csv")
    rows = [[NAME[r.provider], r.target, "\\texttt{" + esc(str(r.mutation)[:70]) + "}", esc(r.grader_fails), esc(r.tofu_fails), esc(r.grader_fails_after_fix), esc(r.tofu_fails_after_fix)] for r in H.itertuples()]
    longtable("supp_holdout", "llp{4.6cm}p{1.2cm}p{1.2cm}p{1.6cm}p{1.6cm}", "Provider & Target & Held-out fault & Grader & Suite & Grader after fix & Suite after fix", rows,
              "Held-out validation: faults written after the grader and suites were finalised, scored once before any change.", "tab:s-holdout")

def trial():
    G = pd.read_csv("data/trial_simulation_grid.csv")
    rows = [[str(int(r.J)), f"{r.rho:.2f}", f"{r.attrition:.2f}", f"{r.power_H1:.3f}", f"{r.power_H1_holm:.3f}", f"{r.power_H3_NI:.3f}", f"{r.power_H3_holm:.3f}",
             f"{r.power_H2:.3f}", f"{r.H2_slope_ci_halfwidth:.3f}", f"{r.power_H4:.3f}", f"{r.typeI_H1:.3f}", f"{r.typeI_H3:.3f}"] for r in G.itertuples()]
    longtable("supp_trial", "rrrrrrrrrrrr", "$J$ & ICC & Attr. & H1 & H1\\textsubscript{Holm} & H3 & H3\\textsubscript{Holm} & H2 & H2 hw & H4 & $\\alpha$ H1 & $\\alpha$ H3", rows,
              "Full simulation grid for the proposed trial (2,000 replications; type I 1,000).", "tab:s-trial")

if __name__ == "__main__":
    for f in [catalogue, mutations, semantic, implicit, falsefriends, retrieval, variants, grader, holdout, trial]:
        f(); print("ok", f.__name__)
