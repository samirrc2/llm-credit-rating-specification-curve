#!/usr/bin/env python3
"""Held-out-ISSUER benchmark for the baseline comparison (Reviewer 3, Concern 3).

Spec hashed before computation: analysis/revision2/SPEC_r3_heldout_issuer_and_audit.md
The existing comparison splits SPECIFICATIONS; the reviewer asked for both settings. Offline,
deterministic, no new model calls.
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
IGHY = RS["letter_to_ig_hy"]; BAND = RS["letter_to_band"]; BOUNDARY = RS["ig_hy_boundary"]
P = pd.read_parquet(PB / "data/panel/panel.parquet")
P = P[P.provider.isin(["openai", "google"])]
CR = P[(P.family == "credit_health") & (P.parse_rule == "lenient") & P.decision.notna()].copy()
CR["ighy"] = CR.dec_letter.map(IGHY); CR["band"] = CR.dec_letter.map(BAND)
bnd = LRANK[BOUNDARY] if BOUNDARY in LRANK else max(
    LRANK[l] for l, v in IGHY.items() if v == "IG" and l in LRANK)

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
            "sem_entropy": float(-(p * np.log(p)).sum()),
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

specs = sorted(CR.spec_id.unique()); calib, valid = set(specs[0::2]), set(specs[1::2])
out = {"_meta": {"spec": "analysis/revision2/SPEC_r3_heldout_issuer_and_audit.md",
                 "spec_sha256": open(PB / "results/SPEC_r3_heldout_issuer_and_audit.sha256")
                                .read().split()[0],
                 "n_splits": 300, "seed": 42, "new_model_calls": 0,
                 "note": "Features and events use the SAME 16/16 specification split as the "
                         "specification-held-out benchmark; the issuer split determines only "
                         "which issuers discrimination is evaluated on."}}
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
    D = pd.DataFrame(rows); items = D.item.values
    base = float(D.event.mean())
    if D.event.sum() in (0, len(D)):
        res_out[res] = {"n_items": int(len(D)), "event_base_rate": round(base, 3),
                        "computable": False,
                        "reason": f"event base rate {base:.2f}; discrimination undefined"}
        print(f"  == {res}: base rate {base:.2f} -- undefined, not computable")
        continue
    per = {c: [] for c in CANDS}; diffs = []; used = 0
    for _ in range(300):
        perm = rng.permutation(len(D))
        hold = D.iloc[perm[len(D) // 2:]]               # held-out issuer half
        if hold.event.sum() in (0, len(hold)):
            continue
        a = {c: auc(hold[c].values, hold.event.values) for c in CANDS}
        if any(v is None for v in a.values()):
            continue
        for c in CANDS:
            per[c].append(a[c])
        diffs.append(a["sis"] - a["dissent"]); used += 1
    q = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
    res_out[res] = {"n_items": int(len(D)), "event_base_rate": round(base, 3),
                    "computable": True, "splits_used": used,
                    "mean_auc": {c: round(float(np.mean(per[c])), 4) for c in CANDS},
                    "auc_pct_interval": {c: q(per[c]) for c in CANDS},
                    "auc_diff_sis_minus_dissent_mean": round(float(np.mean(diffs)), 9),
                    "auc_diff_max_abs": round(float(np.max(np.abs(diffs))), 9),
                    "auc_diff_interval": q(diffs)}
    print(f"\n  == {res}: {len(D)} issuers, base rate {base:.2f}, {used} usable splits")
    for c in CANDS:
        print(f"     {c:20s} mean held-out-issuer AUC {res_out[res]['mean_auc'][c]:.4f}  "
              f"{res_out[res]['auc_pct_interval'][c]}")
    print(f"     AUC(score) - AUC(dissent): mean {res_out[res]['auc_diff_sis_minus_dissent_mean']}, "
          f"max |diff| {res_out[res]['auc_diff_max_abs']}")
out["by_resolution"] = res_out

# the spec's prediction, asserted: rank-equivalence is a per-issuer property, so it must hold on
# every random subset of issuers. A non-zero difference anywhere is a bug.
for res in ("ighy", "band"):
    if res_out[res].get("computable"):
        m = res_out[res]["auc_diff_max_abs"]
        assert m == 0.0, f"BUG: held-out-issuer AUC difference must be 0 at {res}; max |diff| {m}"
print("\n  assertion holds: on every one of the 300 issuer splits the score and the dissent count "
      "give identical AUC, as rank-equivalence requires.")
json.dump(out, open(PB / "results/results_r3_heldout_issuer.json", "w"), indent=1)
print("  -> results/results_r3_heldout_issuer.json")
