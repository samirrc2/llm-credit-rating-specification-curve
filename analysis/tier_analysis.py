#!/usr/bin/env python3
"""Model-tier robustness (reviewer check). OFFLINE, deterministic (seed 42).

Compares the per-comparison IG/HY flip (and three-way band flip) between the nano/flash
tier and the flagship tier on the SAME frozen 12-specification grid x 45 credit-health
items x 3 seeds. Uses the identical flip metric as run_analysis.py: per item,
1 - Gini-Simpson concentration of its IG/HY draws, averaged across items, with an
issuer-clustered percentile bootstrap 95% CI. Reads only frozen panels; makes no API call.

Inputs (frozen):
  data/raw/realarm/battery_comp_runs/run_20260710_102711/arm_panel.json   (nano/flash, matched grid)
  capture/flagship_runs/run_20260830_141844/flagship_panel.json           (flagship, MANIFEST_FLAGSHIP)
Output:
  results/results_tier.json
"""
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter
import numpy as np

PB = Path(__file__).resolve().parents[1]
RS = json.load(open(PB / "data" / "frozen" / "main" / "rating_scale.json"))
IGHY = RS["letter_to_ig_hy"]; BAND = RS["letter_to_band"]
rng = np.random.default_rng(42)

NANO = PB / "data" / "raw" / "realarm" / "battery_comp_runs" / "run_20260710_102711" / "arm_panel.json"
FLAG = PB / "capture" / "flagship_runs" / "run_20260830_141844" / "flagship_panel.json"

def rows(p): return json.load(open(p))["rows"]

def per_item_flip(rowset, mapping, prov=None):
    d = {}
    for r in rowset:
        if prov and r["provider"] != prov: continue
        let = r.get("parsed_letter"); v = mapping.get(let) if let else None
        if v is None: continue
        d.setdefault(r["item_id"], []).append(v)
    out = {}
    for it, xs in d.items():
        n = len(xs)
        if n < 2: continue
        p = np.array(list(Counter(xs).values())) / n
        out[it] = 1 - float((p ** 2).sum())
    return out

def summ(flips):
    arr = np.array(list(flips.values()))
    m = float(arr.mean())
    bs = np.array([float(np.mean(rng.choice(arr, len(arr), replace=True))) for _ in range(2000)])
    return {"flip": round(m, 4), "CI95": [round(float(np.percentile(bs, 2.5)), 4),
                                          round(float(np.percentile(bs, 97.5)), 4)],
            "n_items": len(arr)}

def paired_diff(a, b):
    items = sorted(set(a) & set(b))
    diff = np.array([b[i] - a[i] for i in items])
    md = float(diff.mean())
    bs = np.array([float(np.mean(rng.choice(diff, len(diff), replace=True))) for _ in range(5000)])
    return {"diff": round(md, 4), "CI95": [round(float(np.percentile(bs, 2.5)), 4),
                                           round(float(np.percentile(bs, 97.5)), 4)], "n_items": len(items)}

nf, fg = rows(NANO), rows(FLAG)
out = {"_meta": {"grid": "12 specs x 45 credit items x 3 seeds",
                 "nano_flash_models": sorted(set(r["model"] for r in nf)),
                 "flagship_models": sorted(set(r["model"] for r in fg)),
                 "metric": "per-comparison flip = 1 - Gini-Simpson concentration, mean over items; "
                           "issuer-clustered percentile bootstrap 95% CI (reps=2000; diff reps=5000)"}}
for label, mp in [("ighy", IGHY), ("band", BAND)]:
    a, b = per_item_flip(nf, mp), per_item_flip(fg, mp)
    out[f"tier.{label}.nano_flash"] = summ(a)
    out[f"tier.{label}.flagship"] = summ(b)
    out[f"tier.{label}.diff_flagship_minus_nano"] = paired_diff(a, b)
    if label == "ighy":
        for pv in ("openai", "google"):
            out[f"tier.ighy.nano_flash.{pv}"] = summ(per_item_flip(nf, mp, pv))
            out[f"tier.ighy.flagship.{pv}"] = summ(per_item_flip(fg, mp, pv))
# IG rate (leniency) for context
for label, rowset in [("nano_flash", nf), ("flagship", fg)]:
    c = Counter(IGHY.get(r.get("parsed_letter")) for r in rowset if r.get("parsed_letter"))
    tot = sum(c.values())
    out[f"tier.ig_rate.{label}"] = round(c.get("IG", 0) / tot, 4)

(PB / "results").mkdir(exist_ok=True)
(PB / "results" / "results_tier.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
