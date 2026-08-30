"""Post-hoc addenda (LABELLED) on the frozen panel — no new model calls.
  T6  human-benchmark formal test (machine per-comparison disagreement vs published
      agency split rates, two-proportion z + item-clustered bootstrap)
  ADD2 variance-component power analysis + bootstrap-subsampling validation
  ADD3 effective-resolution function R(tau) with item-bootstrap CIs
Writes 03_analysis/results_addenda.json. Reads ONLY panel.parquet + verified literature.
"""
from __future__ import annotations
import json, math, collections
from pathlib import Path
import numpy as np, pandas as pd

PB = Path(__file__).resolve().parents[1]
RS = json.load(open(PB / "data" / "frozen" / "main" / "rating_scale.json"))
P = pd.read_parquet(PB / "data" / "panel" / "panel.parquet")
P = P[P.provider.isin(["openai","google"])].copy()  # two-vendor design
L = P[P.parse_rule == "lenient"].copy()
CR = L[(L.family == "credit_health") & L.decision.notna()].copy()
rng = np.random.default_rng(42)
GMAP = {"letter": "dec_letter", "notch": "dec_notch", "band": "dec_band", "ig_hy": "dec_ighy"}

# ---- VERIFIED published human split rates, PAIRED LIKE-FOR-LIKE BY AGENCY SCALE ----
# Cantor, Packer & Cole / Livingston et al. (2010, JMCB): ~13% split at the AGENCY LETTER
# (broad alpha, AA vs A) level, ~50% at the AGENCY NOTCH (modifier, AA+ vs AA) level; N=13,853.
# CORRESPONDENCE with rating_scale.json coarsenings (this is the crux, verified):
#   agency NOTCH (modifier)  == our 'letter'  (21-grade AAA..C WITH +/-)         -> human 0.50
#   agency LETTER (broad)    == our 'notch'    (letter_to_notch_collapsed, 9 major grades, +/- stripped) -> human 0.13
# So machine 'letter' is tested vs 50% (not 13%); machine 'notch' vs 13%. band / ig_hy: no published rate.
HUMAN = {"letter": {"split": 0.50, "N": 13853, "agency_level": "notch/modifier (AA+ vs AA) = our 21-grade letter scale"},
         "notch":  {"split": 0.13, "N": 13853, "agency_level": "broad letter/alpha (AA vs A) = our notch-collapsed 9-grade scale"}}
HUMAN_SRC = ("Cantor, Packer & Cole; Livingston, Naranjo & Zhou (2010, J. Money Credit & Banking), "
             "N=13,853 issues; ~50% split at NOTCH (modifier) level, ~13% at LETTER (broad alpha) level. "
             "Paired like-for-like against our matching coarsenings.")


def per_item_disagreement(sub, col):
    """mean over items of P(two random draws for the item disagree at this granularity)."""
    vals = []
    for it, g in sub.groupby("item_id"):
        vc = g[col].value_counts(normalize=True)
        vals.append(1 - float((vc ** 2).sum()))
    return np.array(vals)


def fleiss_kappa(sub, col):
    cats = sorted(sub[col].dropna().unique()); cidx = {c: i for i, c in enumerate(cats)}; q = len(cats)
    Pi = []; colsum = np.zeros(q)
    for it, g in sub.groupby("item_id"):
        counts = np.zeros(q)
        for v in g[col].dropna():
            counts[cidx[v]] += 1
        n = counts.sum()
        if n < 2:
            continue
        Pi.append((np.sum(counts ** 2) - n) / (n * (n - 1))); colsum += counts
    Pbar = float(np.mean(Pi)); pj = colsum / colsum.sum(); Pe = float(np.sum(pj ** 2))
    return (Pbar - Pe) / (1 - Pe) if Pe < 1 else 0.0


# ================= T6 =================
def t6():
    from math import erf, sqrt
    def pnorm(z):  # one-sided upper tail
        return 0.5 * (1 - erf(z / sqrt(2)))
    items = CR.item_id.unique()
    rows = []
    for g, col in GMAP.items():
        di = per_item_disagreement(CR, col)
        m = float(di.mean())
        # naive comparison count (pairwise, per item) -> anti-conservative n
        ncomp = int(sum(int(round(n)) * (int(round(n)) - 1) / 2 for n in CR.groupby("item_id")[col].size()))
        entry = {"granularity": g, "machine_percomparison_disagree": round(m, 4),
                 "machine_pairwise_comparisons": ncomp}
        if g in HUMAN:
            h = HUMAN[g]["split"]; N = HUMAN[g]["N"]
            p = (m * ncomp + h * N) / (ncomp + N)
            se = math.sqrt(p * (1 - p) * (1 / ncomp + 1 / N))
            z = (m - h) / se if se > 0 else float("inf")
            # item-clustered bootstrap: resample items, recompute machine disagreement
            bs = []
            for _ in range(2000):
                samp = rng.choice(items, len(items), replace=True)
                bs.append(np.mean([di[list(items).index(it)] for it in samp]))
            bs = np.array(bs)
            ci = [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
            p_clust = float(np.mean(bs <= h))   # one-sided: P(machine disagreement <= human)
            entry.update({"human_split": h, "human_N": N, "agency_level": HUMAN[g]["agency_level"],
                          "z_naive": round(float(z), 2), "p_naive": ("<1e-6" if pnorm(z) < 1e-6 else round(pnorm(z), 6)),
                          "machine_95CI_clustered": ci, "p_dependence_adjusted": (("<0.0005" if p_clust == 0 else round(p_clust, 4))),
                          "conclusion": ("machine significantly MORE inconsistent than agencies"
                                         if ci[0] > h else "dependence-adjusted inconclusive")})
        else:
            entry["human_split"] = None; entry["note"] = "no verified published human rate at this granularity; not tested"
        rows.append(entry)
    return {"T6.rows": rows, "T6.human_source": HUMAN_SRC,
            "T6.caveat": ("Machine 'raters' are specifications; agency raters are two firms. The comparison "
                          "is calibration, not identity. Naive z uses the pairwise-comparison count and is "
                          "anti-conservative; the item-clustered bootstrap is the honest inference.")}


# ================= ADD2 power + subsample validation =================
def add2():
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm
    d0 = CR.dropna(subset=["dec_letter"]).copy(); d0["lr"] = d0.dec_letter.map({l: i for i, l in enumerate(RS["letter_scale"])})
    d0["A3_temperature"] = d0.A3_temperature.astype(str)
    form = ("lr ~ C(item_id)+C(A1_provider)+C(A2_version)+C(A3_temperature)+C(A4_paraphrase)"
            "+C(A5_format)+C(A6_fewshot)+C(A7_presentation)")
    def shares(dd):
        m = smf.ols(form, data=dd).fit(); a = anova_lm(m, typ=2); t = a["sum_sq"].sum()
        return {"residual": float(a["sum_sq"]["Residual"] / t * 100),
                "A7": float(a["sum_sq"]["C(A7_presentation)"] / t * 100),
                "item": float(a["sum_sq"]["C(item_id)"] / t * 100)}
    full = shares(d0)
    # bootstrap-subsampling validation: resample items at fractions, recompute shares
    items = list(CR.item_id.unique()); val = {}
    for frac in [0.25, 0.5, 0.75]:
        k = max(4, int(len(items) * frac)); res = collections.defaultdict(list)
        for _ in range(40):
            samp = rng.choice(items, k, replace=False)
            try:
                s = shares(d0[d0.item_id.isin(samp)])
                for kk, vv in s.items():
                    res[kk].append(vv)
            except Exception:
                pass
        val[f"frac_{frac}"] = {kk: [round(float(np.mean(vv)), 2), round(float(np.std(vv)), 2)] for kk, vv in res.items()}
    # variance-component power (rough): detectable axis variance-share at 80% power given residual share
    # For a 2-level axis, F-test power ~ noncentrality lambda = N_eff * (eta2/(1-eta2)); solve eta2 for lambda~7.85 (80% power, df1=1)
    n_eff = int(CR.groupby(["item_id"]).ngroups) * 3   # items x seeds effective replication
    lam = 7.85
    mde_eta2 = lam / (n_eff + lam)
    return {"ADD2.full_shares_pct": {k: round(v, 2) for k, v in full.items()},
            "ADD2.subsample_validation_mean_sd": val,
            "ADD2.min_detectable_axis_varshare_80pct_pct": round(mde_eta2 * 100, 2),
            "ADD2.assumptions": ("Power figure assumes an F-test for a single 2-level main effect, effective "
                "replication n=items*seeds, alpha=0.05, and treats residual+seed as the error term; it is an "
                "order-of-magnitude guide, not an exact design calc. Subsample validation resamples items "
                "(the clustering unit) at 25/50/75% and reports mean+/-sd of the key shares to show the "
                "decomposition is stable, not an artefact of the 45-item sample.")}


# ================= ADD3 R(tau) =================
def add3():
    order = ["letter", "notch", "band", "ig_hy"]
    kap = {g: fleiss_kappa(CR, GMAP[g]) for g in order}
    # item-bootstrap CIs on kappa per granularity
    items = CR.item_id.unique(); kci = {}
    boot = {g: [] for g in order}
    for _ in range(1000):
        samp = rng.choice(items, len(items), replace=True)
        sub = pd.concat([CR[CR.item_id == it] for it in samp])
        for g in order:
            boot[g].append(fleiss_kappa(sub, GMAP[g]))
    for g in order:
        kci[g] = [round(float(np.percentile(boot[g], 2.5)), 3), round(float(np.percentile(boot[g], 97.5)), 3)]
    def R(tau):
        for g in order:
            if kap[g] >= tau:
                return g
        return "none (coarser than IG/HY)"
    def R_ci(tau):   # bootstrap distribution of R(tau)
        c = collections.Counter()
        for i in range(1000):
            got = "none (coarser than IG/HY)"
            for g in order:
                if boot[g][i] >= tau:
                    got = g; break
            c[got] += 1
        return {k: round(v / 1000, 3) for k, v in c.most_common()}
    return {"ADD3.definition": ("Effective resolution R(tau) of a machine rating opinion = the FINEST scale "
                "granularity at which cross-specification agreement, chance-corrected by Fleiss' kappa, "
                "attains threshold tau. It is benchmark-free, reusable, and reported with item-bootstrap CIs."),
            "ADD3.kappa_by_granularity": {g: round(kap[g], 3) for g in order},
            "ADD3.kappa_95CI": kci,
            "ADD3.R_0.40": R(0.40), "ADD3.R_0.60": R(0.60), "ADD3.R_0.75": R(0.75),
            "ADD3.R_0.40_bootstrap_dist": R_ci(0.40), "ADD3.R_0.60_bootstrap_dist": R_ci(0.60)}


OUT = {"_label": "POST-HOC ADDENDA (labelled); frozen panel only; no new model calls.",
       "T6_human_benchmark": t6(), "ADD2_power_validation": add2(), "ADD3_effective_resolution": add3()}
(PB / "results" / "results_addenda.json").write_text(json.dumps(OUT, indent=1))
print("T6:")
for r in OUT["T6_human_benchmark"]["T6.rows"]:
    print(" ", r["granularity"], "machine", r["machine_percomparison_disagree"],
          "| human", r.get("human_split"), "| z", r.get("z_naive"), "| p_dep", r.get("p_dependence_adjusted"), "|", r.get("conclusion", r.get("note")))
print("ADD2 MDE axis varshare 80%:", OUT["ADD2_power_validation"]["ADD2.min_detectable_axis_varshare_80pct_pct"], "%")
print("ADD2 subsample validation:", OUT["ADD2_power_validation"]["ADD2.subsample_validation_mean_sd"]["frac_0.5"])
print("ADD3 kappa:", OUT["ADD3_effective_resolution"]["ADD3.kappa_by_granularity"])
print("ADD3 R(0.4)=", OUT["ADD3_effective_resolution"]["ADD3.R_0.40"], " R(0.6)=", OUT["ADD3_effective_resolution"]["ADD3.R_0.60"], " R(0.75)=", OUT["ADD3_effective_resolution"]["ADD3.R_0.75"])
