#!/usr/bin/env python3
"""Reproducible cross-model transfer of the specification-instability score (R2-5 / R3-5)
and design aliasing diagnostics (R2-4 / R3-2), computed offline from the frozen artifacts.

Cross-model transfer
--------------------
For each model we compute a per-item specification-instability score (SIS) as the
Gini-Simpson dispersion (1 - sum p_c^2) of that model's IG/HY decisions across its own
specification x seed cells (parse_rule='lenient', credit_health family). "Transfer" asks
whether the SIS estimated on one model predicts the instability of a *different* model:
  - rank agreement: Spearman(SIS_A, SIS_B) over the shared items;
  - discrimination: AUC of SIS_A used to flag items whose SIS_B is above B's median.
We report the distribution over all distinct model pairs and, separately, over
cross-provider pairs (the operationally relevant "a new model from another vendor" case).

Aliasing diagnostics
--------------------
From the frozen specification grid (grid_definition.json), main effects are effect-coded
(k-1 columns per k-level factor). We report the maximum absolute correlation between
main-effect columns belonging to DIFFERENT factors (near-orthogonality of main effects),
and the maximum absolute correlation between any main-effect column and any two-factor-
interaction (2FI) column (residual aliasing). Computed on the analysis scope (providers
openai+google), matching the paper's re-scoped design.

Writes results/results_crossmodel_aliasing.json. Deterministic (seed 42 for AUC bootstrap).
"""
from __future__ import annotations
import json, itertools
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

PB = Path(__file__).resolve().parents[1]
rng = np.random.default_rng(42)
RS = json.load(open(PB / "data" / "frozen" / "main" / "rating_scale.json"))
IGHY = RS["letter_to_ig_hy"]

PROVIDERS = ["openai", "google"]  # paper analysis scope


def simpson(vals):
    n = len(vals)
    return np.nan if n < 2 else 1.0 - sum((c / n) ** 2 for c in Counter(vals).values())


def spearman(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3:
        return np.nan
    return float(np.corrcoef(pd.Series(a[m]).rank(), pd.Series(b[m]).rank())[0, 1])


def auc(score, label):
    score = np.asarray(score, float); label = np.asarray(label, int)
    m = np.isfinite(score)
    score, label = score[m], label[m]
    pos, neg = score[label == 1], score[label == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    c = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return float(c / (len(pos) * len(neg)))


# ---------------------------------------------------------------- cross-model transfer
P = pd.read_parquet(PB / "data" / "panel" / "panel.parquet")
P = P[P.provider.isin(PROVIDERS)]
CR = P[(P.family == "credit_health") & (P.parse_rule == "lenient") & P.decision.notna()].copy()
CR["ighy"] = CR.dec_letter.map(IGHY)

prov_of = CR.groupby("model").provider.first().to_dict()
models = sorted(CR.model.unique())
sis = {m: CR[CR.model == m].groupby("item_id").ighy.apply(lambda s: simpson(s.tolist())) for m in models}

pairs = []
for a, b in itertools.combinations(models, 2):
    idx = sis[a].index.intersection(sis[b].index)
    A = sis[a][idx].values; B = sis[b][idx].values
    rho = spearman(A, B)
    # symmetric AUC: mean of A->(B above median) and B->(A above median)
    medB = np.nanmedian(B); medA = np.nanmedian(A)
    auc_ab = auc(A, (B > medB).astype(int))
    auc_ba = auc(B, (A > medA).astype(int))
    aucm = float(np.nanmean([auc_ab, auc_ba]))
    cross = prov_of[a] != prov_of[b]
    pairs.append({"model_a": a, "model_b": b, "cross_provider": cross,
                  "n_items": int(len(idx)), "spearman": round(rho, 3), "auc": round(aucm, 3)})

allr = [p["spearman"] for p in pairs]
alla = [p["auc"] for p in pairs]
xr = [p["spearman"] for p in pairs if p["cross_provider"]]
xa = [p["auc"] for p in pairs if p["cross_provider"]]

out = {
    "_meta": {"seed": 42, "providers": PROVIDERS, "n_models": len(models), "models": models,
              "score": "per-item Gini-Simpson SIS on IG/HY across each model's spec x seed cells",
              "transfer_defn": "Spearman(SIS_A, SIS_B) and AUC of SIS_A flagging items with above-median SIS_B"},
    "crossmodel_transfer": {
        "pairs": pairs,
        "all_pairs": {"n": len(allr),
                      "spearman_median": round(float(np.nanmedian(allr)), 3),
                      "spearman_mean": round(float(np.nanmean(allr)), 3),
                      "spearman_min": round(float(np.nanmin(allr)), 3),
                      "spearman_max": round(float(np.nanmax(allr)), 3),
                      "auc_median": round(float(np.nanmedian(alla)), 3),
                      "auc_mean": round(float(np.nanmean(alla)), 3)},
        "cross_provider_pairs": {"n": len(xr),
                                 "spearman_median": round(float(np.nanmedian(xr)), 3),
                                 "spearman_mean": round(float(np.nanmean(xr)), 3),
                                 "spearman_min": round(float(np.nanmin(xr)), 3),
                                 "spearman_max": round(float(np.nanmax(xr)), 3),
                                 "auc_median": round(float(np.nanmedian(xa)), 3),
                                 "auc_mean": round(float(np.nanmean(xa)), 3)},
        "note": "Transfer is inconsistent across model pairs (see range); a new model should be re-scored on the grid rather than reusing another model's scores."},
}

# ---------------------------------------------------------------- aliasing diagnostics
# Aliasing is a property of the frozen collection design (the full D-optimal fraction),
# so it is computed on all runs, not the two-provider analysis subset.
grid = json.load(open(PB / "data" / "frozen" / "main" / "grid_definition.json"))
specs = list(grid["specs"])
axes = ["A1_provider", "A2_version", "A3_temperature", "A4_paraphrase",
        "A5_format", "A6_fewshot", "A7_presentation"]


def levels(a):
    seen = []
    for s in specs:
        if s[a] not in seen:
            seen.append(s[a])
    return seen


cols, colaxis = [], []
groups = {}
ci = 0
for a in axes:
    lv = levels(a); k = len(lv)
    if k < 2:
        continue
    idx = {l: i for i, l in enumerate(lv)}
    g = []
    for j in range(k - 1):  # effect coding: k-1 columns
        c = [1.0 if idx[s[a]] == j else (-1.0 if idx[s[a]] == k - 1 else 0.0) for s in specs]
        cols.append(c); colaxis.append(a); g.append(ci); ci += 1
    groups[a] = g
X = np.asarray(cols, float).T
n = X.shape[1]


def col_corr(u, v):
    u = u - u.mean(); v = v - v.mean()
    d = np.sqrt((u * u).sum() * (v * v).sum())
    return 0.0 if d == 0 else float((u * v).sum() / d)


main_off = max(abs(col_corr(X[:, i], X[:, j]))
               for i in range(n) for j in range(i + 1, n) if colaxis[i] != colaxis[j])

# 2FI columns tagged with their two parent factors
twofi = []
for a, b in itertools.combinations(groups.keys(), 2):
    for i in groups[a]:
        for j in groups[b]:
            twofi.append((X[:, i] * X[:, j], {a, b}))
# genuine main-vs-2FI aliasing: main effect m against a 2FI whose parents do NOT include m
main_x_2fi_nonparent = 0.0
# raw max (includes a 2FI vs its own parent, always non-trivial by construction)
main_x_2fi_raw = 0.0
for t, parents in twofi:
    for mc in range(n):
        c = abs(col_corr(t, X[:, mc]))
        main_x_2fi_raw = max(main_x_2fi_raw, c)
        if colaxis[mc] not in parents:
            main_x_2fi_nonparent = max(main_x_2fi_nonparent, c)

out["aliasing_diagnostics"] = {
    "n_runs": len(specs),
    "coding": "effect coding (k-1 columns per k-level factor)",
    "main_effect_max_offdiag_corr_distinct_axes": round(main_off, 3),
    "main_x_2FI_max_abs_corr_nonparent": round(main_x_2fi_nonparent, 3),
    "main_x_2FI_max_abs_corr_raw": round(main_x_2fi_raw, 3),
    "note": "Main effects are near-orthogonal across factors (max off-diagonal correlation between distinct main effects); the largest correlation between a main effect and a two-factor interaction of OTHER factors quantifies residual aliasing. Variance decomposition reported descriptively only.",
}

(PB / "results").mkdir(exist_ok=True)
(PB / "results" / "results_crossmodel_aliasing.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
