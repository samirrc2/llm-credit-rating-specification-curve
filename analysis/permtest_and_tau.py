#!/usr/bin/env python3
"""Two reviewer-requested quantities, computed offline & deterministically (seed 42):

R3-3  Corrected permutation test under the RATING-INVARIANCE null (not accuracy-invariance).
      On the deterministic subgrid (Google, requested temperature 0), we item-center the letter
      ratings (removing issuer composition) and take the between-specification spread of the
      item-centred rating as the statistic; the null permutes specification-condition assignments
      across observations. Reports the observed statistic, the null mean/SD, the exact count of
      permutations as extreme as observed, the p-value, and the specification eta-squared.

R3-5  SIS operating threshold tau. Using the held-out-specification construction (score fit on 16
      calibration specs; flag = any IG/HY flip on the disjoint 16 validation specs), we choose tau by
      Youden's J and report precision/recall/F1 at that tau, plus two reference operating points.

Writes results/results_permtest_tau.json.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd
PB = Path(__file__).resolve().parents[1]
RS = json.load(open(PB/"data"/"frozen"/"main"/"rating_scale.json"))
LRANK = {l:i for i,l in enumerate(RS["letter_scale"])}; IGHY = RS["letter_to_ig_hy"]
rng = np.random.default_rng(42)
P = pd.read_parquet(PB/"data"/"panel"/"panel.parquet")
P = P[P.provider.isin(["openai","google"])]
CR = P[(P.family=="credit_health") & (P.parse_rule=="lenient") & P.decision.notna()].copy()
CR["rank"] = CR.dec_letter.map(LRANK); CR["ighy"] = CR.dec_letter.map(IGHY)
out = {"_meta":{"seed":42}}

# ---------- R3-3: rating-invariance permutation on the deterministic subgrid ----------
sub = CR[(CR.provider=="google") & (CR.requested_temp==0.0)].dropna(subset=["rank"]).copy()
sub["rank_c"] = sub["rank"] - sub.groupby("item_id")["rank"].transform("mean")   # item-centred rating
def between_spec_spread(df, col="rank_c"):
    m = df.groupby("spec_id")[col].mean()
    return float(m.std(ddof=0))
obs = between_spec_spread(sub)
# specification eta^2 on the item-centred rating (variance across specs / total)
grand = sub["rank_c"].mean()
ss_tot = float(((sub["rank_c"]-grand)**2).sum())
gm = sub.groupby("spec_id")["rank_c"]
ss_spec = float(sum(len(g)*(g.mean()-grand)**2 for _,g in gm))
eta2_spec = round(ss_spec/ss_tot, 4) if ss_tot>0 else None
NPERM = 2000
vals = sub["rank_c"].values; specs = sub["spec_id"].values
null = np.empty(NPERM)
for i in range(NPERM):
    permspec = rng.permutation(specs)
    d = pd.DataFrame({"spec_id":permspec,"rank_c":vals})
    null[i] = d.groupby("spec_id")["rank_c"].mean().std(ddof=0)
exceed = int(np.sum(null >= obs))
out["R3_3.rating_invariance_permutation"] = {
    "subgrid":"Google, requested temperature 0 (deterministic)",
    "n_obs":int(len(sub)), "n_specs":int(sub.spec_id.nunique()),
    "statistic":"between-specification SD of item-centred letter rating",
    "observed":round(obs,4),
    "null_mean":round(float(null.mean()),4), "null_sd":round(float(null.std(ddof=0)),4),
    "n_permutations":NPERM, "n_exceed_observed":exceed,
    "p_value":round((exceed+1)/(NPERM+1),4),
    "specification_eta2_itemcentred":eta2_spec,
    "note":"Null permutes specification-condition assignments across observations (rating-invariance null), "
           "not accuracy labels. eta^2 is on specification-level aggregates of the item-centred rating and is "
           "not comparable to the individual-rating variance partition in Table 1."}

# ---------- R3-5: tau calibration on the held-out-specification split ----------
def simpson_flip(vals):
    n=len(vals)
    from collections import Counter
    return np.nan if n<2 else 1-sum((c/n)**2 for c in Counter(vals).values())
specs = sorted(CR.spec_id.unique()); calib=set(specs[0::2]); valid=set(specs[1::2])
rows=[]
for it,g in CR.groupby("item_id"):
    c=g[g.spec_id.isin(calib)].ighy.tolist(); v=g[g.spec_id.isin(valid)].ighy.tolist()
    if len(c)<2 or len(v)<2: continue
    rows.append({"score":simpson_flip(c),"flag":int(len(set(v))>1)})
val=pd.DataFrame(rows); s=val.score.values; y=val.flag.values.astype(int)
def pr_at(tau):
    pred=(s>=tau).astype(int); tp=int(((pred==1)&(y==1)).sum()); fp=int(((pred==1)&(y==0)).sum()); fn=int(((pred==0)&(y==1)).sum())
    prec=tp/(tp+fp) if tp+fp else None; rec=tp/(tp+fn) if tp+fn else None
    f1=(2*prec*rec/(prec+rec)) if prec and rec else None
    return prec,rec,f1
cand=sorted(set(np.round(s,4)))
best=None
for tau in cand:
    pred=(s>=tau).astype(int)
    tpr=((pred==1)&(y==1)).sum()/max((y==1).sum(),1)
    fpr=((pred==1)&(y==0)).sum()/max((y==0).sum(),1)
    J=tpr-fpr
    if best is None or J>best[0]: best=(J,tau)
tau_star=float(best[1]); p,r,f=pr_at(tau_star)
out["R3_5.tau_calibration"]={
    "construction":"score = SIS on 16 calibration specs; flag = any IG/HY flip on the disjoint 16 validation specs (45 issuers)",
    "tau_selected_youdenJ":round(tau_star,3),
    "precision_at_tau":round(p,3) if p else None,"recall_at_tau":round(r,3) if r else None,"f1_at_tau":round(f,3) if f else None,
    "base_rate_flip":round(float(y.mean()),3),
    "reference_points":{f"tau={t}":{"precision":(round(pr_at(t)[0],3) if pr_at(t)[0] else None),
                                    "recall":(round(pr_at(t)[1],3) if pr_at(t)[1] else None)} for t in [0.3,0.5]},
    "note":"tau chosen to maximise Youden's J on the held-out split; practitioners raise tau for higher precision, lower for higher recall."}
(PB/"results").mkdir(exist_ok=True)
(PB/"results"/"results_permtest_tau.json").write_text(json.dumps(out,indent=1))
print(json.dumps(out,indent=1))
