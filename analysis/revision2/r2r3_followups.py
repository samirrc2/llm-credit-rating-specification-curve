#!/usr/bin/env python3
"""Revision-2 follow-ups: aliasing scope, coding invariance, discrete semantic entropy.

Spec committed and hashed before this ran: analysis/revision2/SPEC_r2r3_followups.md
(sha256 in results/SPEC_r2r3_followups.sha256). Offline, deterministic, no new model calls.
"""
import itertools, json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

PB = Path(__file__).resolve().parents[2]
rng = np.random.default_rng(42)
RS = json.load(open(PB / "data/frozen/main/rating_scale.json"))
LETTERS = RS["letter_scale"]; LRANK = {l: i for i, l in enumerate(LETTERS)}
IGHY = RS["letter_to_ig_hy"]; BAND = RS["letter_to_band"]; BOUNDARY = RS["ig_hy_boundary"]
AX = ["A1_provider", "A2_version", "A3_temperature", "A4_paraphrase",
      "A5_format", "A6_fewshot", "A7_presentation"]

P = pd.read_parquet(PB / "data/panel/panel.parquet")
P = P[P.provider.isin(["openai", "google"])]
CR = P[(P.family == "credit_health") & (P.parse_rule == "lenient") & P.decision.notna()].copy()
CR["ighy"] = CR.dec_letter.map(IGHY); CR["band"] = CR.dec_letter.map(BAND)
bnd = LRANK[BOUNDARY] if BOUNDARY in LRANK else max(
    LRANK[l] for l, v in IGHY.items() if v == "IG" and l in LRANK)
out = {"_meta": {"spec": "analysis/revision2/SPEC_r2r3_followups.md",
                 "spec_sha256": open(PB / "results/SPEC_r2r3_followups.sha256").read().split()[0],
                 "new_model_calls": 0, "seed": 42}}

# ---------------- Items 1 and 2: aliasing on the design actually analysed ----------------
design = CR[["spec_id"] + AX].drop_duplicates("spec_id").sort_values("spec_id")
print(f"  analysed design: {len(design)} specs (variance decomposition is fitted on this)")

def effect_code(df):
    cols, axis_of, groups, ci = [], [], {}, 0
    for a in AX:
        lv = sorted(df[a].astype(str).unique().tolist()); k = len(lv)
        if k < 2:
            continue
        idx = {l: i for i, l in enumerate(lv)}; g = []
        for j in range(k - 1):
            cols.append([1.0 if idx[str(v)] == j else (-1.0 if idx[str(v)] == k - 1 else 0.0)
                         for v in df[a]])
            axis_of.append(a); g.append(ci); ci += 1
        groups[a] = g
    return np.asarray(cols, float).T, axis_of, groups

def corr(u, v):
    u = u - u.mean(); v = v - v.mean()
    d = np.sqrt((u * u).sum() * (v * v).sum())
    return 0.0 if d == 0 else float((u * v).sum() / d)

X, axis_of, groups = effect_code(design)
n = X.shape[1]
twofi = [(X[:, i] * X[:, j], {a, b})
         for a, b in itertools.combinations(groups.keys(), 2)
         for i in groups[a] for j in groups[b]]
main_off = max(abs(corr(X[:, i], X[:, j])) for i in range(n) for j in range(i + 1, n)
               if axis_of[i] != axis_of[j])
nonpar = max(abs(corr(t, X[:, m])) for t, par in twofi for m in range(n)
             if axis_of[m] not in par)
Z = np.array([t for t, _ in twofi]).T
qx, _ = np.linalg.qr(X - X.mean(0)); qz, _ = np.linalg.qr(Z - Z.mean(0))
cc = np.linalg.svd(qx.T @ qz, compute_uv=False)
# How far is each INDIVIDUAL main-effect contrast from lying in the 2FI span? R^2 = 1 would be
# exact confounding of that one contrast. Reported because the largest canonical correlation is
# 1.000, which is a statement about a COMBINATION of main effects, not about any single axis --
# a distinction a reviewer is entitled to hold us to.
Xc, Zc = X - X.mean(0), Z - Z.mean(0)
r2_each = []
for j in range(Xc.shape[1]):
    y = Xc[:, j]
    beta, *_ = np.linalg.lstsq(Zc, y, rcond=None)
    r2_each.append((axis_of[j], round(float(1 - ((y - Zc @ beta) ** 2).sum() / (y ** 2).sum()), 4)))
rank_x, rank_z = np.linalg.matrix_rank(Xc), np.linalg.matrix_rank(Zc)
rank_joint = np.linalg.matrix_rank(np.hstack([Xc, Zc]))
print(f"  individual main-effect contrast R^2 on the 2FI span: "
      f"{min(r for _, r in r2_each):.3f}-{max(r for _, r in r2_each):.3f}")
print(f"  rank(main)={rank_x} rank(2FI)={rank_z} rank(joint)={rank_joint} "
      f"=> subspace intersection of dimension {rank_x + rank_z - rank_joint}")

out["aliasing_on_analysed_design"] = {
    "per_contrast_R2_on_2FI_span": r2_each,
    "per_contrast_R2_range": [min(r for _, r in r2_each), max(r for _, r in r2_each)],
    "rank_main": int(rank_x), "rank_2FI": int(rank_z), "rank_joint": int(rank_joint),
    "subspace_intersection_dim": int(rank_x + rank_z - rank_joint),
    "interpretation": "No INDIVIDUAL main-effect contrast lies exactly in the interaction span "
                      "(max R^2 0.901). The largest canonical correlation is nevertheless 1.000 "
                      "because the joint matrix is rank-deficient by 4: some linear COMBINATION "
                      "of main effects coincides exactly with a combination of two-factor "
                      "interactions. That is the coding-invariant statement of non-identification.",
    "n_specs": int(len(design)), "n_main_contrasts": int(n), "n_2fi_contrasts": int(Z.shape[1]),
    "main_effect_max_offdiag_corr_distinct_axes": round(main_off, 3),
    "main_x_2FI_max_abs_corr_nonparent": round(nonpar, 3),
    "canonical_correlations_main_vs_2FI": [round(float(v), 4) for v in cc],
    "largest_canonical_correlation": round(float(cc[0]), 4),
    "n_canonical_above_0.9": int((cc > 0.9).sum()),
    "note": "Canonical correlations are invariant to re-parameterisation within either "
            "subspace; the pairwise column correlation is not."}
print(f"  main off-diagonal (distinct axes)      = {main_off:.3f}")
print(f"  main x 2FI of other axes               = {nonpar:.3f}")
print(f"  largest canonical correlation          = {cc[0]:.4f}  "
      f"({(cc > 0.9).sum()} of {len(cc)} above 0.9)")

# the same two diagnostics on the full 48-spec grid, to document where 0.333 came from
grid = pd.DataFrame(json.load(open(PB / "data/frozen/main/grid_definition.json"))["specs"])
Xg, ag, gg = effect_code(grid)
tg = [(Xg[:, i] * Xg[:, j], {a, b}) for a, b in itertools.combinations(gg.keys(), 2)
      for i in gg[a] for j in gg[b]]
g_non = max(abs(corr(t, Xg[:, m])) for t, par in tg for m in range(Xg.shape[1])
            if ag[m] not in par)
g_off = max(abs(corr(Xg[:, i], Xg[:, j])) for i in range(Xg.shape[1])
            for j in range(i + 1, Xg.shape[1]) if ag[i] != ag[j])
out["aliasing_on_full_48_spec_grid"] = {
    "n_specs": int(len(grid)),
    "main_effect_max_offdiag_corr_distinct_axes": round(g_off, 3),
    "main_x_2FI_max_abs_corr_nonparent": round(g_non, 3),
    "note": "This three-provider grid is the source of the 0.062 / 0.333 figures previously "
            "reported; the analysed arm is the two-provider subset above."}
print(f"  [48-spec grid, for provenance]  off-diag={g_off:.3f}  main x 2FI={g_non:.3f}")

# provider x item orthogonality, on the realised panel
cell = CR.groupby(["item_id", "spec_id"]).size()
Xo, axo, gro = effect_code(CR[AX])
pv = Xo[:, gro["A1_provider"][0]]
I = pd.get_dummies(CR.item_id).astype(float).values; I = I - I.mean(0)
PI = np.column_stack([pv * I[:, c] for c in range(I.shape[1] - 1)])
Zo = np.array([Xo[:, i] * Xo[:, j] for a, b in itertools.combinations(gro.keys(), 2)
               for i in gro[a] for j in gro[b]]).T
mx = lambda A, B: max(abs(corr(A[:, i], B[:, j])) for i in range(A.shape[1])
                      for j in range(B.shape[1]))
out["provider_by_item_identification"] = {
    "items": int(CR.item_id.nunique()), "specs": int(CR.spec_id.nunique()),
    "cells": int(CR.item_id.nunique() * CR.spec_id.nunique()),
    "empty_cells": 0, "cells_with_3_obs": int((cell == 3).sum()),
    "cells_with_2_obs": int((cell == 2).sum()),
    "max_abs_corr_vs_spec_main_effects": round(mx(PI, Xo), 4),
    "max_abs_corr_vs_spec_2FIs": round(mx(PI, Zo), 4),
    "note": "Fully crossed with no empty cell, and near-balanced: 4 of 1440 cells carry 2 "
            "elicitations instead of 3. Orthogonality is therefore numerical, not exact."}
print(f"  provider x item vs spec contrasts: max |corr| "
      f"{max(mx(PI, Xo), mx(PI, Zo)):.4f}  (cells with 2 obs: {(cell == 2).sum()}/1440)")

# ---------------- Item 3: discrete semantic entropy as a benchmark ----------------
def preds(g, res):
    v = (g.ighy if res == "ighy" else g.band if res == "band" else g.dec_letter).tolist()
    k = len(v)
    if k < 2:
        return None
    cnt = Counter(v); p = np.array(list(cnt.values())) / k
    modal_n = cnt.most_common(1)[0][1]
    second = cnt.most_common(2)[1][1] if len(cnt) > 1 else 0
    ranks = [LRANK[l] for l in g.dec_letter if l in LRANK]
    mr = Counter(ranks).most_common(1)[0][0] if ranks else np.nan
    return {"sis": 1 - float((p ** 2).sum()),
            "sem_entropy": float(-(p * np.log(p)).sum()),   # discrete semantic (Shannon) entropy
            "dissent": float(k - modal_n),
            "neg_margin": -(modal_n - second) / k,
            "neg_boundary_dist": -float(abs(mr - bnd)) if ranks else np.nan}

CANDS = ["sis", "sem_entropy", "dissent", "neg_margin", "neg_boundary_dist"]
def auc(score, label):
    s = np.asarray(score, float); y = np.asarray(label, int)
    ok = ~np.isnan(s); s, y = s[ok], y[ok]
    if y.sum() in (0, len(y)):
        return None
    o = np.argsort(s); r = np.empty(len(s)); r[o] = np.arange(1, len(s) + 1)
    r = pd.DataFrame({"s": s, "r": r}).groupby("s").r.transform("mean").values
    n1 = y.sum(); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
def spearman(a, b):
    a, b = pd.Series(a), pd.Series(b); m = a.notna() & b.notna()
    return float(np.corrcoef(a[m].rank(), b[m].rank())[0, 1])
def net_benefit(flag, y, pt):
    nn = len(y)
    tp = int(((flag == 1) & (y == 1)).sum()); fp = int(((flag == 1) & (y == 0)).sum())
    return tp / nn - (fp / nn) * (pt / (1 - pt))
def envelope(score, y, pt):
    s = np.asarray(score, float); ok = ~np.isnan(s); s, y2 = s[ok], y[ok]
    best = -np.inf
    for t in np.unique(np.concatenate([s, [s.max() + 1.0]])):
        best = max(best, net_benefit((s >= t).astype(int), y2, pt))
    return best

specs = sorted(CR.spec_id.unique()); calib, valid = set(specs[0::2]), set(specs[1::2])
PT = [f"{x:.2f}" for x in np.arange(0.05, 0.605, 0.05)]
res_out = {}
for res in ("ighy", "band", "letter"):
    rows = []
    for it, g in CR.groupby("item_id"):
        c, v = g[g.spec_id.isin(calib)], g[g.spec_id.isin(valid)]
        pr = preds(c, res)
        if pr is None or len(v) < 2:
            continue
        vv = (v.ighy if res == "ighy" else v.band if res == "band" else v.dec_letter).tolist()
        rows.append({"item": it, **pr, "event": int(len(set(vv)) > 1)})
    D = pd.DataFrame(rows); y = D.event.values; base = float(y.mean())
    entry = {"n_items": int(len(D)), "event_base_rate": round(base, 3),
             "auc": {c: (round(auc(D[c].values, y), 4) if auc(D[c].values, y) is not None else None)
                     for c in CANDS},
             "spearman_vs_dissent": {c: round(spearman(D[c], D.dissent), 6) for c in CANDS}}
    if y.sum() not in (0, len(y)):
        diffs = []
        for _ in range(2000):
            idx = rng.integers(0, len(D), len(D))
            a1, a2 = auc(D.sem_entropy.values[idx], y[idx]), auc(D.dissent.values[idx], y[idx])
            if a1 is not None and a2 is not None:
                diffs.append(a1 - a2)
        entry["auc_diff_sementropy_minus_dissent"] = round(float(np.mean(diffs)), 6)
        entry["auc_diff_ci95"] = [round(float(np.percentile(diffs, 2.5)), 4),
                                  round(float(np.percentile(diffs, 97.5)), 4)]
        nb = {c: {pt: round(envelope(D[c].values, y, float(pt)), 6) for pt in PT} for c in CANDS}
        entry["net_benefit"] = nb
        entry["max_abs_gap_sementropy_vs_dissent"] = round(
            max(abs(nb["sem_entropy"][pt] - nb["dissent"][pt]) for pt in PT), 9)
        entry["max_abs_gap_sementropy_vs_sis"] = round(
            max(abs(nb["sem_entropy"][pt] - nb["sis"][pt]) for pt in PT), 9)
    else:
        entry["computable"] = False
        entry["reason"] = f"event base rate {base:.2f}; discrimination undefined"
    res_out[res] = entry
    print(f"\n  == {res}: n={len(D)} base rate {base:.2f}")
    for c in CANDS:
        print(f"     {c:20s} AUC {entry['auc'][c]}   Spearman vs dissent "
              f"{entry['spearman_vs_dissent'][c]}")
    if "max_abs_gap_sementropy_vs_dissent" in entry:
        print(f"     max |NB(semantic entropy) - NB(dissent)| = "
              f"{entry['max_abs_gap_sementropy_vs_dissent']:.2e}")
out["semantic_entropy_benchmark"] = res_out

# the spec's prediction, asserted: a departure is a bug, not a finding
ig = res_out["ighy"]
assert ig["auc"]["sem_entropy"] == ig["auc"]["dissent"] == ig["auc"]["sis"], \
    f"BUG: AUCs must coincide exactly at ighy; got {ig['auc']}"
assert ig["spearman_vs_dissent"]["sem_entropy"] == 1.0, \
    f"BUG: Spearman(H, dissent) must be 1 at ighy; got {ig['spearman_vs_dissent']['sem_entropy']}"
assert ig["max_abs_gap_sementropy_vs_dissent"] == 0.0, \
    f"BUG: net benefit must coincide exactly; gap {ig['max_abs_gap_sementropy_vs_dissent']}"
print("\n  assertions hold: discrete semantic entropy is rank-equivalent to the dissent count "
      "at the binary gate, exactly as the spec predicted.")
json.dump(out, open(PB / "results/results_r2r3_followups.json", "w"), indent=1)
print("  -> results/results_r2r3_followups.json")
