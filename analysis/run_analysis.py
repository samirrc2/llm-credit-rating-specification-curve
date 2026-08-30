"""B3 — confirmatory analysis. Reads ONLY 02_panel/panel.parquet (never raw). One
seeded entrypoint. Emits 03_analysis/results.json (destination-named keys) +
MANIFEST_ANALYSIS.sha256. All results confirmatory; exploratory items are labelled.
"""
from __future__ import annotations
import json, collections, hashlib, math
from pathlib import Path
import numpy as np
import pandas as pd

PB = Path(__file__).resolve().parents[1]
OUT = PB / "results"; OUT.mkdir(exist_ok=True)
RS = json.load(open(PB / "data" / "frozen" / "main" / "rating_scale.json"))
LETTERS = RS["letter_scale"]; LRANK = {l: i for i, l in enumerate(LETTERS)}
BANDNOTCH = {"SAFE": 0, "WATCH": 1, "DISTRESS": 2}
DORD = {"BUY": 1, "HOLD": 0, "SELL": -1}
AXES = ["A1_provider", "A2_version", "A3_temperature", "A4_paraphrase", "A5_format", "A6_fewshot", "A7_presentation"]
rng = np.random.default_rng(42)

P = pd.read_parquet(PB / "data" / "panel" / "panel.parquet")
P = P[P.provider.isin(["openai", "google"])].copy()   # two-vendor design: full current+prior coverage
L = P[P.parse_rule == "lenient"].copy()               # primary parse rule
L["letter_rank"] = L.dec_letter.map(LRANK)
CR = L[(L.family == "credit_health") & L.decision.notna()].copy()
DR = L[(L.family == "directional") & L.decision.notna()].copy()
R = {"_meta": {"panel_rows": int(len(P)), "primary_parse": "lenient",
               "panel_sha": open(PB / "data" / "panel" / "MANIFEST_PANEL.sha256").read().strip()[:16],
               "live_cells": sorted(L.groupby(["provider", "version"]).groups.keys())}}


def band_of(letter):
    return RS["letter_to_band"].get(letter)


# ================= 3.1 noise floor =================
def noise_floor():
    d = CR   # credit band-level decisions for seed comparison (also do directional)
    out = {}
    def disagree(sub, col):
        piv = sub.pivot_table(index=["spec_id", "item_id"], columns="seed", values=col, aggfunc="first").dropna()
        if piv.shape[1] < 2:
            return None
        # any pair of seeds disagree
        return round(float((piv.nunique(axis=1) > 1).mean()), 4)
    mat = []
    for (prov, rt, ta), g in L[L.decision.notna()].groupby(["provider", "requested_temp", "temp_applied"]):
        mat.append({"provider": prov, "requested_temp": rt, "temp_applied": bool(ta),
                    "n_cells": int(len(g)), "seed_disagree": disagree(g, "decision")})
    return {"table2.noise_matrix": mat,
            "table2.google_temp0_seed_disagree": disagree(L[(L.provider == "google") & (L.requested_temp == 0.0) & L.decision.notna()], "decision")}


# ================= 3.2 deterministic subgrid (Google@temp0) =================
def det_subgrid():
    sub = CR[(CR.provider == "google") & (CR.requested_temp == 0.0)].copy()
    sub["mband"] = sub.dec_letter.map(band_of)
    acc = sub.groupby("spec_id").apply(lambda x: (x.mband == x.bench_band).mean())
    # permutation on band-accuracy spread
    sub["hit"] = (sub.mband == sub.bench_band).astype(float)
    obs = float(sub.groupby("spec_id").hit.mean().std())
    specs = sub.spec_id.values.copy(); base = sub[["item_id", "hit"]].copy(); null = []
    for _ in range(1000):
        b = base.copy(); b["spec_id"] = rng.permutation(specs)
        null.append(b.groupby("spec_id").hit.mean().std())
    p = float((np.sum(np.array(null) >= obs) + 1) / 1001)
    # letter-rank range too (finest)
    rankrange = sub.groupby("spec_id").apply(lambda x: x.letter_rank.mean())
    return {"table_det.n_specs": int(sub.spec_id.nunique()),
            "table_det.band_accuracy_range": [round(float(acc.min()), 3), round(float(acc.max()), 3)],
            "table_det.band_flip_share_majority": round(float((acc <= 0.5).mean()), 3),
            "table_det.mean_letterrank_range": [round(float(rankrange.min()), 2), round(float(rankrange.max()), 2)],
            "table_det.permutation_p": round(p, 4), "table_det.perm_obs_sd": round(obs, 4)}


# ================= 3.3 variance decomposition =================
def variance_decomp():
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm
    d = CR.dropna(subset=["letter_rank"]).copy()
    d["A3_temperature"] = d.A3_temperature.astype(str)
    form = ("letter_rank ~ C(item_id)+C(A1_provider)+C(A2_version)+C(A3_temperature)+C(A4_paraphrase)"
            "+C(A5_format)+C(A6_fewshot)+C(A7_presentation)+C(A1_provider):C(item_id)")
    m = smf.ols(form, data=d).fit()
    aov = anova_lm(m, typ=2); tot = aov["sum_sq"].sum()
    lab = {"C(item_id)": "item", "C(A1_provider)": "A1_provider", "C(A2_version)": "A2_version",
           "C(A3_temperature)": "A3_temperature", "C(A4_paraphrase)": "A4_paraphrase", "C(A5_format)": "A5_format",
           "C(A6_fewshot)": "A6_fewshot", "C(A7_presentation)": "A7_presentation",
           "C(A1_provider):C(item_id)": "provider_x_item", "Residual": "residual_seed_noise"}
    share = {lab.get(k, k): round(float(v / tot * 100), 3) for k, v in aov["sum_sq"].items()}
    # ---- A1: split the OLS residual into pure within-cell (seed) variance vs other unexplained ----
    # SS_within = variance across seeds within each identical (item, spec) cell -> pure run-to-run.
    gm = d.letter_rank.mean(); ss_tot = float(((d.letter_rank - gm) ** 2).sum())
    ss_within = float(d.groupby(["item_id", "spec_id"]).letter_rank
                      .transform(lambda x: ((x - x.mean()) ** 2).sum()).groupby([d.item_id, d.spec_id]).first().sum())
    seed_pct = round(ss_within / ss_tot * 100, 3)
    resid_pct = float(share.get("residual_seed_noise", 0.0))
    other_pct = round(max(0.0, resid_pct - seed_pct), 3)
    # ---- C3: issuer-clustered bootstrap 95% CI on the pure-seed share and item share ----
    # Per-item aggregates so each bootstrap replicate is O(#items): n, sum, sumsq, and within-cell SS.
    agg = {}
    for it, gi in d.groupby("item_id"):
        n = len(gi); s = float(gi.letter_rank.sum()); sq = float((gi.letter_rank ** 2).sum())
        sw = float(gi.groupby("spec_id").letter_rank.apply(lambda x: ((x - x.mean()) ** 2).sum()).sum())
        agg[it] = (n, s, sq, sw)
    items = np.array(list(agg.keys()))
    A = {it: agg[it] for it in items}
    bs_seed, bs_item = [], []
    for _ in range(1000):
        samp = rng.choice(items, len(items), replace=True)
        N = S = SQ = SW = SBI = 0.0
        for it in samp:
            n, s, sq, sw = A[it]
            N += n; S += s; SQ += sq; SW += sw
            SBI += (s * s) / n              # sum_i^2 / n_i  -> for between-item SS
        if N == 0: continue
        st = SQ - S * S / N                 # SS_total
        if st <= 0: continue
        sb_item = SBI - S * S / N           # SS_between_items
        bs_seed.append(SW / st * 100); bs_item.append(sb_item / st * 100)
    ci = lambda a: [round(float(np.percentile(a, 2.5)), 2), round(float(np.percentile(a, 97.5)), 2)]
    return {"table2.variance_shares_pct_letterrank": share, "table2.n_obs": int(len(d)),
            "table2.n_items": int(len(items)),
            "table2.seed_within_cell_pct": seed_pct,
            "table2.other_unexplained_pct": other_pct,
            "table2.seed_within_cell_pct_CI95": ci(bs_seed),
            "table2.item_share_pct_CI95": ci(bs_item)}


# ================= 3.4 spec curves (band level for Phase A comparability) =================
def spec_curves():
    CR2 = CR.copy(); CR2["mband"] = CR2.dec_letter.map(band_of)
    C1 = CR2.groupby("spec_id").apply(lambda x: float((x.mband == x.bench_band).mean()))
    C2 = CR2.groupby("spec_id").apply(lambda x: float((x.mband.map(BANDNOTCH) - x.bench_band.map(BANDNOTCH)).median()))
    C3 = DR.groupby("spec_id").decision.agg(lambda x: x.value_counts().idxmax())
    citems = CR2.item_id.unique(); ditems = DR.item_id.unique()

    def boot_flip(sub, items, kind, ismb=False):
        vals = []
        for _ in range(1000):
            samp = rng.choice(items, len(items), replace=True)
            s = pd.concat([sub[sub.item_id == it] for it in samp])
            if kind == "C1":
                a = s.groupby("spec_id").apply(lambda x: (x.mband == x.bench_band).mean())
                vals.append(float((a <= 0.5).mean()))
            else:
                c = s.groupby("spec_id").decision.agg(lambda x: x.value_counts().idxmax())
                vals.append(float((c != c.value_counts().idxmax()).mean()))
        return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]

    # permutation for C1 spread
    cs = CR2.copy(); cs["hit"] = (cs.mband == cs.bench_band).astype(float)
    obs = float(cs.groupby("spec_id").hit.mean().std())
    specs = cs.spec_id.values.copy(); base = cs[["item_id", "hit"]].copy(); null = []
    for _ in range(1000):
        b = base.copy(); b["spec_id"] = rng.permutation(specs); null.append(b.groupby("spec_id").hit.mean().std())
    pval = float((np.sum(np.array(null) >= obs) + 1) / 1001)
    c3mode = C3.value_counts().idxmax()
    return {"abstract.flip_share_C1": round(float((C1 <= 0.5).mean()), 3),
            "table1.C1_accuracy_range": [round(float(C1.min()), 3), round(float(C1.max()), 3)],
            "table1.C1_95CI_flip": boot_flip(CR2, citems, "C1"),
            "table1.C2_median_notch_modal_sign": float(np.sign(C2.median())),
            "table1.C2_flip_share": round(float((np.sign(C2) != np.sign(C2.median())).mean()), 3),
            "abstract.flip_share_C3": round(float((C3 != c3mode).mean()), 3),
            "table1.C3_modal": str(c3mode), "table1.C3_95CI_flip": boot_flip(DR, ditems, "C3"),
            "table1.permutation_C1_p": round(pval, 4), "table1.perm_obs_sd": round(obs, 4),
            "_spec_curve_C1": {s: round(float(v), 3) for s, v in C1.items()},
            "_spec_curve_C3": {s: str(v) for s, v in C3.items()}}


# ================= 3.5 vendor structure =================
def vendor():
    base = CR[(CR.version == "current") & (CR.requested_temp == 1.0)].copy()
    base["mband"] = base.dec_letter.map(band_of)
    within, cross = [], []; within_l, cross_l = [], []
    for it, g in base.groupby("item_id"):
        provs = {pr: gg.sort_values("seed") for pr, gg in g.groupby("provider")}
        for pr, gg in provs.items():
            bs = gg.mband.tolist(); ls = gg.dec_letter.tolist()
            for i in range(len(bs)):
                for j in range(i + 1, len(bs)):
                    within.append(bs[i] == bs[j]); within_l.append(ls[i] == ls[j])
        pl = list(provs.items())
        for i in range(len(pl)):
            for j in range(i + 1, len(pl)):
                bi, bj = pl[i][1].mband.iloc[0], pl[j][1].mband.iloc[0]
                li, lj = pl[i][1].dec_letter.iloc[0], pl[j][1].dec_letter.iloc[0]
                cross.append(bi == bj); cross_l.append(li == lj)
    vs = R["block_var"]["table2.variance_shares_pct_letterrank"] if "block_var" in R else None
    return {"table3.within_family_agreement_band": round(float(np.mean(within)), 3),
            "table3.cross_family_agreement_band": round(float(np.mean(cross)), 3),
            "table3.within_family_agreement_letter": round(float(np.mean(within_l)), 3),
            "table3.cross_family_agreement_letter": round(float(np.mean(cross_l)), 3),
            "table3.n_within": len(within), "table3.n_cross": len(cross)}


# ================= 3.6 economic translation =================
SPREAD = {"SAFE": 150, "WATCH": 300, "DISTRESS": 700}   # indicative bps by band (rating-spread table)
def economic():
    d = CR.copy(); d["mband"] = d.dec_letter.map(band_of); d["ighy"] = d.dec_letter.map(RS["letter_to_ig_hy"])
    straddle = d.groupby("item_id").ighy.agg(lambda x: x.nunique() > 1)
    d["spread"] = d.mband.map(SPREAD)
    rng_bps = d.groupby("item_id").spread.agg(lambda x: float(x.max() - x.min()))
    # Cornaggia anchor: 80-140 bps per 2-3 notches -> report both our table + the anchor
    ds = DR.copy(); ds["pos"] = ds.decision.map(DORD)
    turn = ds.groupby("item_id").pos.agg(lambda x: float(np.mean(np.abs(x - np.median(x)))))
    # PRIMARY stability measure (per-comparison, does NOT accumulate with #draws):
    #   pick two random (spec,seed) draws for a name -> P(they land on opposite sides of IG/HY).
    draws = d.groupby("item_id").ighy.size()
    flip_per_item = np.array([1 - float((g.ighy.value_counts(normalize=True) ** 2).sum())
                              for _, g in d.groupby("item_id")])
    percomp_ighy_flip = float(flip_per_item.mean())
    def _bootci(arr, reps=2000):   # issuer-clustered percentile bootstrap 95% CI
        bs = np.array([float(np.mean(rng.choice(arr, len(arr), replace=True))) for _ in range(reps)])
        return [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
    flip_ci = _bootci(flip_per_item); turn_ci = _bootci(turn.values)
    return {"table4.PRIMARY_percomparison_ighy_flip": round(percomp_ighy_flip, 4),
            "table4.PRIMARY_percomparison_ighy_flip_CI95": flip_ci,
            "table4.implied_turnover_CI95": turn_ci,
            "table4.draws_per_name": int(round(float(draws.mean()))),
            "table4.ig_hy_crossing_pct": round(float(straddle.mean()) * 100, 1),
            "table4.ig_hy_denominator": int(d.item_id.nunique()),
            "table4.ig_hy_crossing_note": ("max-over-draws statistic: with ~%d draws/name it accumulates "
                "mechanically; report it as the union a LITERATURE of single-spec papers would collectively "
                "reach, NOT as a per-decision rate. Primary measure is the per-comparison flip above."
                % int(round(float(draws.mean())))),
            "table4.mean_within_name_spread_range_bps": round(float(rng_bps.mean()), 1),
            "table4.max_within_name_spread_range_bps": round(float(rng_bps.max()), 1),
            "table4.cornaggia_anchor": "80-140 bps per 2-3 notches (Cornaggia, Cornaggia & Israelsen)",
            "table4.implied_turnover_meanposdev": round(float(turn.mean()), 3),
            "table4.rating_spread_map_bps": SPREAD}


# ================= 3.7 granularity-stability (NEW) =================
def granularity():
    d = CR.copy()
    gmap = {"letter": "dec_letter", "notch": "dec_notch", "band": "dec_band", "ig_hy": "dec_ighy"}
    curve = {}
    for gname, col in gmap.items():
        # pairwise disagreement within item across all (spec,seed): 1 - Simpson concentration
        dis = []
        for it, g in d.groupby("item_id"):
            vc = g[col].value_counts(normalize=True)
            dis.append(1 - float((vc ** 2).sum()))
        curve[gname] = round(float(np.mean(dis)), 4)
    agree = {g: round(1 - v, 4) for g, v in curve.items()}
    def eff_res(x):
        order = ["letter", "notch", "band", "ig_hy"]   # finest -> coarsest
        for g in order:
            if agree[g] >= x:
                return g
        return "coarser_than_ig_hy"
    # scale usage entropy (from quality report recompute)
    ent = CR.dec_letter.value_counts(normalize=True)
    H = round(-sum(pp * math.log2(pp) for pp in ent if pp > 0), 3)
    # ---- chance-corrected agreement per granularity (POST-HOC ROBUSTNESS, labelled) ----
    # Fleiss' kappa + Gwet's AC1 over items(subjects) x (spec,seed) raters x categories.
    # Answers the chance-baseline objection: IG/HY has a high chance-agreement floor, the
    # 21-letter scale a low one, so raw agreement overstates coarse-level stability.
    def kappa_ac1(col):
        cats = sorted(x for x in d[col].dropna().unique())
        cidx = {c: i for i, c in enumerate(cats)}; q = len(cats)
        Pi, ni_list, colsum = [], [], np.zeros(q)
        for it, g in d.groupby("item_id"):
            counts = np.zeros(q)
            for v in g[col].dropna():
                counts[cidx[v]] += 1
            n = counts.sum()
            if n < 2:
                continue
            Pi.append((np.sum(counts ** 2) - n) / (n * (n - 1)))
            ni_list.append(n); colsum += counts
        Pbar = float(np.mean(Pi)); pj = colsum / colsum.sum()
        Pe_f = float(np.sum(pj ** 2))                       # Fleiss chance
        kappa = (Pbar - Pe_f) / (1 - Pe_f) if Pe_f < 1 else 0.0
        Pe_g = float(np.sum(pj * (1 - pj)) / (q - 1)) if q > 1 else 0.0   # Gwet AC1 chance
        ac1 = (Pbar - Pe_g) / (1 - Pe_g) if Pe_g < 1 else 0.0
        return {"raw_agreement": round(Pbar, 4), "chance_Pe_fleiss": round(Pe_f, 4),
                "fleiss_kappa": round(kappa, 3), "gwet_ac1": round(ac1, 3), "n_categories": q}
    chance = {g: kappa_ac1(c) for g, c in gmap.items()}
    def eff_res_k(x):
        for g in ["letter", "notch", "band", "ig_hy"]:
            if chance[g]["fleiss_kappa"] >= x:
                return g
        return "coarser_than_ig_hy"
    return {"table5.flip_prob_by_granularity": curve, "table5.agreement_by_granularity": agree,
            "table5.effective_resolution_80pct": eff_res(0.80),
            "table5.effective_resolution_90pct": eff_res(0.90),
            "table5.effective_resolution_95pct": eff_res(0.95),
            "table5.scale_usage_letters": int(CR.dec_letter.nunique()),
            "table5.scale_usage_entropy_bits": H, "table5.scale_max_entropy_bits": round(math.log2(21), 2),
            "table5.chance_corrected_POSTHOC": chance,
            "table5.effective_resolution_kappa0.6": eff_res_k(0.6),
            "table5.effective_resolution_kappa0.4": eff_res_k(0.4),
            "table5.note_chance": ("POST-HOC robustness (labelled): raw agreement rises with coarsening partly "
                "because coarse scales have a high chance-agreement floor; chance-corrected (Fleiss kappa / "
                "Gwet AC1) the coarse levels look far worse, so 'no stable resolution' is STARKER, not rescued.")}


# ================= 3.8 robustness =================
def robustness():
    out = {}
    CR2 = CR.copy(); CR2["mband"] = CR2.dec_letter.map(band_of)
    def c1flip(sub):
        a = sub.groupby("spec_id").apply(lambda x: (x.dec_letter.map(band_of) == x.bench_band).mean())
        return round(float((a <= 0.5).mean()), 3)
    out["robust.C1flip_full"] = c1flip(CR2)
    for prov in ["openai", "google", "xai"]:
        out[f"robust.C1flip_drop_{prov}"] = c1flip(CR2[CR2.provider != prov])
    # parse-rule sensitivity: recompute granularity agreement under strict & tolerant
    for rule in ["strict", "tolerant"]:
        rr = P[(P.parse_rule == rule) & (P.family == "credit_health") & P.dec_letter.notna()]
        dis = [1 - float((g.dec_band.value_counts(normalize=True) ** 2).sum()) for _, g in rr.groupby("item_id")]
        out[f"robust.band_agreement_{rule}"] = round(1 - float(np.mean(dis)), 4)
    return out


R["block_noise"] = noise_floor()
R["block_det"] = det_subgrid()
R["block_var"] = variance_decomp()
R["block_spec"] = spec_curves()
R["block_vendor"] = vendor()
R["block_econ"] = economic()
R["block_gran"] = granularity()
R["block_robust"] = robustness()

# strip internal helpers before save (keep spec curves for plotting separately)
spec_plot = {"C1": R["block_spec"].pop("_spec_curve_C1"), "C3": R["block_spec"].pop("_spec_curve_C3")}
(OUT / "spec_curves.json").write_text(json.dumps(spec_plot, indent=1))
(OUT / "results.json").write_text(json.dumps(R, indent=1))
h = hashlib.sha256()
h.update((OUT / "results.json").read_bytes())
h.update(Path(__file__).resolve().read_bytes())   # hash this script from its own (analysis/) location
(OUT / "MANIFEST_ANALYSIS.sha256").write_text(h.hexdigest() + "\n")
print("=== KEY RESULTS ===")
print("C1 flip:", R["block_spec"]["abstract.flip_share_C1"], "CI", R["block_spec"]["table1.C1_95CI_flip"],
      "| C3 flip:", R["block_spec"]["abstract.flip_share_C3"], "| perm p:", R["block_spec"]["table1.permutation_C1_p"])
print("det subgrid band acc range:", R["block_det"]["table_det.band_accuracy_range"], "perm p:", R["block_det"]["table_det.permutation_p"])
print("variance shares:", R["block_var"]["table2.variance_shares_pct_letterrank"])
print("vendor within/cross (band):", R["block_vendor"]["table3.within_family_agreement_band"], R["block_vendor"]["table3.cross_family_agreement_band"])
print("granularity agreement:", R["block_gran"]["table5.agreement_by_granularity"])
print("effective resolution 90%:", R["block_gran"]["table5.effective_resolution_90pct"])
print("economic IG/HY %:", R["block_econ"]["table4.ig_hy_crossing_pct"], "spread range bps:", R["block_econ"]["table4.mean_within_name_spread_range_bps"])
print("MANIFEST_ANALYSIS:", h.hexdigest()[:16])
