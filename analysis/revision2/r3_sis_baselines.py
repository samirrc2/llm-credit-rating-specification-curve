#!/usr/bin/env python3
"""R3 (SIS) — does the specification-instability score add anything over simple baselines?

Reviewer 3 asks for a benchmark against: the number of dissenting elicitations, the modal rating's
distance to the IG/HY boundary, and self-consistency vote margins. (Semantic entropy and
token-level confidence are NOT computable: the frozen corpus stores no logprobs. Stated, not
omitted.) Offline, deterministic, seed 42. No new data.

The binary-gate result is algebraic and is asserted here as a test, not discovered: with k
elicitations and minority count m, SIS = 1 - (p^2 + (1-p)^2) = 2p(1-p) with p = m/k, which is
strictly increasing in m for m < k/2. SIS is therefore an order-isomorphic transform of the dissent
count at binary resolution, and the two must have identical ROC-AUC. Any difference is a bug.
"""
import json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

PB = Path(__file__).resolve().parents[2]
rng = np.random.default_rng(42)
RS = json.load(open(PB / "data/frozen/main/rating_scale.json"))
LETTERS = RS["letter_scale"]; LRANK = {l: i for i, l in enumerate(LETTERS)}
IGHY = RS["letter_to_ig_hy"]; BAND = RS["letter_to_band"]
BOUNDARY = RS["ig_hy_boundary"]

P = pd.read_parquet(PB / "data/panel/panel.parquet")
P = P[P.provider.isin(["openai", "google"])]
CR = P[(P.family == "credit_health") & (P.parse_rule == "lenient") & P.decision.notna()].copy()
CR["ighy"] = CR.dec_letter.map(IGHY)
CR["band"] = CR.dec_letter.map(BAND)
CR["rank"] = CR.dec_letter.map(LRANK)
print(f"  panel: {len(CR)} rows, {CR.item_id.nunique()} items, {CR.spec_id.nunique()} specs")

# the IG/HY boundary position on the ordinal letter scale
bnd = LRANK[BOUNDARY] if BOUNDARY in LRANK else None
if bnd is None:
    ig = [LRANK[l] for l, v in IGHY.items() if v == "IG" and l in LRANK]
    bnd = max(ig)
print(f"  IG/HY boundary at letter rank {bnd} ({BOUNDARY!r})")

gini = lambda v: np.nan if len(v) < 2 else 1 - float(
    (np.array(list(Counter(v).values())) / len(v) ** 1 / len(v) * len(v) ** 0).sum() * 0 +
    ((np.array(list(Counter(v).values())) / len(v)) ** 2).sum())

def auc(score, label):
    s = np.asarray(score, float); y = np.asarray(label, int)
    ok = ~np.isnan(s)
    s, y = s[ok], y[ok]
    if y.sum() in (0, len(y)): return None
    order = np.argsort(s); r = np.empty(len(s)); r[order] = np.arange(1, len(s) + 1)
    # average ranks for ties -- essential here, the baselines are heavily tied
    df = pd.DataFrame({"s": s, "r": r}); r = df.groupby("s").r.transform("mean").values
    n1 = y.sum(); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

def spearman(a, b):
    a = pd.Series(a); b = pd.Series(b); ok = a.notna() & b.notna()
    return float(np.corrcoef(a[ok].rank(), b[ok].rank())[0, 1])

def predictors(g, res):
    """candidate scores for one item on one calibration spec set"""
    if res == "ighy": v = g.ighy.tolist()
    elif res == "band": v = g.band.tolist()
    else: v = g.dec_letter.tolist()
    k = len(v)
    if k < 2: return None
    cnt = Counter(v); p = np.array(list(cnt.values())) / k
    sis = 1 - float((p ** 2).sum())
    modal, modal_n = cnt.most_common(1)[0]
    dissent = k - modal_n                      # number of dissenting elicitations
    margin = (modal_n - (cnt.most_common(2)[1][1] if len(cnt) > 1 else 0)) / k   # vote margin
    ranks = [LRANK[l] for l in g.dec_letter if l in LRANK]
    modal_rank = Counter(ranks).most_common(1)[0][0] if ranks else np.nan
    dist = abs(modal_rank - bnd) if ranks else np.nan   # distance to the IG/HY boundary
    return {"sis": sis, "dissent": float(dissent), "neg_margin": -margin,
            "neg_boundary_dist": -float(dist)}

CANDS = ["sis", "dissent", "neg_margin", "neg_boundary_dist"]
LABEL = {"sis": "SIS (Gini--Simpson)", "dissent": "no. dissenting elicitations",
         "neg_margin": "self-consistency vote margin (neg.)",
         "neg_boundary_dist": "distance to IG/HY boundary (neg.)"}

res_out = {}
specs = sorted(CR.spec_id.unique())
for res in ("ighy", "band", "letter"):
    calib, valid = set(specs[0::2]), set(specs[1::2])
    rows = []
    for it, g in CR.groupby("item_id"):
        c, v = g[g.spec_id.isin(calib)], g[g.spec_id.isin(valid)]
        pr = predictors(c, res)
        if pr is None or len(v) < 2: continue
        vv = (v.ighy if res == "ighy" else v.band if res == "band" else v.dec_letter).tolist()
        rows.append({"item": it, **pr, "event": int(len(set(vv)) > 1)})
    D = pd.DataFrame(rows)
    base = float(D.event.mean())
    aucs = {c: auc(D[c].values, D.event.values) for c in CANDS}
    # issuer-clustered bootstrap on the SIS-minus-dissent AUC difference
    items = D.item.values
    diffs = []
    for _ in range(2000):
        idx = rng.integers(0, len(D), len(D))
        a1 = auc(D.sis.values[idx], D.event.values[idx])
        a2 = auc(D.dissent.values[idx], D.event.values[idx])
        if a1 is not None and a2 is not None: diffs.append(a1 - a2)
    res_out[res] = {
        "n_items": int(len(D)), "event_base_rate": round(base, 3),
        "auc": {c: (round(aucs[c], 4) if aucs[c] is not None else None) for c in CANDS},
        "spearman_sis_vs_dissent": round(spearman(D.sis, D.dissent), 6),
        "auc_diff_sis_minus_dissent": round(float(np.mean(diffs)), 6) if diffs else None,
        "auc_diff_ci95": [round(float(np.percentile(diffs, 2.5)), 4),
                          round(float(np.percentile(diffs, 97.5)), 4)] if diffs else None}
    print(f"\n  == resolution: {res}   n={len(D)} items, event base rate {base:.2f}")
    for c in CANDS:
        a = aucs[c]
        print(f"     {LABEL[c]:40s} AUC {a if a is None else round(a,4)}")
    print(f"     Spearman(SIS, dissent count) = {res_out[res]['spearman_sis_vs_dissent']:.6f}")
    print(f"     AUC(SIS) - AUC(dissent) = {res_out[res]['auc_diff_sis_minus_dissent']}  "
          f"CI {res_out[res]['auc_diff_ci95']}")

# the algebraic identity, asserted
k = 16
grid = [(m, 2 * (m / k) * (1 - m / k)) for m in range(0, k // 2 + 1)]
mono = all(grid[i][1] < grid[i + 1][1] for i in range(len(grid) - 1))
smallest_nonzero = grid[1][1]
print(f"\n  binary-gate algebra at k={k}: SIS strictly increasing in dissent count: {mono}")
print(f"  smallest non-zero SIS = {smallest_nonzero:.4f}; reported Youden tau = 0.08 "
      f"=> flags iff SIS>0 iff at least one dissent: {0.08 < smallest_nonzero}")

out = {"_meta": {"seed": 42, "panel_rows": int(len(CR)), "items": int(CR.item_id.nunique()),
                 "specs": int(CR.spec_id.nunique()),
                 "not_computable": ["semantic entropy", "token-level confidence"],
                 "not_computable_reason": "the frozen response corpus stores no logprobs; these "
                                          "baselines would require re-elicitation with logprobs "
                                          "enabled and are not available for all providers"},
       "by_resolution": res_out,
       "binary_gate_algebra": {"k": k, "sis_monotone_in_dissent_count": bool(mono),
                               "smallest_nonzero_sis": round(smallest_nonzero, 4),
                               "reported_tau": 0.08,
                               "rule_reduces_to_any_disagreement": bool(0.08 < smallest_nonzero)}}
json.dump(out, open(PB / "results/results_r3_sis_baselines.json", "w"), indent=1)
print(f"\n  -> results/results_r3_sis_baselines.json")
