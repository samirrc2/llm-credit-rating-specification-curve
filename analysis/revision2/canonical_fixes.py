#!/usr/bin/env python3
"""Single canonical source for the numbers the final correction pass needs.

Items addressed (see the correction brief):
  1  IG/HY boundary index b on a half-step convention, what w includes, and the referral share
     under the corrected near-boundary rule (replacing the stale ~33%).
  2  Specification-only vs seed-only IG/HY disagreement, and the per-profile n_i (96 vs 95) used
     for the without-replacement sensitivity.
  8  One canonical calculation of BOTH the operating-point precision/recall AND the decision-curve
     net benefit, so Section 4.2 and the net-benefit table cannot disagree again.
  9  Scope of the SIS-dissent equivalence by resolution.

No new claims, no new experiments. Offline, deterministic.
"""
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd

PB = Path(__file__).resolve().parents[2]
RS = json.load(open(PB / "data/frozen/main/rating_scale.json"))
LETTERS = RS["letter_scale"]; LRANK = {l: i for i, l in enumerate(LETTERS)}
IGHY = RS["letter_to_ig_hy"]; BAND = RS["letter_to_band"]
P = pd.read_parquet(PB / "data/panel/panel.parquet")
P = P[P.provider.isin(["openai", "google"])]
CR = P[(P.family == "credit_health") & (P.parse_rule == "lenient") & P.decision.notna()].copy()
CR["ighy"] = CR.dec_letter.map(IGHY); CR["rank"] = CR.dec_letter.map(LRANK)
out = {"_meta": {"rows": int(len(CR)), "profiles": int(CR.item_id.nunique()),
                 "specs": int(CR.spec_id.nunique()), "new_model_calls": 0}}

# ---------------- 1. boundary index and the near-boundary band ----------------
b = (LRANK["BBB-"] + LRANK["BB+"]) / 2.0
near = lambda r, w: abs(r - b) <= w
bands = {}
for w in (1, 1.5, 2, 2.5, 3):
    inc = [l for l in LETTERS if near(LRANK[l], w)]
    bands[str(w)] = inc
WATCH = [l for l in LETTERS if BAND[l] == "WATCH"]
modal_letter = CR.groupby("item_id").dec_letter.agg(lambda v: Counter(v).most_common(1)[0][0])
modal_rank = modal_letter.map(LRANK)
share = {str(w): round(float(modal_rank.map(lambda r: near(r, w)).mean()), 4)
         for w in (1, 1.5, 2, 2.5, 3)}
out["item1_boundary"] = {
    "rank_BBBminus": LRANK["BBB-"], "rank_BBplus": LRANK["BB+"], "b_halfstep": b,
    "letters_in_band_by_w": bands, "WATCH_stratum_letters": WATCH,
    "band_equals_WATCH_at_any_w": any(sorted(v) == sorted(WATCH) for v in bands.values()),
    "share_of_profiles_near_boundary_by_w": share,
    "note": "w=1 admits only the two letters straddling the boundary; the WATCH stratum spans "
            "BB+ through B-. The two constructs are not the same and must not be equated."}
print(f"  [1] b={b}  band(w=1)={bands['1']}   WATCH={WATCH}")
print(f"      band==WATCH at any w: {out['item1_boundary']['band_equals_WATCH_at_any_w']}")
print(f"      share of profiles near boundary: {share}")

# ---------------- 2. specification-only vs seed-only disagreement ----------------
def gini(v):
    n = len(v)
    if n < 2:
        return np.nan
    p = np.array(list(Counter(v).values())) / n
    return 1 - float((p ** 2).sum())

# total: all elicitations of a profile pooled (specification and/or seed vary)
tot = CR.groupby("item_id").ighy.apply(lambda v: gini(v.tolist()))
n_i = CR.groupby("item_id").size()
# without replacement uses each profile's OWN n_i, not a blanket 96/95
wor = (tot * n_i / (n_i - 1))
# specification-only: collapse seeds to the per-(profile,spec) modal call, then vary spec
spec_modal = (CR.groupby(["item_id", "spec_id"]).ighy
              .agg(lambda v: Counter(v).most_common(1)[0][0]).reset_index())
spec_only = spec_modal.groupby("item_id").ighy.apply(lambda v: gini(v.tolist()))
# seed-only: within identical profile x specification cells, vary seed only
cell = CR.groupby(["item_id", "spec_id"]).ighy.apply(lambda v: gini(v.tolist()))
seed_only = cell.groupby("item_id").mean()
out["item2_decomposition"] = {
    "n_i_distribution": {str(k): int(v) for k, v in Counter(n_i.tolist()).items()},
    "profiles_with_n_lt_96": int((n_i < 96).sum()),
    "total_pair_disagreement_with_replacement": round(float(tot.mean()), 4),
    "total_pair_disagreement_without_replacement_per_profile_n": round(float(wor.mean()), 4),
    "specification_only_pair_disagreement": round(float(spec_only.mean()), 4),
    "seed_only_pair_disagreement_within_cells": round(float(seed_only.mean()), 4),
    "note": "Total pools both sources. Specification-only collapses the three seeds to the "
            "per-cell modal call before varying specification. Seed-only varies seed inside "
            "identical profile x specification cells."}
i2 = out["item2_decomposition"]
print(f"  [2] n_i: {i2['n_i_distribution']}  (profiles with n<96: {i2['profiles_with_n_lt_96']})")
print(f"      total {i2['total_pair_disagreement_with_replacement']:.4f}  "
      f"without-replacement {i2['total_pair_disagreement_without_replacement_per_profile_n']:.4f}")
print(f"      specification-only {i2['specification_only_pair_disagreement']:.4f}   "
      f"seed-only {i2['seed_only_pair_disagreement_within_cells']:.4f}")

# ---------------- 8. one canonical operating-point + net-benefit calculation ----------------
specs = sorted(CR.spec_id.unique()); calib, valid = set(specs[0::2]), set(specs[1::2])
rows = []
for it, g in CR.groupby("item_id"):
    c = g[g.spec_id.isin(calib)].ighy.tolist(); v = g[g.spec_id.isin(valid)].ighy.tolist()
    if len(c) < 2 or len(v) < 2:
        continue
    cnt = Counter(c)
    rows.append({"item": it, "k_cal": len(c), "sis": gini(c),
                 "dissent": len(c) - cnt.most_common(1)[0][1], "event": int(len(set(v)) > 1)})
D = pd.DataFrame(rows); y = D.event.values; n = len(D)
k_cal = sorted(set(D.k_cal))
def confusion(flag):
    TP = int(((flag == 1) & (y == 1)).sum()); FP = int(((flag == 1) & (y == 0)).sum())
    FN = int(((flag == 0) & (y == 1)).sum()); TN = int(((flag == 0) & (y == 0)).sum())
    return {"TP": TP, "FP": FP, "FN": FN, "TN": TN,
            "precision": round(TP / (TP + FP), 4) if TP + FP else None,
            "recall": round(TP / (TP + FN), 4) if TP + FN else None,
            "flagged_share": round(float(flag.mean()), 4),
            "net_benefit": {f"{pt:.2f}": round(TP / n - (FP / n) * (pt / (1 - pt)), 6)
                            for pt in (0.10, 0.20, 0.30, 0.45, 0.60)}}
RULES = {"any_disagreement_sis_gt_0": (D.sis > 0).astype(int).values,
         "sis_ge_0.08": (D.sis >= 0.08).astype(int).values,
         "dissent_ge_2": (D.dissent >= 2).astype(int).values,
         "dissent_ge_3": (D.dissent >= 3).astype(int).values}
out["item8_canonical"] = {
    "construction": "score on the 16 calibration specifications; event = the profile's modal "
                    "IG/HY call changes on at least one of the 16 disjoint validation "
                    "specifications; n = %d profiles" % n,
    "k_calibration_elicitations_per_profile": k_cal,
    "smallest_nonzero_sis_at_k_cal": round(2 * (1 / k_cal[0]) * (1 - 1 / k_cal[0]), 4),
    "smallest_nonzero_sis_at_k16": round(2 * (1 / 16) * (15 / 16), 4),
    "min_dissent_count_satisfying_sis_ge_0.08": int(D[D.sis >= 0.08].dissent.min()),
    "event_base_rate": round(float(y.mean()), 4),
    "rules": {k: confusion(v) for k, v in RULES.items()},
    "note": "tau=0.08 and 'any disagreement' are DIFFERENT rules on this calibration set, which "
            "pools three seeds per specification (k=%d). The equivalence of tau=0.08 to "
            "'any disagreement' holds only at k=16." % k_cal[0]}
for k, v in out["item8_canonical"]["rules"].items():
    print(f"  [8] {k:26} TP={v['TP']:2} FP={v['FP']:2} prec={v['precision']} rec={v['recall']} "
          f"NB(0.10)={v['net_benefit']['0.10']:.4f} NB(0.60)={v['net_benefit']['0.60']:.4f}")
print(f"      k_cal={k_cal}  smallest non-zero SIS there = "
      f"{out['item8_canonical']['smallest_nonzero_sis_at_k_cal']}  "
      f"(at k=16 it is {out['item8_canonical']['smallest_nonzero_sis_at_k16']})")
print(f"      SIS>=0.08 implies at least {out['item8_canonical']['min_dissent_count_satisfying_sis_ge_0.08']} dissents at k={k_cal[0]}")

# ---------------- 9. equivalence scope by resolution ----------------
def spearman(a, b_):
    a, b_ = pd.Series(a), pd.Series(b_); m = a.notna() & b_.notna()
    return round(float(np.corrcoef(a[m].rank(), b_[m].rank())[0, 1]), 6)
eq = {}
for res, col in (("ighy", "ighy"), ("band", "band")):
    CR["_r"] = CR.dec_letter.map(BAND) if res == "band" else CR.ighy
    rr = []
    for it, g in CR.groupby("item_id"):
        c = g[g.spec_id.isin(calib)]._r.tolist()
        if len(c) < 2:
            continue
        cnt = Counter(c)
        rr.append({"sis": gini(c), "dissent": len(c) - cnt.most_common(1)[0][1]})
    F = pd.DataFrame(rr)
    eq[res] = {"spearman_sis_vs_dissent": spearman(F.sis, F.dissent),
               "rank_identical": spearman(F.sis, F.dissent) == 1.0}
out["item9_equivalence_scope"] = {
    "by_resolution": eq,
    "note": "At the binary gate the equivalence is algebraic, since SIS=2(m/k)(1-m/k) is strictly "
            "increasing in the minority count. At three bands the measures are NOT rank-identical."}
print(f"  [9] Spearman(SIS, dissent): ighy {eq['ighy']['spearman_sis_vs_dissent']}, "
      f"band {eq['band']['spearman_sis_vs_dissent']} (rank-identical at band: {eq['band']['rank_identical']})")

# ---------------- 2b/3b. dissent-count operating rule, tie handling, AND-gate recall ----------
cells = CR.groupby(["item_id", "spec_id"]).ighy.apply(list)
short = [(k, v) for k, v in cells.items() if len(v) == 2]
no_modal_2 = sum(1 for _, v in short if v[0] != v[1])
no_modal_3 = sum(1 for _, v in cells.items() if len(v) == 3 and max(Counter(v).values()) == 1)
modal_letter_all = CR.groupby("item_id").dec_letter.agg(lambda v: Counter(v).most_common(1)[0][0])
rows2 = []
for it, g in CR.groupby("item_id"):
    c = g[g.spec_id.isin(calib)].ighy.tolist(); v = g[g.spec_id.isin(valid)].ighy.tolist()
    if len(c) < 2 or len(v) < 2:
        continue
    cnt = Counter(c)
    rows2.append({"d": len(c) - cnt.most_common(1)[0][1],
                  "near": bool(abs(LRANK[modal_letter_all[it]] - b) <= 1),
                  "event": int(len(set(v)) > 1)})
D2 = pd.DataFrame(rows2); y2 = D2.event.values; n2 = len(D2)
def metrics(flag):
    TP = int(((flag == 1) & (y2 == 1)).sum()); FP = int(((flag == 1) & (y2 == 0)).sum())
    FN = int(((flag == 0) & (y2 == 1)).sum())
    return {"TP": TP, "FP": FP,
            "precision": round(TP / (TP + FP), 4) if TP + FP else None,
            "recall": round(TP / (TP + FN), 4) if TP + FN else None,
            "referred_share": round(float(flag.mean()), 4),
            "net_benefit": {f"{pt:.2f}": round(TP / n2 - (FP / n2) * (pt / (1 - pt)), 6)
                            for pt in (0.10, 0.30, 0.60)}}
out["item2b_tie_handling"] = {
    "two_observation_cells": len(short),
    "two_observation_cells_with_disagreeing_seeds": no_modal_2,
    "three_observation_cells_with_no_modal_winner": no_modal_3,
    "rule": "the per-specification outcome is the modal call across that cell's seeds; a tie with no "
            "modal winner would be resolved by treating the cell as dissenting",
    "note": "The rule never binds in these data: all four two-observation cells are unanimous and "
            "no three-observation cell lacks a modal winner."}
out["item3b_dissent_rule"] = {
    "construction": out["item8_canonical"]["construction"],
    "by_threshold_c": {str(c_): metrics((D2.d >= c_).astype(int).values)
                       for c_ in (1, 2, 3, 4, 6, 8)},
    "and_gate_d_ge_1_and_near_w1": metrics(((D2.d >= 1) & (D2.near)).astype(int).values),
    "note": "d>=3 attains precision 1.000 with a flat net benefit of 0.6667 and so dominates "
            "d>=1 once referral is costly. Conjoining near-boundary status with dissent cuts "
            "recall to 0.176, so near-boundary status is reported as a severity indicator rather "
            "than a mandatory gate."}
i3 = out["item3b_dissent_rule"]
print(f"  [2b] two-obs cells {len(short)}, disagreeing {no_modal_2}, no-modal 3-obs {no_modal_3}")
for c_, v in i3["by_threshold_c"].items():
    print(f"  [3b] d>={c_}: prec {v['precision']} recall {v['recall']} referred {v['referred_share']} "
          f"NB.60 {v['net_benefit']['0.60']}")
g = i3["and_gate_d_ge_1_and_near_w1"]
print(f"  [3b] d>=1 AND near(w=1): recall {g['recall']} referred {g['referred_share']}")

json.dump(out, open(PB / "results/results_canonical_fixes.json", "w"), indent=1)
print("\n  -> results/results_canonical_fixes.json")
