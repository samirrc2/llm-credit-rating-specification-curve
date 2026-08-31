#!/usr/bin/env python3
"""Extended offline analyses for the ISWA revision (deterministic, seed 42; no API calls).
Computes and writes results/results_extended.json:
  A2  score validation: does the specification-instability score, fit on a calibration
      half of the specs, predict held-out IG/HY instability? (Spearman + ROC-AUC + AP)
  B1  self-consistency curve: residual per-comparison IG/HY flip after a k-of-n majority
      vote, for k = 1,3,5,9,15
  B5  ordinal-weighted agreement (linear + quadratic) and Krippendorff's alpha (ordinal),
      as robustness for the unweighted Fleiss kappa on 21 categories
  B6  IG/HY flip share by benchmark stratum (SAFE / WATCH / DISTRESS)
  B8  flagship credit-band accuracy vs Altman (with nano/flash comparison)
  A4  per-issuer deployment cost of the score at each k
"""
from __future__ import annotations
import json, glob
from pathlib import Path
from collections import Counter
from itertools import combinations
import numpy as np
import pandas as pd

PB = Path(__file__).resolve().parents[1]
RS = json.load(open(PB / "data" / "frozen" / "main" / "rating_scale.json"))
LETTERS = RS["letter_scale"]; LRANK = {l: i for i, l in enumerate(LETTERS)}
IGHY = RS["letter_to_ig_hy"]
rng = np.random.default_rng(42)

P = pd.read_parquet(PB / "data" / "panel" / "panel.parquet")
P = P[P.provider.isin(["openai", "google"])]
CR = P[(P.family == "credit_health") & (P.parse_rule == "lenient") & P.decision.notna()].copy()
CR["ighy"] = CR.dec_letter.map(IGHY)
CR["rank"] = CR.dec_letter.map(LRANK)
out = {"_meta": {"credit_rows": int(len(CR)), "items": int(CR.item_id.nunique()),
                 "specs": int(CR.spec_id.nunique()), "seed": 42}}

def simpson_flip(vals):
    n = len(vals)
    if n < 2: return np.nan
    p = np.array(list(Counter(vals).values())) / n
    return 1 - float((p ** 2).sum())

# ---------- A2: score validation on a calibration/validation spec split ----------
specs = sorted(CR.spec_id.unique())
calib = set(specs[0::2]); valid = set(specs[1::2])            # deterministic interleaved 16/16 split
rows = []
for it, g in CR.groupby("item_id"):
    c = g[g.spec_id.isin(calib)].ighy.tolist()
    v = g[g.spec_id.isin(valid)].ighy.tolist()
    if len(c) < 2 or len(v) < 2: continue
    rows.append({"item": it, "score_calib": simpson_flip(c),
                 "heldout_flip": simpson_flip(v),
                 "heldout_any_flip": int(len(set(v)) > 1)})
val = pd.DataFrame(rows)
def spearman(a, b):
    ra, rb = pd.Series(a).rank(), pd.Series(b).rank()
    return float(np.corrcoef(ra, rb)[0, 1])
def auc(score, label):
    pos = score[label == 1]; neg = score[label == 0]
    if len(pos) == 0 or len(neg) == 0: return None
    return float(np.mean([ (p > n) + 0.5 * (p == n) for p in pos for n in neg ]))
def avg_precision(score, label):
    order = np.argsort(-score); lab = label[order]; tp = np.cumsum(lab)
    prec = tp / (np.arange(len(lab)) + 1); rec = tp / lab.sum()
    ap = 0.0; prev = 0.0
    for i in range(len(lab)):
        if lab[i]: ap += prec[i]
    return float(ap / lab.sum())
lab = val.heldout_any_flip.values
base_auc = auc(val.score_calib.values, lab)

# issuer-clustered bootstrap 95% CI on the AUC (resample the 45 issuers; fixed split)
sc = val.score_calib.values
b_auc = []
for _ in range(1000):
    idx = rng.integers(0, len(val), len(val))
    a = auc(sc[idx], lab[idx])
    if a is not None: b_auc.append(a)
auc_ci = [round(float(np.percentile(b_auc, 2.5)), 3), round(float(np.percentile(b_auc, 97.5)), 3)]

# split-sensitivity: repeated balanced random 16/16 spec splits; recompute AUC each
item_spec = {it: {sp: g[g.spec_id == sp].ighy.tolist() for sp in specs}
             for it, g in CR.groupby("item_id")}
split_aucs = []
for _ in range(300):
    perm = list(specs); rng.shuffle(perm)
    cset, vset = set(perm[:len(perm)//2]), set(perm[len(perm)//2:])
    ss, ll = [], []
    for it, sm in item_spec.items():
        c = [x for sp in cset for x in sm[sp]]; v = [x for sp in vset for x in sm[sp]]
        if len(c) < 2 or len(v) < 2: continue
        ss.append(simpson_flip(c)); ll.append(int(len(set(v)) > 1))
    ss, ll = np.array(ss), np.array(ll)
    a = auc(ss, ll)
    if a is not None: split_aucs.append(a)
split_aucs = np.array(split_aucs)

out["A2.score_validation"] = {
    "n_items": int(len(val)),
    "spearman_calibscore_vs_heldoutflip": round(spearman(val.score_calib, val.heldout_flip), 3),
    "roc_auc_flag_heldout_flip": round(base_auc, 3),
    "roc_auc_CI95_issuer_bootstrap": auc_ci,
    "roc_auc_repeated_splits_median": round(float(np.median(split_aucs)), 3),
    "roc_auc_repeated_splits_IQR": [round(float(np.percentile(split_aucs, 25)), 3),
                                    round(float(np.percentile(split_aucs, 75)), 3)],
    "roc_auc_repeated_splits_range": [round(float(split_aucs.min()), 3), round(float(split_aucs.max()), 3)],
    "avg_precision": round(avg_precision(val.score_calib.values, lab), 3),
    "heldout_flip_base_rate": round(float(lab.mean()), 3),
    "note": "score fit on 16 calibration specs; label/flip on the disjoint 16 validation specs; "
            "issuer-clustered bootstrap CI (1000) and 300 balanced random splits for split-sensitivity"}

# ---------- A2b: EXTERNAL validation on the 31 decontaminated REAL issuers -----------
# Same held-out-specification validation, but on real firms (arm_runs), not synthetic profiles.
ARM = sorted(glob.glob(str(PB / "data" / "raw" / "realarm" / "arm_runs" / "run_*" / "arm_panel.json")))[-1]
arm = json.load(open(ARM))["rows"]
aspecs = sorted(set(r["spec_id"] for r in arm))
acal, aval = set(aspecs[0::2]), set(aspecs[1::2])            # 6/6 interleaved split
byiss = {}
for r in arm:
    let = r.get("parsed_letter"); ig = IGHY.get(let) if let else None
    if ig is None: continue
    byiss.setdefault(r["item_id"], {}).setdefault(r["spec_id"], []).append(ig)
arows = []
for it, sm in byiss.items():
    c = [x for sp in acal for x in sm.get(sp, [])]
    v = [x for sp in aval for x in sm.get(sp, [])]
    if len(c) < 2 or len(v) < 2: continue
    arows.append((simpson_flip(c), simpson_flip(v), int(len(set(v)) > 1)))
asc = np.array([r[0] for r in arows]); ahf = np.array([r[1] for r in arows]); alab = np.array([r[2] for r in arows])
a_auc = auc(asc, alab)
ab = []
for _ in range(1000):
    idx = rng.integers(0, len(asc), len(asc)); aa = auc(asc[idx], alab[idx])
    if aa is not None: ab.append(aa)
out["A2b.real_issuer_validation"] = {
    "n_real_issuers": int(len(arows)),
    "spearman_calibscore_vs_heldoutflip": round(spearman(pd.Series(asc), pd.Series(ahf)), 3),
    "roc_auc_flag_heldout_flip": (round(a_auc, 3) if a_auc is not None else None),
    "roc_auc_CI95_issuer_bootstrap": ([round(float(np.percentile(ab, 2.5)), 3), round(float(np.percentile(ab, 97.5)), 3)] if ab else None),
    "heldout_flip_base_rate": round(float(alab.mean()), 3),
    "note": "held-out-specification validation on the 31 real decontaminated issuers (arm_runs, 12 specs "
            "split 6/6, 3 seeds); external-issuer generalization of the synthetic-battery validation"}

# ---------- B1: self-consistency curve (residual flip after k-of-n majority vote) ----
# For each item, p=P(IG). A k-vote returns IG if >half of k draws are IG; ties (even k) broken at random
# in expectation. Residual per-comparison flip = mean over items of 2 q (1-q), q=P(k-vote=IG).
from math import comb
def q_majority(p, k):
    q = 0.0
    for j in range(k + 1):
        w = comb(k, j) * p ** j * (1 - p) ** (k - j)
        if j > k / 2: q += w
        elif j == k / 2: q += 0.5 * w      # tie
    return q
p_ig = CR.groupby("item_id").ighy.apply(lambda s: float((s == "IG").mean()))
curve = {}
for k in (1, 3, 5, 9, 15):
    qs = p_ig.apply(lambda p: q_majority(p, k))
    curve[k] = round(float((2 * qs * (1 - qs)).mean()), 4)
out["B1.self_consistency_residual_flip_by_k"] = curve

# ---------- B5: ordinal-weighted agreement + Krippendorff alpha (ordinal) -----------
# units = items; values = letter ranks across all (spec,seed). Coincidence-based Krippendorff.
def krippendorff_alpha(groups, metric):
    # groups: list of arrays of ranks per unit. metric(a,b)->distance
    Do_num = Do_den = 0.0
    allv = []
    for g in groups:
        m = len(g)
        if m < 2: continue
        for a, b in combinations(g, 2):
            Do_num += 2 * metric(a, b)   # ordered pairs
        Do_den += m * (m - 1)
        allv.extend(g)
    allv = np.array(allv)
    Do = Do_num / Do_den
    # expected: over all pairs of values in the pooled coincidence
    N = len(allv)
    # sample-based expected distance
    idx = rng.integers(0, N, size=200000)
    jdx = rng.integers(0, N, size=200000)
    De = float(np.mean([metric(allv[i], allv[j]) for i, j in zip(idx, jdx)]))
    return 1 - Do / De if De > 0 else np.nan
groups = [g.values for _, g in CR.groupby("item_id")["rank"]]
lin = lambda a, b: abs(a - b)
quad = lambda a, b: (a - b) ** 2
out["B5.weighted_agreement"] = {
    "krippendorff_alpha_linear": round(float(krippendorff_alpha(groups, lin)), 3),
    "krippendorff_alpha_quadratic": round(float(krippendorff_alpha(groups, quad)), 3),
    "note": "letter-rank scale (0-20); ordinal-weighted; complements unweighted Fleiss kappa"}

# ---------- B6: IG/HY flip by benchmark stratum ------------------------------------
strat = {}
for band, g in CR.groupby("bench_band"):
    per = g.groupby("item_id").ighy.apply(lambda s: simpson_flip(s.tolist()))
    strat[str(band)] = {"ighy_flip": round(float(per.mean()), 4), "n_items": int(per.shape[0])}
out["B6.ighy_flip_by_stratum"] = strat

# ---------- B8: flagship band accuracy vs Altman (+ nano/flash) --------------------
def band_of(letter): return RS["letter_to_band"].get(letter)
def band_accuracy(rows):
    ok = tot = 0
    for r in rows:
        let = r.get("parsed_letter"); b = band_of(let) if let else None
        bench = r.get("benchmark_label")
        if b is None or bench is None: continue
        tot += 1; ok += int(b == bench)
    return round(ok / tot, 4), tot
fg = json.load(open(sorted(glob.glob(str(PB / "capture" / "flagship_runs" / "run_*" / "flagship_panel.json")))[-1]))["rows"]
nf = json.load(open(PB / "data" / "raw" / "realarm" / "battery_comp_runs" / "run_20260710_102711" / "arm_panel.json"))["rows"]
fa, ft = band_accuracy(fg); na, nt = band_accuracy(nf)
out["B8.band_accuracy_vs_altman"] = {"flagship": fa, "flagship_n": ft, "nano_flash": na, "nano_flash_n": nt,
    "ig_rate_flagship": round(float(np.mean([IGHY.get(r.get("parsed_letter")) == "IG" for r in fg if r.get("parsed_letter")])), 4),
    "ig_rate_nano_flash": round(float(np.mean([IGHY.get(r.get("parsed_letter")) == "IG" for r in nf if r.get("parsed_letter")])), 4)}

# ---------- A4: per-issuer deployment cost of the score at each k -------------------
def per_call(rows):
    u = [r.get("usd", 0) for r in rows]; i = [r.get("in_tok", 0) for r in rows]; o = [r.get("out_tok", 0) for r in rows]
    return float(np.mean(u)), float(np.mean(i)), float(np.mean(o))
cf, cfi, cfo = per_call(fg); cn, cni, cno = per_call(nf)
cost = {}
for k in (1, 3, 5, 9, 15):
    cost[k] = {"nano_flash_usd_per_1000_issuers": round(cn * k * 1000, 2),
               "flagship_usd_per_1000_issuers": round(cf * k * 1000, 2),
               "tokens_per_issuer_nano": int((cni + cno) * k)}
out["A4.deployment_cost"] = {"per_call_usd": {"nano_flash": round(cn, 5), "flagship": round(cf, 5)}, "by_k": cost}

# ---------- D7: mean per-issuer letter-rating entropy (within-firm spread) -----------
def _entropy(vals):
    n = len(vals)
    if n < 1: return 0.0
    p = np.array(list(Counter(vals).values())) / n
    return float(-(p * np.log2(p)).sum())
per_item_ent = CR.groupby("item_id").dec_letter.apply(lambda s: _entropy(s.tolist()))
out["D7.rating_entropy_bits"] = {
    "per_item_mean": round(float(per_item_ent.mean()), 3),
    "pooled": round(float(_entropy(CR.dec_letter.tolist())), 3),
    "max_bits_21_grades": round(float(np.log2(21)), 3),
    "note": "mean within-firm letter-rating entropy across the 45 credit items (post-hoc)"}

(PB / "results").mkdir(exist_ok=True)
(PB / "results" / "results_extended.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
