"""Generate manuscript LaTeX tables from data/. Run from the repository root:
python code/make_tables.py  -> tex/tab_*.tex"""
import os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_core as ac

NAME = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud", "openstack": "OpenStack"}
SH = {"aws": "AWS", "azure": "Az", "gcp": "GC", "openstack": "OS"}
CONCEPT = {"K01": "Virtual network", "K02": "Subnets and zones", "K03": "Internet routing", "K04": "Private egress (NAT)",
           "K05": "Traffic filtering", "K06": "Workload identity", "K07": "Object storage", "K08": "Compute template",
           "K09": "Elastic pool", "K10": "L7 load balancer", "K11": "Managed database", "K12": "CDN", "K13": "Metric alarm"}
pc = lambda v: "--" if pd.isna(v) else f"{100 * v:.1f}"
os.makedirs("tex", exist_ok=True)

def write(name, s):
    open(f"tex/{name}.tex", "w", encoding="utf-8").write(s)

def tab_concepts():
    d = pd.read_csv("data/coded_decisions.csv"); cat = pd.read_csv("data/slot_catalogue.csv")
    z = ac.explode(d.rename(columns={"codes_A": "codes"})); z["concept"] = z.code.map(lambda c: ac.PREFIX[c.split(".")[0]])
    rows = []
    for k in CONCEPT:
        r = [k, CONCEPT[k], str((cat.concept == k).sum())]
        r += [str(z[(z.provider == p) & (z.concept == k)].code.nunique() or "--") for p in ac.PROVS]
        r += [str(z[(z.provider == p) & (z.concept == k) & (z.path == "<type>")].rtype.nunique() or "--") for p in ac.PROVS]
        rows.append(" & ".join(r) + r" \\")
    tot = ["", "Total", str(len(cat))] + [str(z[z.provider == p].code.nunique()) for p in ac.PROVS] + \
          [str(z[(z.provider == p) & (z.path == "<type>")].rtype.nunique()) for p in ac.PROVS]
    s = r"""\begin{table}
\caption{Reference-architecture concepts, slot catalogue and realisation per provider.}
\label{tab:concepts}
\small
\begin{tabular}{llrrrrrrrrr}\toprule
 & & & \multicolumn{4}{c}{Slots realised} & \multicolumn{4}{c}{Types coded to the concept} \\ \cmidrule(lr){4-7}\cmidrule(lr){8-11}
ID & Concept & Catalogue & AWS & Az & GC & OS & AWS & Az & GC & OS \\ \midrule
""" + "\n".join(rows) + r"""
\midrule
""" + " & ".join(tot) + r""" \\
\bottomrule\end{tabular}
\begin{flushleft}\footnotesize Az = Azure; GC = Google Cloud; OS = OpenStack. A slot is a vendor-neutral configuration role (e.g., \textit{fw.priority}: evaluation priority of a filter rule); the catalogue was built inductively from the four implementations, so every slot is realised by at least one provider. Types count distinct resource and data-source types whose type choice was coded to a slot of the concept; totals count distinct types per provider and can be smaller than column sums because one type may realise several concepts. -- = not realised.\end{flushleft}
\end{table}
"""
    write("tab_concepts", s)

def tab_pairs():
    P = pd.read_csv("data/pair_indices.csv")
    V = {t: pd.read_csv(f"data/pair_indices_variant_{t}.csv").set_index(["home", "target"]) for t in ["Val", "Any", "Up"]}
    rows = []
    for h in ac.PROVS:
        for t in ac.PROVS:
            if h == t: continue
            r = P[(P.home == h) & (P.target == t)].iloc[0]
            cells = [f"{NAME[h]} $\\rightarrow$ {NAME[t]}", str(r.n_target_slots), str(r.I), str(r.R), str(r.F), str(r.Rd), str(r.N), str(r.D),
                     pc(r.surface), pc(1 - r.novel), pc(r.abstraction), pc(V["Val"].loc[(h, t)].abstraction), pc(V["Any"].loc[(h, t)].abstraction), pc(V["Up"].loc[(h, t)].abstraction)]
            rows.append(" & ".join(cells) + r" \\")
    m = lambda f, c: pc(f[c].mean())
    rows.append(r"\midrule")
    rows.append(" & ".join(["Mean of 12 pairs", "", "", "", "", "", "", "", m(P, "surface"), pc(1 - P.novel.mean()), m(P, "abstraction"),
                            pc(V["Val"].abstraction.mean()), pc(V["Any"].abstraction.mean()), pc(V["Up"].abstraction.mean())]) + r" \\")
    s = r"""\begin{table}
\caption{Correspondence categories and indices for all ordered provider pairs (percent of the target provider's slots).}
\label{tab:pairs}
\footnotesize
\setlength{\tabcolsep}{3.2pt}
\begin{tabular}{lrrrrrrrrrrrrr}\toprule
 & & \multicolumn{6}{c}{Slot counts} & & & \multicolumn{4}{c}{Role-overlap index by semantic criterion} \\ \cmidrule(lr){3-8}\cmidrule(lr){11-14}
Home $\rightarrow$ target & $|S_T|$ & I & R & F & R$_d$ & N & D & Label overlap & Corresp. & Doc. & +Value & +Struct. & Any judge \\ \midrule
""" + "\n".join(rows) + r"""
\bottomrule\end{tabular}
\begin{flushleft}\footnotesize Slot counts and the label-overlap and documented role-overlap indices use documented divergences only. I = identical label, R = renamed role, F = shared label with divergent meaning, R$_d$ = renamed and divergent, N = no home counterpart, D = home slot with no target counterpart (not in the denominator). Label overlap = I/$|S_T|$; Corresp.\ (correspondence share) = 1 $-$ N/$|S_T|$; role overlap = (I+R)/$|S_T|$. +Value adds consensus value-semantic divergences from two LLM judges; +Struct.\ adds all consensus divergences including composition differences; Any judge treats a slot pair as divergent unless both judges called it equivalent (upper bound on divergence). Pairs share implementations and are not independent observations; means are descriptive.\end{flushleft}
\end{table}
"""
    write("tab_pairs", s)

def tab_robust():
    V = pd.read_csv("data/robustness_variants.csv")
    rows = [" & ".join([r.variant.replace("&", "\\&"), pc(r.surface_mean), pc(r.abstraction_mean), pc(r.divergent_mean), pc(r.novel_mean),
                        f"{pc(r.surface_aws_min)}--{pc(r.surface_aws_max)}", f"{pc(r.abstraction_aws_min)}--{pc(r.abstraction_aws_max)}"]) + r" \\" for r in V.itertuples()]
    s = r"""\begin{table}
\caption{Sensitivity of the indices to coding, identity, weighting, granularity and semantic criteria (percent).}
\label{tab:robust}
\footnotesize
\begin{tabular}{lrrrrrr}\toprule
 & \multicolumn{4}{c}{Mean over 12 ordered pairs} & \multicolumn{2}{c}{Range over AWS $\rightarrow$ 3 targets} \\ \cmidrule(lr){2-5}\cmidrule(lr){6-7}
Variant & Label & Role & Divergent & Novel & Label & Role \\ \midrule
""" + "\n".join(rows) + r"""
\bottomrule\end{tabular}
\begin{flushleft}\footnotesize Primary: primary codes, a slot shared if any realising label is shared, documented divergences, each slot weighted equally. Each variant changes one choice; definitions in Section~\ref{sec:sensitivity}. Concept granularity collapses slots to the 13 concepts and ignores divergence. Implicit realisation reclassifies target slots that the home provider realises by default or by composition from novel to divergent.\end{flushleft}
\end{table}
"""
    write("tab_robust", s)

def tab_retrieval():
    S = pd.read_csv("data/retrieval_summary.csv", index_col=0)
    RR = pd.read_csv("data/retrieval_tie_aware.csv"); ch1 = RR[RR.cue == "name"].chance_hit1.mean()
    lab = [("name", "Type name"), ("name_stem", "Type name, stemmed"), ("name_char", "Type name, character 3--5-grams"),
           ("name_args", "Type name + argument names"), ("name_args_desc", "Type name + argument names + schema descriptions"),
           ("role_description", "Vendor-neutral role description (query) vs.\\ type name + arguments")]
    rows = []
    for c, l in lab:
        r = S.loc[c]
        rows.append(" & ".join([l, str(int(r.n)), pc(r.hit1), pc(r.hit10), f"{r.mrr:.2f}", f"{r.med_rank:.0f}", pc(r.pct_rank), pc(r.zero), pc(r.recall10)]) + r" \\")
    s = r"""\begin{table}
\caption{Tie-aware lexical retrieval of counterpart resource types from complete target catalogues.}
\label{tab:retrieval}
\footnotesize
\begin{tabular}{p{5.2cm}rrrrrrrr}\toprule
Cue & $n$ & Hit@1 & Hit@10 & MRR & Median rank & Median pct. & Zero overlap & Recall@10 \\ \midrule
""" + "\n".join(rows) + r"""
\midrule
Random ranking (expected) & """ + str(int(S.loc["name"].n)) + " & " + pc(ch1) + " & " + pc(S.loc["name"].chance_hit10) + r""" & & & 50.0 & & \\
\bottomrule\end{tabular}
\begin{flushleft}\footnotesize Hit@$k$, mean reciprocal rank (MRR) and ranks are expectations under uniformly random ordering of tied scores \citep{mcsherry2008computing}; Hit@$k$ and MRR are percent and proportion respectively. Median pct.\ = median expected rank divided by catalogue size (percent). Zero overlap = query shares no weighted token with any true counterpart, so its rank is undetermined. Recall@10 counts all counterparts of the query. Catalogue sizes: AWS 1,746; Azure 1,107; Google Cloud 1,396; OpenStack 108 resource types.\end{flushleft}
\end{table}
"""
    write("tab_retrieval", s)

def tab_agreement():
    A = pd.read_csv("data/agreement.csv", index_col=0)
    lab = {"AB": "A (primary) vs.\\ B", "AC": "A (primary) vs.\\ C", "BC": "B vs.\\ C"}
    rows = [" & ".join([lab[k], str(int(r.n)), pc(r.primary_agree), f"{r.kappa_primary:.3f}", f"{r.kappa_class:.3f}", f"{r.kappa_concept:.3f}",
                        pc(r.set_exact), f"{r.jaccard:.3f}", f"{r.alpha_masi:.3f}", str(int(r.primary_mismatch)), str(int(r.set_disagree))]) + r" \\" for k, r in A.iterrows()]
    s = r"""\begin{table}
\caption{Agreement between the primary coding (A) and two blinded model coders (B, C) on coding units.}
\label{tab:agreement}
\footnotesize
\setlength{\tabcolsep}{3.5pt}
\begin{tabular}{lrrrrrrrrrr}\toprule
Pair & $n$ & Primary agr. & $\kappa$ primary & $\kappa$ class & $\kappa$ concept & Exact set & Jaccard & $\alpha_{\mathrm{MASI}}$ & Primary diff. & Set diff. \\ \midrule
""" + "\n".join(rows) + r"""
\bottomrule\end{tabular}
\begin{flushleft}\footnotesize B = \texttt{claude-sonnet-5}; C = \texttt{claude-sonnet-4-5-20250929}; both blinded to codes and HCL comments, thinking disabled. $\kappa$ class: slot vs.\ WIRE vs.\ SCAF vs.\ META. $\kappa$ concept: concept of the primary code, with WIRE, SCAF and META as separate categories. $\alpha_{\mathrm{MASI}}$: Krippendorff's $\alpha$ with the MASI set distance \citep{passonneau2006measuring}. Primary diff.\ = units whose first-listed codes differ; Set diff.\ = units whose code sets are not identical. C left one block (2 units) uncoded after three rounds.\end{flushleft}
\end{table}
"""
    write("tab_agreement", s)

def tab_trial():
    G = pd.read_csv("data/trial_simulation_grid.csv"); G = G[G.attrition == 0.20]
    rows = []
    for J in [28, 40, 56]:
        for rho in [0.05, 0.10, 0.15, 0.20]:
            r = G[(G.J == J) & (np.isclose(G.rho, rho))].iloc[0]
            rows.append(" & ".join([str(J), f"{rho:.2f}", f"{r.power_H1_holm:.2f}", f"{r.power_H3_holm:.2f}", f"{r.H2_slope_ci_halfwidth:.2f}",
                                    f"{r.power_H4:.2f}", f"{r.typeI_H1:.3f}", f"{r.typeI_H3:.3f}"]) + r" \\")
        if J != 56: rows.append(r"\addlinespace")
    s = r"""\begin{table}
\caption{Simulated operating characteristics of the proposed trial (2,000 replications per cell; attrition 20\%).}
\label{tab:trial}
\footnotesize
\begin{tabular}{rrrrrrrr}\toprule
Sections $J$ & ICC & H1 power (Holm) & H3 power (Holm) & H2 slope 95\% CI half-width & H4 power & H1 type I & H3 type I \\ \midrule
""" + "\n".join(rows) + r"""
\bottomrule\end{tabular}
\begin{flushleft}\footnotesize H1: d = 0.30 on the transfer score; H3: true AWS-rubric difference 0, non-inferiority margin $-$0.20 SD; type I: H1 at d = 0, H3 at a true difference of $-$0.20 SD (1,000 replications). H2: concept-level slope of 0.5 SD per unit audit gap, concept--provider combinations as units ($K-2$ df). H4: false-friend error odds ratio 0.70, baseline 40\%, seven opportunities per student. Design: four strata, arm $\times$ provider allocation in permuted blocks, mean section size 25 (CV 0.3), consent 85\%. Monte Carlo SE $\leq$ 0.011 for power and $\leq$ 0.007 for type I.\end{flushleft}
\end{table}
"""
    write("tab_trial", s)

if __name__ == "__main__":
    for f in [tab_concepts, tab_pairs, tab_robust, tab_retrieval, tab_agreement, tab_trial]:
        f(); print("ok", f.__name__)
