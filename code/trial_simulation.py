"""Design simulation for the proposed cluster-randomised trial.
Design: J sections randomised within S = 4 strata (campus x time slot) to the four cells arm (AF/CF) x held-out provider (Azure/GCP),
in permuted blocks; variable section sizes (CV 0.3); student opt-in consent obtained before allocation; post-consent attrition.
Analyses mirror the protocol: H1 section-level ANCOVA (stratum, provider, section-mean pretest; df = J - 2 - 3 - 1 - 1);
H3 one-sided non-inferiority on the AWS rubric at margin -0.20 SD; Holm over {H1, H3};
H2 secondary: concept-level differences regressed on audit gap (K - 2 df, concepts as units, section-clustered noise);
H4 secondary: section-level analysis of false-friend error proportions over O pre-specified opportunities.
Usage: python code/trial_simulation.py  (from the repository root)."""
import json, sys
import numpy as np
import pandas as pd
from scipy import stats

SEED = 20261111

def allocate(rng, J, S=4):
    strata = np.repeat(np.arange(S), int(np.ceil(J / S)))[:J]
    arm, prov = np.zeros(J, int), np.zeros(J, int)
    for s in range(S):
        idx = np.where(strata == s)[0]
        cells = np.tile([(0, 0), (0, 1), (1, 0), (1, 1)], (int(np.ceil(len(idx) / 4)), 1))[:len(idx)]
        cells = cells[rng.permutation(len(idx))]
        arm[idx], prov[idx] = cells[:, 0], cells[:, 1]
    return strata, arm, prov

def section_data(rng, J, nbar, rho, R2, attr, consent=0.85, cv=0.3):
    size = np.maximum(8, np.round(rng.gamma(1 / cv**2, nbar * cv**2, J))).astype(int)
    n_obs = rng.binomial(rng.binomial(size, consent), 1 - attr)
    n_obs = np.maximum(n_obs, 2)
    return size, n_obs

def ols_p(y, X, j, one_sided_lower=None):
    b, res, rk, sv = np.linalg.lstsq(X, y, rcond=None)
    df = len(y) - X.shape[1]
    s2 = ((y - X @ b) ** 2).sum() / df
    se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[j, j])
    if one_sided_lower is None:
        return 2 * stats.t.sf(abs(b[j] / se), df), b[j], se, df
    return stats.t.sf((b[j] - one_sided_lower) / se, df), b[j], se, df

def simulate(J, rho, d, d3, attr, reps, rng, nbar=25, R2=0.3, gaps=None, slope=0.5, sd_v=0.10, ff=(0.40, 0.70), O=7):
    out = dict(h1=0, h3=0, holm_h1=0, holm_h3=0, h2=0, h4=0, h2_ci=[], d_hat=[])
    K = len(gaps); g = gaps - gaps.mean()
    for _ in range(reps):
        strata, arm, prov = allocate(rng, J)
        size, n = section_data(rng, J, nbar, rho, R2, attr)
        S = 4
        D = np.column_stack([np.ones(J), arm, prov] + [(strata == s).astype(float) for s in range(1, S)])
        # section-level pretest mean and outcome mean (standardised student-level units)
        pre = rng.normal(0, np.sqrt(rho) , J) + rng.normal(0, np.sqrt((1 - rho) / n))
        beta_pre = np.sqrt(R2)
        u = rng.normal(0, np.sqrt(rho * (1 - R2)), J)
        e = rng.normal(0, np.sqrt((1 - rho) * (1 - R2) / n))
        prov_eff, strat_eff = 0.1, rng.normal(0, 0.1, S)[strata]
        y = beta_pre * pre + u + e + d * arm + prov_eff * prov + strat_eff
        X = np.column_stack([D, pre])
        p1, bh, se1, df1 = ols_p(y, X, 1)
        out["d_hat"].append(bh)
        # H3: AWS rubric, true difference d3, NI margin -0.20, one-sided alpha .05
        u3 = rng.normal(0, np.sqrt(rho * (1 - R2)), J); e3 = rng.normal(0, np.sqrt((1 - rho) * (1 - R2) / n))
        y3 = beta_pre * pre + u3 + e3 + d3 * arm + strat_eff
        p3, b3, se3, _ = ols_p(y3, X, 1, one_sided_lower=-0.20)
        out["h1"] += p1 < 0.05; out["h3"] += p3 < 0.05
        ps = sorted([(p1, "h1"), (p3, "h3")])
        if ps[0][0] < 0.025:
            out["holm_" + ps[0][1]] += 1
            if ps[1][0] < 0.05: out["holm_" + ps[1][1]] += 1
        # H2: concept subscores, section-correlated, concepts as units
        c = rng.normal(0, 0.3, K); v = rng.normal(0, sd_v, K)
        M = 0.8 * (u + e)[:, None] + c[None, :] \
            + arm[:, None] * (d + slope * g + v)[None, :] + rng.normal(0, 1, (J, K)) / np.sqrt(n)[:, None]
        diff = M[arm == 1].mean(0) - M[arm == 0].mean(0)
        lr = stats.linregress(g, diff)
        out["h2"] += lr.pvalue < 0.05
        out["h2_ci"].append(2 * stats.t.ppf(0.975, K - 2) * lr.stderr)
        # H4: false-friend error proportion over O opportunities, logit-normal section effects
        lo = np.log(ff[0] / (1 - ff[0])) + rng.normal(0, np.sqrt(rho) * 1.8, J) + np.log(ff[1]) * arm
        k = rng.binomial(n * O, 1 / (1 + np.exp(-lo)))
        prop = np.arcsin(np.sqrt(k / (n * O)))
        p4, *_ = ols_p(prop, D, 1)
        out["h4"] += p4 < 0.05
    r = {k: (v / reps if not isinstance(v, list) else None) for k, v in out.items()}
    r["h2_ci_halfwidth"] = float(np.median(out["h2_ci"]) / 2)
    r["d_hat_sd"] = float(np.std(out["d_hat"]))
    return r

def main(reps=2000):
    rng = np.random.default_rng(SEED)
    ci = pd.read_csv("data/concept_indices_from_aws.csv")
    gaps = {}
    for t in ["azure", "gcp"]:
        q = ci[ci.target == t].dropna(subset=["abstraction"])
        gaps[t] = (q.abstraction - q.surface).values
    G = np.r_[gaps["azure"], gaps["gcp"]]
    rows = []
    for J in [28, 40, 56]:
        for rho in [0.05, 0.10, 0.15, 0.20]:
            for attr in [0.10, 0.20]:
                pw = simulate(J, rho, 0.30, 0.0, attr, reps, rng, gaps=G)
                t1 = simulate(J, rho, 0.0, -0.20, attr, reps // 2, rng, gaps=G)
                rows.append(dict(J=J, rho=rho, attrition=attr, power_H1=pw["h1"], power_H1_holm=pw["holm_h1"],
                                 power_H3_NI=pw["h3"], power_H3_holm=pw["holm_h3"], power_H2=pw["h2"],
                                 H2_slope_ci_halfwidth=pw["h2_ci_halfwidth"], power_H4=pw["h4"],
                                 typeI_H1=t1["h1"], typeI_H3=t1["h3"], sd_d_hat=pw["d_hat_sd"]))
                print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv("data/trial_simulation_grid.csv", index=False)
    # J-selection rule: smallest J in {28,40,56} with Holm-adjusted H1 power >= .80 at the pilot ICC (attrition .20)
    rule = {f"{rho}": int(df[(df.rho == rho) & (df.attrition == 0.20) & (df.power_H1_holm >= 0.80)].J.min())
            if ((df.rho == rho) & (df.attrition == 0.20) & (df.power_H1_holm >= 0.80)).any() else None for rho in [0.05, 0.10, 0.15, 0.20]}
    json.dump(rule, open("data/trial_J_rule.json", "w"), indent=1)
    print(rule)

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2000)
