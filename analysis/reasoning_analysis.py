#!/usr/bin/env python3
"""Reasoning-architecture robustness (reviewer R2). OFFLINE, deterministic (seed 42).
Reads the FROZEN reasoning corpus (capture/reasoning_runs/) and compares the reasoning model
(DeepSeek-R1, native chain-of-thought) to the nano/flash and flagship tiers on the SAME frozen
12-spec grid x 45 credit items x 3 seeds. No API calls. Writes results/results_reasoning.json.
Run once the arm is collected + frozen; wired into reproduce.sh so the paid run never repeats."""
from __future__ import annotations
import json, glob
from pathlib import Path
from collections import Counter
import numpy as np
PB=Path(__file__).resolve().parents[1]
IGHY=json.load(open(PB/"data"/"frozen"/"main"/"rating_scale.json"))["letter_to_ig_hy"]
rng=np.random.default_rng(42)
def rows(p): return json.load(open(p))["rows"]
def per_item_flip(rs):
    d={}
    for r in rs:
        ig=IGHY.get(r.get("parsed_letter"))
        if ig: d.setdefault(r["item_id"],[]).append(ig)
    return {it:1-sum((c/len(v))**2 for c in Counter(v).values()) for it,v in d.items() if len(v)>=2}
def summ(fl):
    a=np.array(list(fl.values())); m=float(a.mean())
    bs=np.array([float(np.mean(rng.choice(a,len(a),replace=True))) for _ in range(2000)])
    return {"flip":round(m,4),"CI95":[round(float(np.percentile(bs,2.5)),4),round(float(np.percentile(bs,97.5)),4)],"n":len(a)}
def band_acc(rs):
    ok=tot=0; B=json.load(open(PB/"data"/"frozen"/"main"/"rating_scale.json"))["letter_to_band"]
    for r in rs:
        b=B.get(r.get("parsed_letter")); bn=r.get("benchmark_label")
        if b and bn: tot+=1; ok+=(b==bn)
    return round(ok/tot,4) if tot else None

reason_glob=sorted(glob.glob(str(PB/"capture"/"reasoning_runs"/"run_*"/"reasoning_panel.json")))
if not reason_glob:
    print("No reasoning corpus yet — run capture/run_reasoning.py then freeze_reasoning.py."); raise SystemExit(0)
rz=rows(reason_glob[-1])
nf=rows("data/raw/realarm/battery_comp_runs/run_20260710_102711/arm_panel.json")
fg=rows(sorted(glob.glob(str(PB/"capture"/"flagship_runs"/"run_*"/"flagship_panel.json")))[-1])
out={"_meta":{"grid":"12 specs x 45 credit items x 3 seeds","reasoning_model":json.load(open(reason_glob[-1])).get("model")}}
out["reasoning.ighy_flip"]=summ(per_item_flip(rz))
out["nano_flash.ighy_flip"]=summ(per_item_flip(nf))
out["flagship.ighy_flip"]=summ(per_item_flip(fg))
out["reasoning.band_accuracy_vs_altman"]=band_acc(rz)
out["reasoning.ig_rate"]=round(float(np.mean([IGHY.get(r.get("parsed_letter"))=="IG" for r in rz if r.get("parsed_letter")])),4)
# paired difference reasoning - nano/flash
a=per_item_flip(rz); b=per_item_flip(nf); it=sorted(set(a)&set(b))
diff=np.array([a[i]-b[i] for i in it]); md=float(diff.mean())
bs=np.array([float(np.mean(rng.choice(diff,len(diff),replace=True))) for _ in range(5000)])
out["reasoning_minus_nanoflash.diff"]={"diff":round(md,4),"CI95":[round(float(np.percentile(bs,2.5)),4),round(float(np.percentile(bs,97.5)),4)],"n":len(it)}
(PB/"results").mkdir(exist_ok=True)
(PB/"results"/"results_reasoning.json").write_text(json.dumps(out,indent=1))
print(json.dumps(out,indent=1))
