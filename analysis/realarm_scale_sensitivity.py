#!/usr/bin/env python3
"""R3-4 closure: does the LLM respond to ABSOLUTE monetary scale (not just ratios)?
Z'' is invariant to the uniform per-issuer dollar scaling by construction, but an LLM sees the raw
dollar figures too. Each real issuer was scaled by its own perturb_scale in [0.6, 1.7]; these factors
already span the perturbation range across the 31 issuers. We test, using the data already collected
(no new API calls), whether per-issuer LLM instability and rating LEVEL vary with the applied scale.
Near-zero association = the LLM output is not driven by absolute monetary scale within the range.
OFFLINE, deterministic (seed 42). Writes results/results_scale_sensitivity.json."""
from __future__ import annotations
import json, glob
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
PB=Path(__file__).resolve().parents[1]
rng=np.random.default_rng(42)
IGHY=json.load(open(PB/"data"/"frozen"/"main"/"rating_scale.json"))["letter_to_ig_hy"]
ORDER=json.load(open(PB/"data"/"frozen"/"main"/"rating_scale.json"))["letter_scale"]
LR={l:i for i,l in enumerate(ORDER)}

xw={e["item_id"]:e["perturb_scale"] for e in json.load(open(PB/"data"/"frozen"/"realarm"/"sealed_crosswalk.json"))["map"]}
panel=sorted(glob.glob(str(PB/"data"/"raw"/"realarm"/"arm_runs"/"run_2026*"/"arm_panel.json")))[-1]
rows=json.load(open(panel))["rows"]

by=defaultdict(list)      # item -> list of rows
for r in rows:
    if r.get("parsed_band"): by[r["item_id"]].append(r)

def gini(vals):
    n=len(vals)
    return None if n<2 else 1-sum((c/n)**2 for c in Counter(vals).values())

scale=[]; band_flip=[]; ighy_flip=[]; mean_rank=[]; ig_rate=[]
for it, rs in by.items():
    if it not in xw: continue
    bands=[r["parsed_band"] for r in rs]
    igh=[IGHY.get(r.get("parsed_letter")) for r in rs if IGHY.get(r.get("parsed_letter"))]
    ranks=[LR[r["parsed_letter"]] for r in rs if r.get("parsed_letter") in LR]
    bf=gini(bands)
    if bf is None: continue
    scale.append(xw[it]); band_flip.append(bf)
    ighy_flip.append(gini(igh) if len(igh)>=2 else 0.0)
    mean_rank.append(float(np.mean(ranks)) if ranks else np.nan)
    ig_rate.append(float(np.mean([x=="IG" for x in igh])) if igh else np.nan)

scale=np.array(scale); band_flip=np.array(band_flip); ighy_flip=np.array(ighy_flip)
mean_rank=np.array(mean_rank); ig_rate=np.array(ig_rate)

def spearman(a,b):
    import pandas as pd
    m=~(np.isnan(a)|np.isnan(b))
    return round(float(np.corrcoef(pd.Series(a[m]).rank(),pd.Series(b[m]).rank())[0,1]),3)
def perm_p(a,b,reps=5000):
    import pandas as pd
    m=~(np.isnan(a)|np.isnan(b)); a,b=a[m],b[m]
    obs=abs(np.corrcoef(pd.Series(a).rank(),pd.Series(b).rank())[0,1])
    cnt=0
    for _ in range(reps):
        bp=rng.permutation(b)
        if abs(np.corrcoef(pd.Series(a).rank(),pd.Series(bp).rank())[0,1])>=obs: cnt+=1
    return round((cnt+1)/(reps+1),4)

out={
 "_meta":{"n_issuers":int(len(scale)),"scale_range":[round(float(scale.min()),3),round(float(scale.max()),3)],
          "scale_applied_range_spec":"LogUniform[0.6,1.7]","seed":42,"panel":Path(panel).parts[-2],
          "design":"per-issuer applied dollar-scale factor vs per-issuer LLM instability and rating level; existing data, no new API calls"},
 "instability_vs_scale":{
   "spearman_bandflip_vs_scale":spearman(band_flip,scale),"perm_p":perm_p(band_flip,scale),
   "spearman_ighyflip_vs_scale":spearman(ighy_flip,scale)},
 "rating_level_vs_scale":{
   "spearman_meanletterrank_vs_scale":spearman(mean_rank,scale),
   "spearman_igrate_vs_scale":spearman(ig_rate,scale),
   "note":"tests whether presenting larger absolute dollar figures (same ratios) shifts the rating level"},
 "summary_band_flip":{"mean":round(float(band_flip.mean()),4),"sd":round(float(band_flip.std()),4)},
 "interpretation":"Near-zero Spearman associations indicate the LLM's instability and rating level do not track the absolute monetary scale within the tested [0.6,1.7] range; the decontamination's random scaling is not driving the reported instability."}
(PB/"results").mkdir(exist_ok=True)
(PB/"results"/"results_scale_sensitivity.json").write_text(json.dumps(out,indent=1))
print(json.dumps(out,indent=1))
