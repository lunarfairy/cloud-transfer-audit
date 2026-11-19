"""Generate all manuscript figures from data/. Run from the repository root:
python code/make_figures.py   -> fig/fig1_decomposition.pdf ... fig6_trial_power.pdf (+ .png)"""
import os, sys
from math import comb
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_core as ac

plt.rcParams.update({"axes.labelsize": 8, "axes.linewidth": 0.6, "axes.spines.right": False, "axes.spines.top": False,
                     "axes.titlelocation": "left", "axes.titlesize": 8, "font.size": 8, "legend.fontsize": 7, "legend.frameon": False,
                     "lines.linewidth": 1.2, "patch.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.bbox": "tight",
                     "savefig.dpi": 300, "xtick.labelsize": 6, "ytick.labelsize": 6, "xtick.major.size": 3, "ytick.major.size": 3,
                     "xtick.major.width": 0.6, "ytick.major.width": 0.6, "font.family": "sans-serif"})
NAME = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud", "openstack": "OpenStack"}
COL = {"I": "#1f4e79", "R": "#8fb8de", "Div": "#e08b2c", "N": "#bdbdbd"}
CONCEPT = {"K01": "Virtual network", "K02": "Subnets and zones", "K03": "Internet routing", "K04": "Private egress (NAT)",
           "K05": "Traffic filtering", "K06": "Workload identity", "K07": "Object storage", "K08": "Compute template",
           "K09": "Elastic pool", "K10": "L7 load balancer", "K11": "Managed database", "K12": "CDN", "K13": "Metric alarm"}
W = 6.3
os.makedirs("fig", exist_ok=True)

def letter(ax, s, x=-0.02, y=1.04):
    ax.text(x, y, s, transform=ax.transAxes, fontsize=9, fontweight="bold", ha="right", va="bottom")

def save(fig, name):
    fig.savefig(f"fig/{name}.pdf"); fig.savefig(f"fig/{name}.png", dpi=300); plt.close(fig)

def fig1():
    P = pd.read_csv("data/pair_indices.csv")
    order = [(h, t) for h in ac.PROVS for t in ac.PROVS if h != t]
    P = P.set_index(["home", "target"]).loc[order].reset_index()
    tags = [("primary", "Documented divergence only", "o", "#1f4e79"), ("Val", "+ consensus value divergence", "D", "#4d8ac0"),
            ("Any", "+ consensus structural divergence", "s", "#8fb8de"), ("Up", "Any judge non-equivalent", "v", "#6b6b6b")]
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 3.3), gridspec_kw=dict(width_ratios=[1.35, 1], wspace=0.16), sharey=True)
    y = np.arange(len(P))[::-1]
    left = np.zeros(len(P))
    for c, lab in [("I", "Identical label"), ("R", "Renamed role"), ("Div", "Shared role, divergent meaning"), ("N", "No home counterpart")]:
        v = (P.I if c == "I" else P.R if c == "R" else (P.F + P.Rd) if c == "Div" else P.N) / P.n_target_slots
        a.barh(y, v, left=left, color=COL[c], height=0.72, label=lab, edgecolor="white", linewidth=0.4)
        left += v
    a.set_yticks(y); a.set_yticklabels([f"{NAME[h]} \u2192 {NAME[t]}" for h, t in order])
    a.set_xlim(0, 1); a.set_xlabel("Share of target provider's slots"); a.set_xticks([0, .25, .5, .75, 1]); a.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
    for yy, n in zip(y, P.n_target_slots): a.text(1.012, yy, str(n), va="center", ha="left", fontsize=6, color="#555555")
    a.set_title("Label identity is rare")
    a.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.13), handlelength=1.2, columnspacing=1.0)
    for tag, lab, m, colr in tags:
        f = "data/pair_indices.csv" if tag == "primary" else f"data/pair_indices_variant_{tag}.csv"
        Q = pd.read_csv(f).set_index(["home", "target"]).loc[order].reset_index()
        b.scatter(Q.abstraction, y, marker=m, s=16, color=colr, label=lab, zorder=3, edgecolor="white", linewidth=0.3)
    Qs = [pd.read_csv("data/pair_indices.csv" if t == "primary" else f"data/pair_indices_variant_{t}.csv").set_index(["home", "target"]).loc[order].abstraction.values for t, *_ in tags]
    for i, yy in enumerate(y): b.plot([min(q[i] for q in Qs), max(q[i] for q in Qs)], [yy, yy], color="#cccccc", lw=0.8, zorder=1)
    b.set_xlim(0, 0.8); b.set_xlabel("Role-overlap index"); b.set_xticks([0, .2, .4, .6, .8]); b.set_xticklabels(["0", "20%", "40%", "60%", "80%"])
    b.set_title("Role overlap by semantic criterion")
    b.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=1, handletextpad=0.3)
    letter(a, "a", x=-0.36); letter(b, "b")
    save(fig, "fig2_composition")

def fig2():
    C = pd.read_csv("data/concept_profile_from_aws.csv", index_col=0).sort_values("abstraction")
    fig, ax = plt.subplots(figsize=(W * 0.72, 3.0))
    y = np.arange(len(C))
    for i, (k, r) in enumerate(C.iterrows()):
        ax.plot([r.surface, r.abstraction], [i, i], color="#cccccc", lw=0.8, zorder=1)
    ax.scatter(C.surface, y, s=18, color=COL["I"], label="Label overlap", zorder=3)
    ax.scatter(C.abstraction, y, s=18, facecolor="white", edgecolor=COL["I"], label="Role overlap (documented divergence)", zorder=3)
    ax.scatter(C.abstraction_val, y, s=16, marker="D", color="#4d8ac0", label="Role overlap (+ consensus value divergence)", zorder=3)
    ax.scatter(C.abstraction_any, y, s=16, marker="s", color="#8fb8de", label="Role overlap (+ consensus structural divergence)", zorder=3)
    ax.set_yticks(y); ax.set_yticklabels([f"{CONCEPT[k]} ({k})" for k in C.index])
    for i, n in enumerate(C.n): ax.text(1.02, i, f"n={int(n)}", va="center", fontsize=6, color="#555555", transform=ax.get_yaxis_transform())
    ax.set_xlim(-0.02, 1.0); ax.set_xticks([0, .25, .5, .75, 1]); ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Share of target slots, pooled over AWS \u2192 Azure, Google Cloud, OpenStack")
    ax.set_title("Concepts differ in how much a role-level encoding adds over names")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.16), ncol=2, handletextpad=0.3, columnspacing=0.8)
    save(fig, "fig3_concept_profile")

def fig3():
    d = pd.read_csv("data/coded_decisions.csv"); z = ac.explode(d.rename(columns={"codes_A": "codes"}))
    z["concept"] = z.code.map(lambda c: ac.PREFIX[c.split(".")[0]])
    types = z[z.path == "<type>"].groupby(["concept", "provider"]).rtype.nunique().unstack().reindex(index=list(CONCEPT), columns=ac.PROVS)
    decs = z.drop_duplicates(["provider", "rtype", "rname", "path", "concept"]).groupby(["concept", "provider"]).size().unstack().reindex(index=list(CONCEPT), columns=ac.PROVS)
    fig, axs = plt.subplots(1, 2, figsize=(W, 3.4), gridspec_kw=dict(wspace=0.06), sharey=True)
    for ax, M, title, vmax in [(axs[0], types, "Resource and data-source types per concept", 6), (axs[1], decs, "Configured decisions coded to the concept's slots", 40)]:
        A = M.values.astype(float)
        ax.imshow(np.nan_to_num(A, nan=0), cmap="Blues", vmin=0, vmax=vmax, aspect="auto")
        for i in range(A.shape[0]):
            for j in range(A.shape[1]):
                v = A[i, j]
                ax.text(j, i, "\u2013" if np.isnan(v) else f"{int(v)}", ha="center", va="center", fontsize=6,
                        color="white" if (not np.isnan(v) and v > 0.6 * vmax) else "black")
        ax.set_xticks(range(4)); ax.set_xticklabels([NAME[p] for p in ac.PROVS]); ax.set_title(title)
        ax.tick_params(length=0)
        for s in ax.spines.values(): s.set_visible(False)
    axs[0].set_yticks(range(13)); axs[0].set_yticklabels([f"{CONCEPT[k]} ({k})" for k in CONCEPT])
    letter(axs[0], "a", x=-0.02); letter(axs[1], "b", x=-0.02)
    save(fig, "fig1_decomposition")

def hit_curve(R, ks):
    out = []
    for k in ks:
        p = []
        for r in R.itertuples():
            g, e = r.rank_opt - 1, r.tied_block
            rr = g + e + 1 - r.rank_pess
            if k <= g: p.append(0.0)
            elif k >= g + e - rr + 1: p.append(1.0)
            else: p.append(1 - comb(e - (k - g), rr) / comb(e, rr))
        out.append(np.mean(p))
    return np.array(out)

def fig4():
    R = pd.read_csv("data/retrieval_tie_aware.csv")
    ks = np.unique(np.round(np.logspace(0, 3, 40)).astype(int))
    cues = [("name", "Type name", "#1f4e79", "-"), ("name_char", "Type name, character n-grams", "#4d8ac0", "--"),
            ("name_args", "Type name + argument names", "#8fb8de", "-"), ("role_description", "Vendor-neutral role description", "#e08b2c", "-")]
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 3.0), gridspec_kw=dict(width_ratios=[1.5, 1], wspace=0.95))
    for cue, lab, colr, ls in cues:
        a.plot(ks, hit_curve(R[R.cue == cue], ks), color=colr, ls=ls, label=lab)
    q = R[R.cue == "name"]
    ch = [np.mean([1.0 if k >= r.N else 1 - comb(r.N - r.n_rel, k) / comb(r.N, k) for r in q.itertuples()]) for k in ks]
    a.plot(ks, ch, color="#999999", ls=":", label="Random ranking")
    a.set_xscale("log"); a.set_xticks([1, 10, 100, 1000]); a.set_xticklabels(["1", "10", "100", "1k"])
    a.set_xlabel("Cut-off k (rank in the target catalogue)"); a.set_ylabel("Queries with a counterpart in top k")
    a.set_ylim(0, 1); a.set_title("Names rarely retrieve the counterpart")
    a.legend(loc="upper center", bbox_to_anchor=(0.6, -0.25), ncol=2, handlelength=1.8)
    S = R.groupby("cue").zero_overlap.mean().reindex([c for c, *_ in cues])
    b.barh(range(len(S))[::-1], S.values, color=[c for _, _, c, _ in cues], height=0.6)
    for i, v in zip(range(len(S))[::-1], S.values): b.text(v + 0.01, i, f"{100 * v:.0f}%", va="center", fontsize=6)
    b.set_yticks(range(len(S))[::-1]); b.set_yticklabels(["Type name", "Type name,\ncharacter n-grams", "Type name +\nargument names", "Vendor-neutral\nrole description"])
    b.set_xlim(0, 0.8); b.set_xticks([0, .25, .5, .75]); b.set_xticklabels(["0", "25%", "50%", "75%"])
    b.set_xlabel("Share of queries"); b.set_title("No token shared with any counterpart")
    letter(a, "a"); letter(b, "b", x=-0.55)
    save(fig, "fig4_retrieval")

def fig5():
    V = pd.read_csv("data/robustness_variants.csv")
    V["variant"] = V.variant.replace({"primary": "primary (any shared label, documented divergence, slot-weighted)"})
    V = V.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(W * 0.75, 3.1))
    y = np.arange(len(V))
    ax.scatter(V.surface_mean, y, color=COL["I"], s=16, label="Label-overlap index (mean of 12 pairs)", zorder=3)
    ax.scatter(V.abstraction_mean, y, facecolor="white", edgecolor=COL["I"], s=18, label="Role-overlap index (mean of 12 pairs)", zorder=3)
    for i, r in V.iterrows(): ax.plot([r.surface_mean, r.abstraction_mean], [i, i], color="#dddddd", lw=0.8, zorder=1)
    pr = V.index[V.variant.str.startswith("primary")][0]
    ax.axhspan(pr - 0.45, pr + 0.45, color="#f2f2f2", zorder=0)
    ax.set_yticks(y); ax.set_yticklabels(V.variant)
    ax.set_xlim(0, 1); ax.set_xticks([0, .25, .5, .75, 1]); ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.set_title("Label overlap stays low under every variant; role overlap is criterion-dependent")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.08), ncol=2)
    ax.set_xlabel("")
    save(fig, "fig5_robustness")

def fig6():
    G = pd.read_csv("data/trial_simulation_grid.csv"); G = G[G.attrition == 0.20]
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.4), sharey=True, gridspec_kw=dict(wspace=0.08))
    cols = {28: "#bdbdbd", 40: "#8fb8de", 56: "#1f4e79"}
    for J in [28, 40, 56]:
        q = G[G.J == J].sort_values("rho")
        a.plot(q.rho, q.power_H1_holm, marker="o", ms=3, color=cols[J], label=f"J = {J} sections")
        b.plot(q.rho, q.power_H3_holm, marker="o", ms=3, color=cols[J], label=f"J = {J} sections")
    for ax, t in [(a, "H1 superiority, d = 0.30 (Holm)"), (b, "H3 non-inferiority, margin \u22120.20 SD (Holm)")]:
        ax.axhline(0.8, color="#999999", ls=":", lw=0.8); ax.set_xticks([.05, .10, .15, .20]); ax.set_xlabel("Intraclass correlation")
        ax.set_ylim(0, 1); ax.set_title(t)
    a.set_ylabel("Simulated power"); a.legend(loc="lower left")
    letter(a, "a"); letter(b, "b")
    save(fig, "fig6_trial_power")

if __name__ == "__main__":
    for f in [fig1, fig2, fig3, fig4, fig5, fig6]:
        f(); print("ok", f.__name__)
