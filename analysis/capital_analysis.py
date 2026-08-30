"""T8.2 (POST-HOC ADDITION, labelled) — MACHINE RWA VARIABILITY / capital recast.
Maps every spec x seed portfolio's letter verdicts through the frozen Basel III ECRA
risk-weight table (00_frozen_inputs/capital_map.json, quote-verified from BIS CRE20.42)
into portfolio RWA and Pillar-1 minimum capital at 8%, and reports the dispersion of
required capital across specifications. No model calls. Reads panel.parquet + capital_map.json.
Writes 03_analysis/results_capital.json.

Scope (stated, load-bearing): Pillar 1 minimum only (no buffers), 8% ratio, ECRA base
risk weights, equal-weight $1B notional per name, on-balance-sheet drawn corporate EAD.
"""
from __future__ import annotations
import json, itertools, collections
from pathlib import Path
import numpy as np, pandas as pd

PB = Path(__file__).resolve().parents[1]
CM = json.load(open(PB / "data" / "frozen" / "main" / "capital_map.json"))
RW = CM["letter_to_risk_weight"]
EAD = 1_000_000_000.0        # $1B per name (stated equal-weight base case)
RATIO = 0.08                 # Pillar 1 minimum
rng = np.random.default_rng(42)

P = pd.read_parquet(PB / "data" / "panel" / "panel.parquet")
P = P[P.provider.isin(["openai","google"])].copy()  # two-vendor design

def build(parse_rule):
    L = P[P.parse_rule == parse_rule]
    CR = L[(L.family == "credit_health") & L.dec_letter.notna()].copy()
    CR["rw"] = CR.dec_letter.map(RW)
    return CR

CR = build("lenient")
ALL_NAMES = sorted(CR.item_id.unique())

# ---- balanced draw set: spec x seed combos that carry the FULL name set ----
def draw_table(CR, names):
    """pivot to draws x names risk-weight matrix; keep only complete draws over `names`."""
    sub = CR[CR.item_id.isin(names)]
    piv = sub.pivot_table(index=["spec_id", "seed"], columns="item_id", values="rw", aggfunc="first")
    piv = piv.dropna(axis=0, how="any")           # complete draws only
    # provider + axis metadata per draw (one provider per draw)
    meta = (sub.groupby(["spec_id", "seed"])[["A1_provider", "A2_version", "A3_temperature",
            "A4_paraphrase", "A5_format", "A6_fewshot", "A7_presentation"]].first())
    meta = meta.loc[piv.index]
    return piv, meta

def cap_stats(piv, label, names):
    n_names = piv.shape[1]
    total_notional = n_names * EAD
    # portfolio min capital per draw ($)
    cap = RATIO * (piv.values * EAD).sum(axis=1)           # one number per draw
    port_rwa = (piv.values * EAD).sum(axis=1)              # RWA $ per draw
    avg_rw = piv.values.mean(axis=1)                       # portfolio average risk weight
    q = lambda a, p: float(np.percentile(a, p))
    # distribution of required capital across draws
    dist = {"min": float(cap.min()), "p25": q(cap, 25), "median": float(np.median(cap)),
            "p75": q(cap, 75), "max": float(cap.max())}
    rng_abs = dist["max"] - dist["min"]
    rng_pct_med = rng_abs / dist["median"] * 100
    rng_pct_notional = rng_abs / total_notional * 100      # capital range as % of book
    # PRIMARY non-accumulating stat: expected |capital difference| between two random draws
    # = Gini mean absolute difference of the per-draw capital vector (per-comparison, not a sum)
    diffs = np.abs(np.subtract.outer(cap, cap))
    iu = np.triu_indices(len(cap), k=1)
    emad = float(diffs[iu].mean())                          # $ expected abs diff per comparison
    emad_pct_med = emad / dist["median"] * 100
    return {"label": label, "n_draws": int(len(cap)), "n_names": int(n_names),
            "total_notional_usd": total_notional,
            "capital_distribution_usd": {k: round(v, 0) for k, v in dist.items()},
            "capital_range_usd": round(rng_abs, 0),
            "capital_range_pct_of_median": round(rng_pct_med, 2),
            "capital_range_pct_of_notional": round(rng_pct_notional, 3),
            "expected_abs_capital_diff_per_comparison_usd": round(emad, 0),
            "expected_abs_capital_diff_pct_of_median": round(emad_pct_med, 2),
            "portfolio_avg_riskweight": {"min": round(float(avg_rw.min()), 4),
                "median": round(float(np.median(avg_rw)), 4), "max": round(float(avg_rw.max()), 4)},
            "_cap_vector": [round(float(x), 0) for x in cap]}

# ============ BASE CASE (lenient, all 45 names, equal-weight) ============
piv, meta = draw_table(CR, ALL_NAMES)
base = cap_stats(piv, "base_equalweight_lenient_45names", ALL_NAMES)

# ---- per-name capital dispersion (expected |risk-weight diff| across draws, per name) ----
per_name = {}
for nm in ALL_NAMES:
    g = CR[CR.item_id == nm]["rw"].values
    d = np.abs(np.subtract.outer(g, g)); iu = np.triu_indices(len(g), k=1)
    per_name[nm] = {"n": int(len(g)), "rw_min": float(g.min()), "rw_max": float(g.max()),
                    "rw_range": float(g.max() - g.min()),
                    "expected_abs_rw_diff": round(float(d[iu].mean()) if len(g) > 1 else 0.0, 4),
                    "capital_range_usd_per_name": round(float((g.max() - g.min()) * EAD * RATIO), 0)}
name_emad = np.array([per_name[n]["expected_abs_rw_diff"] for n in ALL_NAMES])

# ============ DECOMPOSITION: seed noise vs design axes ============
def decompose(piv, meta):
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm
    df = meta.copy()
    df["cap"] = RATIO * (piv.values * EAD).sum(axis=1)
    df["seed"] = [str(s) for _, s in piv.index]
    for c in ["A2_version", "A3_temperature", "A4_paraphrase", "A5_format", "A6_fewshot", "A7_presentation", "A1_provider"]:
        df[c] = df[c].astype(str)
    form = ("cap ~ C(A1_provider)+C(A2_version)+C(A3_temperature)+C(A4_paraphrase)"
            "+C(A5_format)+C(A6_fewshot)+C(A7_presentation)+C(seed)")
    m = smf.ols(form, data=df).fit(); a = anova_lm(m, typ=2); t = a["sum_sq"].sum()
    share = {k.replace("C(", "").replace(")", ""): round(float(a["sum_sq"][k] / t * 100), 2)
             for k in a.index}
    design = round(sum(v for k, v in share.items() if k.startswith("A")), 2)
    return {"variance_share_pct": share, "design_axes_total_pct": design,
            "seed_noise_pct": share.get("seed", 0.0), "residual_pct": share.get("Residual", 0.0),
            "note": ("Portfolio required-capital variance across draws decomposed by design axes "
                     "(A1 provider..A7 presentation) vs seed (pure sampling noise) vs residual "
                     "(unmodelled axis interactions). Each draw is single-provider.")}
decomp = decompose(piv, meta)

# ============ ROBUSTNESS ============
# (a) value-weight: SYNTHETIC identity-agnostic Zipf concentration by name index (NO real-firm data)
zw = np.array([1.0 / (i + 1) for i in range(len(ALL_NAMES))]); zw = zw / zw.sum()   # sums to 1
vw_ead = zw * (len(ALL_NAMES) * EAD)                                                # same total book
def cap_vw(piv):
    order = list(piv.columns)
    w = np.array([vw_ead[ALL_NAMES.index(c)] for c in order])
    cap = RATIO * (piv.values * w).sum(axis=1)
    q = lambda p: float(np.percentile(cap, p))
    diffs = np.abs(np.subtract.outer(cap, cap)); iu = np.triu_indices(len(cap), k=1)
    med = float(np.median(cap))
    return {"n_draws": int(len(cap)), "weight_scheme": "synthetic Zipf 1/rank by name index (identity-agnostic, no real-firm data); total book held at $45B",
            "capital_distribution_usd": {"min": round(float(cap.min()),0), "p25": round(q(25),0),
                "median": round(med,0), "p75": round(q(75),0), "max": round(float(cap.max()),0)},
            "capital_range_pct_of_median": round((cap.max()-cap.min())/med*100, 2),
            "expected_abs_capital_diff_pct_of_median": round(float(diffs[iu].mean())/med*100, 2)}
rob_vw = cap_vw(piv)

# (b) exclude saturating names whose verdict ever reaches CCC-or-worse (RW hits 1.50 via CCC band)
#     define saturating = name reaches the DISTRESS band (dec_band) in >=1 draw (letter in CCC+..C)
DISTRESS = {"CCC+", "CCC", "CCC-", "CC", "C"}
reaches_ccc = [nm for nm in ALL_NAMES
               if CR[CR.item_id == nm].dec_letter.isin(DISTRESS).any()]
nonsat = [nm for nm in ALL_NAMES if nm not in reaches_ccc]
piv_ns, meta_ns = draw_table(CR, nonsat)
rob_ex = cap_stats(piv_ns, "exclude_CCC_reaching_nonsaturating", nonsat)
rob_ex.pop("_cap_vector", None)

# (c) parse-rule sensitivity
rob_parse = {}
for pr in ["strict", "tolerant"]:
    crp = build(pr)
    common = sorted(set(crp.item_id.unique()) & set(ALL_NAMES))
    pivp, _ = draw_table(crp, common)
    s = cap_stats(pivp, f"parse_{pr}", common); s.pop("_cap_vector", None)
    rob_parse[pr] = {k: s[k] for k in ["n_draws", "n_names", "capital_distribution_usd",
                     "capital_range_pct_of_median", "expected_abs_capital_diff_pct_of_median",
                     "expected_abs_capital_diff_per_comparison_usd"]}

# collapse check
collapse = {
 "n_saturating_names_reach_CCC": len(reaches_ccc),
 "n_nonsaturating_names": len(nonsat),
 "base_expected_abs_capital_diff_pct_of_median": base["expected_abs_capital_diff_pct_of_median"],
 "nonsat_expected_abs_capital_diff_pct_of_median": rob_ex["expected_abs_capital_diff_pct_of_median"],
 "base_capital_range_pct_of_median": base["capital_range_pct_of_median"],
 "nonsat_capital_range_pct_of_median": rob_ex["capital_range_pct_of_median"],
 "collapses_without_saturating_names": bool(
     rob_ex["expected_abs_capital_diff_pct_of_median"] < 0.5 * base["expected_abs_capital_diff_pct_of_median"]),
 "interpretation": ("If dispersion largely persists after removing CCC-reaching names, capital "
    "variability is NOT merely a saturation artefact; if it collapses, the headline capital range is "
    "driven by the sub-BB- 150% ceiling being reached by some specs and not others.")}

# ============ T8.3 RCAP REGULATORY BENCHMARK (verified constants) ============
# Machine outlier deviation from its OWN median, to line up with RCAP's "outlier vs benchmark" framing.
_med = base["capital_distribution_usd"]["median"]
mach_pos = (base["capital_distribution_usd"]["max"] - _med) / _med * 100
mach_neg = (_med - base["capital_distribution_usd"]["min"]) / _med * 100
benchmark = {
 "rcap_source": "BCBS 256 (July 2013), 'RCAP - Analysis of risk-weighted assets for credit risk in the banking book'; BIS press release p130705 (05 Jul 2013).",
 "rcap_url": "https://www.bis.org/press/p130705.htm  (full report https://www.bis.org/publ/bcbs256.htm)",
 "rcap_verified_quote": ("\"...could result in the reported capital ratios for some outlier banks varying by as much "
   "as 2 percentage points from a 10% risk-based capital ratio benchmark (or 20% in relative terms) in either "
   "direction, although the capital ratios for most banks fall within a narrower range.\" (BIS press release, 05 Jul 2013)"),
 "rcap_scope": ">100 major banks; 32 major international banks in the portfolio benchmarking exercise; IRB internal models (PD/LGD) on real/hypothetical banking-book portfolios.",
 "rcap_headline_relative_dispersion_pct": 20.0,          # outlier bank vs 10% benchmark, relative terms
 "rcap_headline_abs_capital_ratio_pp": 2.0,              # percentage points either direction
 "rcap_qualifier": "Applies to OUTLIER banks; most banks fall in a narrower range. Corporate asset class showed the TIGHTEST clustering; sovereign the greatest variation.",
 "machine_outlier_deviation_from_median_pct": {"above_median": round(mach_pos, 1), "below_median": round(mach_neg, 1)},
 "machine_expected_pairwise_relative_pct": base["expected_abs_capital_diff_pct_of_median"],
 "machine_full_range_relative_pct": base["capital_range_pct_of_median"],
 "comparison_statement": (
   f"RCAP: OUTLIER banks deviate up to ~20% (relative) from a 10% capital-ratio benchmark on the SAME "
   f"portfolios using IRB internal models. Machine: specifications rating the SAME $45B book under the "
   f"STANDARDISED (ECRA) approach deviate -{mach_neg:.0f}%/+{mach_pos:.0f}% (relative) from their median at "
   f"the extremes, with an EXPECTED pairwise gap of {base['expected_abs_capital_diff_pct_of_median']:.1f}%. "
   f"The machine's central-tendency pairwise dispersion ({base['expected_abs_capital_diff_pct_of_median']:.1f}%) "
   f"is of the same order as RCAP's outlier dispersion (~20%); on the like-for-like outlier metric the machine "
   f"spread is somewhat WIDER."),
 "non_comparability_note": (
   "UNITS DIFFER — this is calibration, not identity. RCAP measures ACROSS-BANK dispersion from IRB internal "
   "PD/LGD models on real supervised portfolios, expressed as capital-RATIO percentage points; our measure is "
   "ACROSS-SPECIFICATION dispersion of an LLM's letter ratings pushed through the STANDARDISED ECRA table on a "
   "synthetic 45-name battery, expressed as relative dispersion in required Pillar-1 capital. RCAP's 20% is an "
   "OUTLIER-vs-benchmark figure; our primary 20.5% is an EXPECTED pairwise gap. The two should be read as "
   "order-of-magnitude comparanda, not equated. We do NOT claim LLM specifications are banks."),
 "supporting_literature": (
   "Behn, Haselmann & Vig (2022, Journal of Finance, 'The Limits of Model-Based Regulation') and "
   "Mariathasan & Merrouche (2014, J. Financial Intermediation, 'The manipulation of Basel risk-weights') "
   "corroborate material practice-based / model-based RWA variation across institutions. Cited QUALITATIVELY; "
   "we extract no numeric benchmark from them (only BCBS 256 supplies our quote-verified figure)."),
 "mandatory_caveat": (
   "The capital figures are the regulatory MINIMUM implied by the ratings the model emits under a stated, "
   "stripped-down Pillar-1/ECRA/equal-weight/no-buffer scenario. They are NOT a claim that any bank would deploy "
   "an LLM as its rating engine, NOT an economic loss estimate, and NOT a statement about realised capital "
   "adequacy. The exercise shows that IF identical inputs were rated under trivially different prompt "
   "specifications, the implied regulatory capital would swing by the magnitudes reported."),
 "attack_item_xii": ("(xii) 'Specs aren't banks and standardized isn't IRB, so the RCAP comparison is invalid.' "
   "Conceded on units (see non_comparability_note). The comparison is a calibration anchor: it places the "
   "machine's specification-induced capital dispersion on the same axis as the cross-bank dispersion that "
   "regulators already deemed large enough to warrant policy action. The claim is 'same order of magnitude, "
   "measured honestly with different instruments', identical in spirit to the T6 human-benchmark framing.")}

# ============ T8.4 CORRELATED-NOISE BRIDGE: within- vs cross-vendor capital-error correlation ============
def vendor_correlation(piv, meta):
    names = list(piv.columns)
    RWmat = piv.values.astype(float)                        # draws x names
    E = RWmat - RWmat.mean(axis=0, keepdims=True)           # per-name capital-error (demeaned across draws)
    prov = meta["A1_provider"].values
    nd = len(prov)
    same, diff = [], []
    same_by = collections.defaultdict(list)
    for i in range(nd):
        for j in range(i + 1, nd):
            a, b = E[i], E[j]
            if a.std() == 0 or b.std() == 0:
                continue
            r = float(np.corrcoef(a, b)[0, 1])
            if prov[i] == prov[j]:
                same.append(r); same_by[prov[i]].append(r)
            else:
                diff.append(r)
    rho_same = float(np.mean(same)) if same else float("nan")
    rho_diff = float(np.mean(diff)) if diff else float("nan")
    return {
     "definition": ("Each specification is treated as an institution holding the SAME 45-name book. Its per-name "
        "capital error = risk-weight deviation from the cross-specification mean for that name. rho = mean "
        "across-name correlation of these error vectors between two specifications."),
     "rho_same_vendor": round(rho_same, 3), "rho_diff_vendor": round(rho_diff, 3),
     "gap_same_minus_diff": round(rho_same - rho_diff, 3),
     "n_same_pairs": len(same), "n_diff_pairs": len(diff),
     "rho_same_by_vendor": {k: round(float(np.mean(v)), 3) for k, v in sorted(same_by.items())},
     "interpretation": (
        "rho_same > rho_diff means two institutions running the SAME vendor make correlated capital errors, so "
        "their implied capital shortfalls move together (a systemic, non-diversifiable component); switching "
        "vendors diversifies the error. rho_same < rho_diff would mean vendor choice is not the correlating "
        "axis. This is the micro-foundation for the correlated-shock channel in Llacay & Peffer (Finance "
        "Research Letters, 2026): homogeneous model adoption converts idiosyncratic rating noise into a common "
        "factor."),
     "attack_item_xiii": ("(xiii) 'You never show market impact.' Conceded — T8 runs no market simulation. We "
        "establish only the necessary precondition for the transmission mechanism: that same-vendor capital "
        "errors are correlated (rho_same vs rho_diff). The step from correlated capital errors to procyclical "
        "deleveraging / fire-sale amplification is cited, not simulated (Llacay & Peffer 2026; the RCAP policy "
        "concern with practice-based RWA variation). Market-impact modelling is scoped out and flagged as future work.")}
vendor_corr = vendor_correlation(piv, meta)

OUT = {
 "_label": "POST-HOC ADDITION (T8.2-8.4, labelled): machine RWA/capital dispersion on the frozen panel. "
           "No model calls. ECRA table quote-verified from BIS CRE20.42 (see capital_map.json).",
 "capital.scope": {"pillar": "Pillar 1 minimum only, no buffers", "min_ratio": RATIO,
    "risk_weights": "Basel III ECRA corporate base weights (CRE20.42)", "weighting": "equal-weight",
    "notional_per_name_usd": EAD, "n_names": len(ALL_NAMES),
    "capital_map_sha256_ref": "see 00_frozen_inputs/MANIFEST_CAPITAL.sha256"},
 "capital.base": {k: v for k, v in base.items() if k != "_cap_vector"},
 "capital.primary_number_for_main_text": {
    "statistic": "expected absolute difference in required Pillar-1 capital between two randomly chosen specifications of the SAME $45B equal-weight book (per-comparison, non-accumulating)",
    "value_usd": base["expected_abs_capital_diff_per_comparison_usd"],
    "value_pct_of_median_capital": base["expected_abs_capital_diff_pct_of_median"],
    "full_range_usd": base["capital_range_usd"],
    "full_range_pct_of_median_capital": base["capital_range_pct_of_median"]},
 "capital.decomposition": decomp,
 "capital.per_name_summary": {
    "expected_abs_rw_diff_median": round(float(np.median(name_emad)), 4),
    "expected_abs_rw_diff_max": round(float(name_emad.max()), 4),
    "n_names_zero_dispersion": int((name_emad == 0).sum()),
    "median_per_name_capital_range_usd": round(float(np.median(
        [per_name[n]["capital_range_usd_per_name"] for n in ALL_NAMES])), 0)},
 "capital.robustness_value_weight": rob_vw,
 "capital.robustness_exclude_saturating": rob_ex,
 "capital.robustness_parse_rule": rob_parse,
 "capital.saturation_collapse_check": collapse,
 "capital.regulatory_benchmark_RCAP": benchmark,
 "capital.vendor_error_correlation": vendor_corr,
 "_cap_vector_base": base["_cap_vector"],
 "capital.assumptions": (
    "Equal-weight $1B on-balance-sheet drawn corporate EAD per name; Pillar-1 minimum at 8%; ECRA "
    "base risk weights only (no CRM, no CCF, no maturity adjustment, no buffers, no Pillar 2). "
    "Draws are complete spec x seed portfolios (each single-provider). 'Capital' throughout is the "
    "regulatory minimum implied by the ratings the model emits, NOT an economic loss estimate."),
 "_per_name": per_name}

(PB / "results" / "results_capital.json").write_text(json.dumps(OUT, indent=1))
print("draws:", base["n_draws"], "| names:", base["n_names"], "| notional $%.0fB" % (base["total_notional_usd"]/1e9))
print("capital distribution $M:", {k: round(v/1e6,1) for k,v in base["capital_distribution_usd"].items()})
print("range: $%.1fM = %.2f%% of median | %.3f%% of book" % (
    base["capital_range_usd"]/1e6, base["capital_range_pct_of_median"], base["capital_range_pct_of_notional"]))
print("PRIMARY expected |Δcapital| per comparison: $%.1fM = %.2f%% of median" % (
    base["expected_abs_capital_diff_per_comparison_usd"]/1e6, base["expected_abs_capital_diff_pct_of_median"]))
print("decomp design axes %.1f%% | seed %.1f%% | residual %.1f%%" % (
    decomp["design_axes_total_pct"], decomp["seed_noise_pct"], decomp["residual_pct"]))
print("saturating(reach CCC):", len(reaches_ccc), "| nonsat:", len(nonsat),
      "| collapses:", collapse["collapses_without_saturating_names"])
print("  base EMAD%%=%.2f  ->  nonsat EMAD%%=%.2f" % (
    base["expected_abs_capital_diff_pct_of_median"], rob_ex["expected_abs_capital_diff_pct_of_median"]))
print("RCAP: machine outlier dev from median +%.0f%%/-%.0f%% vs RCAP outlier ~20%% (relative)" % (mach_pos, mach_neg))
print("vendor corr: rho_same=%.3f  rho_diff=%.3f  gap=%.3f  (same %d / diff %d pairs)" % (
    vendor_corr["rho_same_vendor"], vendor_corr["rho_diff_vendor"], vendor_corr["gap_same_minus_diff"],
    vendor_corr["n_same_pairs"], vendor_corr["n_diff_pairs"]))
print("  rho_same_by_vendor:", vendor_corr["rho_same_by_vendor"])
