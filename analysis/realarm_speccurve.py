#!/usr/bin/env python3
"""R3-1 closure: specification curve on an EXTERNAL benchmark not used to construct the profiles.
Reads the real-issuer arm panel (31 decontaminated real firms x 12 specs x 3 seeds) and scores each
specification's credit-band accuracy against the firms' DISCLOSED AGENCY RATINGS (external reference,
independent of profile construction). Produces a per-specification accuracy curve analogous to Fig 1,
and the split of specifications around the majority-accuracy threshold. OFFLINE, deterministic (seed 42).
Writes results/results_realarm_speccurve.json."""
from __future__ import annotations
import json, glob
from pathlib import Path
from collections import defaultdict
import numpy as np
PB=Path(__file__).resolve().parents[1]
rng=np.random.default_rng(42)

panel=sorted(glob.glob(str(PB/"data"/"raw"/"realarm"/"arm_runs"/"run_2026*"/"arm_panel.json")))[-1]
rows=json.load(open(panel))["rows"]

def spec_accuracy(strata):
    """per-spec exact band accuracy vs disclosed agency rating, on the given strata."""
    by=defaultdict(lambda:[0,0])  # spec -> [hit,total]
    for r in rows:
        if not r.get("parsed_band"): continue
        if r.get("benchmark_label") not in strata: continue
        hit,tot=by[r["spec_id"]]
        by[r["spec_id"]]=[hit+(r["parsed_band"]==r["benchmark_label"]), tot+1]
    return {s:round(h/t,4) for s,(h,t) in sorted(by.items()) if t}

def issuer_cluster_ci(strata, reps=5000):
    """issuer-clustered bootstrap CI on the mean per-spec accuracy (resample issuers)."""
    # build per-(issuer) contribution: for each issuer, its correct/total across all specs
    issuers=sorted(set(r["item_id"] for r in rows if r.get("benchmark_label") in strata))
    per={i:[0,0] for i in issuers}
    for r in rows:
        if not r.get("parsed_band") or r.get("benchmark_label") not in strata: continue
        per[r["item_id"]][0]+=int(r["parsed_band"]==r["benchmark_label"]); per[r["item_id"]][1]+=1
    arr=[(h,t) for h,t in per.values() if t]
    def acc(sample):
        H=sum(h for h,_ in sample); T=sum(t for _,t in sample); return H/T if T else np.nan
    obs=acc(arr); bs=[]
    idx=np.arange(len(arr))
    for _ in range(reps):
        s=[arr[k] for k in rng.choice(idx,len(idx),replace=True)]; bs.append(acc(s))
    return round(float(obs),4),[round(float(np.percentile(bs,2.5)),4),round(float(np.percentile(bs,97.5)),4)]

def spread_permutation(strata, reps=2000):
    """Within-arm, issuer-preserving permutation test: is the between-spec accuracy spread beyond chance?
    Null permutes specification labels WITHIN each issuer (preserving the repeated-measures structure:
    each issuer keeps its own set of hits, only the spec attribution is shuffled); statistic = SD across
    specs of per-spec mean accuracy."""
    import pandas as pd
    d=[(r["item_id"], r["spec_id"], int(r["parsed_band"]==r["benchmark_label"]))
       for r in rows if r.get("parsed_band") and r.get("benchmark_label") in strata]
    df=pd.DataFrame(d,columns=["item","spec","hit"])
    def spread(spec_series):
        return float(df.hit.groupby(spec_series).mean().std(ddof=0))
    obs=spread(df.spec)
    # per-issuer index groups, to shuffle spec labels within each issuer
    groups=[g.index.values for _,g in df.groupby("item")]
    specvals=df.spec.values
    null=np.empty(reps)
    for i in range(reps):
        permuted=specvals.copy()
        for idx in groups:
            permuted[idx]=rng.permutation(specvals[idx])
        null[i]=spread(pd.Series(permuted,index=df.index))
    exceed=int(np.sum(null>=obs))
    return {"scheme":"issuer-preserving (spec labels permuted within issuer)",
            "observed_spread_sd":round(obs,4),"null_mean":round(float(null.mean()),4),
            "null_sd":round(float(null.std(ddof=0)),4),"n_perm":reps,"n_exceed":exceed,
            "p_value":round((exceed+1)/(reps+1),4)}

for name,strata in [("SAFE_WATCH",("SAFE","WATCH")),("ALL",("SAFE","WATCH","DISTRESS"))]:
    curve=spec_accuracy(strata)
    vals=np.array(list(curve.values()))
    obs,ci=issuer_cluster_ci(strata)
    spread_perm=spread_permutation(strata)
    out={
      "_meta":{"benchmark":"disclosed agency ratings (external; NOT used to construct the real firms)",
               "grid":"31 real issuers x 12 specs x 3 seeds","strata":list(strata),"seed":42,"panel":Path(panel).parts[-2]},
      "n_specs":len(curve),
      "per_spec_band_accuracy":curve,
      "spec_curve_sorted":sorted(vals.round(4).tolist()),
      "mean_accuracy":round(float(vals.mean()),4),
      "min_spec_accuracy":round(float(vals.min()),4),
      "max_spec_accuracy":round(float(vals.max()),4),
      "range_pp":round(float(100*(vals.max()-vals.min())),1),
      "issuer_clustered_mean":obs,"issuer_clustered_95CI":ci,
      "spread_permutation_test":spread_perm,
      "pct_specs_majority_correct":round(float((vals>=0.5).mean()),4),
      "note":("External-benchmark specification curve: each point is one specification's exact credit-band "
              "accuracy against the firms' disclosed agency ratings. Because the agency rating is independent "
              "of profile construction, this is the benchmark-independent curve requested by R3-1. The spread "
              "across specifications (range %.1f pp) shows the specification sensitivity persists against a "
              "truly external reference."%(100*(vals.max()-vals.min())))}
    (PB/"results").mkdir(exist_ok=True)
    (PB/"results"/f"results_realarm_speccurve_{name}.json").write_text(json.dumps(out,indent=1))
    print(f"=== {name} === specs={out['n_specs']}  mean={out['mean_accuracy']}  "
          f"range=[{out['min_spec_accuracy']},{out['max_spec_accuracy']}] ({out['range_pp']}pp)  "
          f"issuer-clustered {obs} CI{ci}")
