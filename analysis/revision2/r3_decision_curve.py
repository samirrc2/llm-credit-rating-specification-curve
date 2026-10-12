#!/usr/bin/env python3
"""R3 Concern #3 required action: decision-curve / net-benefit analysis for triage.

Spec committed and hashed before this ran: analysis/revision2/SPEC_r3_decision_curve.md
(sha256 in results/SPEC_r3_decision_curve.sha256). Offline, deterministic, no RNG, no new data.

The ighy-resolution result is PREDICTED by the spec, not discovered: SIS = 2(m/k)(1-m/k) is
strictly increasing in the dissent count m for m < k/2, so the two strategies' threshold families
generate identical flag sets and their net-benefit curves must coincide exactly. A non-zero gap
is a bug in this script. Asserted at the end.
"""
import json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

PB = Path(__file__).resolve().parents[2]
RS = json.load(open(PB / "data/frozen/main/rating_scale.json"))
LETTERS = RS["letter_scale"]; LRANK = {l: i for i, l in enumerate(LETTERS)}
IGHY = RS["letter_to_ig_hy"]; BAND = RS["letter_to_band"]; BOUNDARY = RS["ig_hy_boundary"]

P = pd.read_parquet(PB / "data/panel/panel.parquet")
P = P[P.provider.isin(["openai", "google"])]
CR = P[(P.family == "credit_health") & (P.parse_rule == "lenient") & P.decision.notna()].copy()
CR["ighy"] = CR.dec_letter.map(IGHY); CR["band"] = CR.dec_letter.map(BAND)
bnd = LRANK[BOUNDARY] if BOUNDARY in LRANK else max(
    LRANK[l] for l, v in IGHY.items() if v == "IG" and l in LRANK)
print(f"  panel {len(CR)} rows, {CR.item_id.nunique()} items, {CR.spec_id.nunique()} specs; "
      f"IG/HY boundary rank {bnd}")

def predictors(g, res):
    v = (g.ighy if res == "ighy" else g.band if res == "band" else g.dec_letter).tolist()
    k = len(v)
    if k < 2: return None
    cnt = Counter(v); p = np.array(list(cnt.values())) / k
    modal_n = cnt.most_common(1)[0][1]
    second = cnt.most_common(2)[1][1] if len(cnt) > 1 else 0
    ranks = [LRANK[l] for l in g.dec_letter if l in LRANK]
    mr = Counter(ranks).most_common(1)[0][0] if ranks else np.nan
    return {"sis": 1 - float((p ** 2).sum()), "dissent": float(k - modal_n),
            "neg_margin": -(modal_n - second) / k,
            "neg_boundary_dist": -float(abs(mr - bnd)) if ranks else np.nan}

CONT = ["sis", "dissent", "neg_margin", "neg_boundary_dist"]
PT = [round(x, 2) for x in np.arange(0.05, 0.605, 0.05)]

def net_benefit(flag, y, pt):
    """NB = TP/n - (FP/n)*(pt/(1-pt))"""
    n = len(y)
    tp = int(((flag == 1) & (y == 1)).sum()); fp = int(((flag == 1) & (y == 0)).sum())
    return tp / n - (fp / n) * (pt / (1 - pt))

def envelope(score, y, pt):
    """best attainable NB over this score's own thresholds (most favourable reading)"""
    s = np.asarray(score, float); ok = ~np.isnan(s)
    s2, y2 = s[ok], y[ok]
    best, best_thr = -np.inf, None
    for t in np.unique(np.concatenate([s2, [s2.max() + 1.0]])):
        nb = net_benefit((s2 >= t).astype(int), y2, pt)
        if nb > best + 1e-15: best, best_thr = nb, float(t)
    return best, best_thr

specs = sorted(CR.spec_id.unique()); calib, valid = set(specs[0::2]), set(specs[1::2])
out = {}
for res in ("ighy", "band", "letter"):
    rows = []
    for it, g in CR.groupby("item_id"):
        c, v = g[g.spec_id.isin(calib)], g[g.spec_id.isin(valid)]
        pr = predictors(c, res)
        if pr is None or len(v) < 2: continue
        vv = (v.ighy if res == "ighy" else v.band if res == "band" else v.dec_letter).tolist()
        rows.append({"item": it, **pr, "event": int(len(set(vv)) > 1)})
    D = pd.DataFrame(rows); y = D.event.values
    base = float(y.mean())
    if y.sum() in (0, len(y)):
        out[res] = {"n_items": int(len(D)), "event_base_rate": round(base, 3),
                    "computable": False,
                    "reason": f"event base rate is {base:.2f}; net benefit is degenerate because "
                              "flag_all is optimal at every pt"}
        print(f"\n  == {res}: n={len(D)}, base rate {base:.2f} -- DEGENERATE, not computable")
        continue
    curves = {c: {} for c in CONT}; curves["any_disagreement"] = {}
    curves["flag_all"] = {}; curves["flag_none"] = {}
    for pt in PT:
        for c in CONT:
            nb, thr = envelope(D[c].values, y, pt)
            curves[c][f"{pt:.2f}"] = round(nb, 6)
        curves["any_disagreement"][f"{pt:.2f}"] = round(
            net_benefit((D.sis.values > 0).astype(int), y, pt), 6)
        curves["flag_all"][f"{pt:.2f}"] = round(
            net_benefit(np.ones(len(y), int), y, pt), 6)
        curves["flag_none"][f"{pt:.2f}"] = 0.0
    gap = max(abs(curves["sis"][k] - curves["dissent"][k]) for k in curves["sis"])
    gap_m = max(abs(curves["sis"][k] - curves["neg_margin"][k]) for k in curves["sis"])
    gap_b = max(abs(curves["sis"][k] - curves["neg_boundary_dist"][k]) for k in curves["sis"])
    gap_a = max(abs(curves["sis"][k] - curves["any_disagreement"][k]) for k in curves["sis"])
    out[res] = {"n_items": int(len(D)), "event_base_rate": round(base, 3), "computable": True,
                "pt_grid": [f"{p:.2f}" for p in PT], "net_benefit": curves,
                "max_abs_gap_sis_vs_dissent": round(gap, 9),
                "max_abs_gap_sis_vs_vote_margin": round(gap_m, 6),
                "max_abs_gap_sis_vs_boundary_dist": round(gap_b, 6),
                "max_abs_gap_sis_vs_any_disagreement": round(gap_a, 6)}
    print(f"\n  == {res}: n={len(D)}, base rate {base:.2f}")
    print(f"     max |NB(SIS) - NB(dissent count)|      = {gap:.2e}")
    print(f"     max |NB(SIS) - NB(vote margin)|        = {gap_m:.6f}")
    print(f"     max |NB(SIS) - NB(boundary distance)|  = {gap_b:.6f}")
    print(f"     max |NB(SIS) - NB('any disagreement')| = {gap_a:.6f}")
    for pt in (0.10, 0.20, 0.30):
        k = f"{pt:.2f}"
        print(f"     pt={k}: SIS {curves['sis'][k]:+.4f}  dissent {curves['dissent'][k]:+.4f}  "
              f"any-dis {curves['any_disagreement'][k]:+.4f}  "
              f"bnd {curves['neg_boundary_dist'][k]:+.4f}  all {curves['flag_all'][k]:+.4f}")

# the spec's prediction, asserted -- a non-zero gap at binary resolution is a bug
if out["ighy"].get("computable"):
    g = out["ighy"]["max_abs_gap_sis_vs_dissent"]
    assert g == 0.0, f"BUG: SIS and dissent count must coincide exactly at ighy; gap {g}"
    print("\n  assertion holds: SIS and the dissent count have identical net-benefit curves "
          "at binary resolution, exactly, as the spec predicted.")

json.dump({"_meta": {"spec": "analysis/revision2/SPEC_r3_decision_curve.md",
                     "spec_sha256": open(PB / "results/SPEC_r3_decision_curve.sha256").read().split()[0],
                     "deterministic": True, "rng": None, "new_elicitations": 0,
                     "net_benefit": "TP/n - (FP/n)*(pt/(1-pt))",
                     "continuous_strategies": "upper envelope over the strategy's own thresholds"},
           "by_resolution": out}, open(PB / "results/results_r3_decision_curve.json", "w"), indent=1)
print("\n  -> results/results_r3_decision_curve.json")
