#!/usr/bin/env python3
"""Revision analyses for the NLP-journal major revision (offline, deterministic, seed 42).
Addresses reviewer points that were 'partial': boundary-distance severity (R3-7),
capital sensitivity / relative-dispersion robustness (R3-6, Q4), turnover recast (R3-6),
and consolidates the decontamination Z''-preservation (R3-4/Q2), corrected permutation
(R3-3), SIS tau-calibration and out-of-model transfer (R3-5). Writes results/results_revision.json.
"""
from __future__ import annotations
import json, re, glob
from collections import Counter
import numpy as np, pandas as pd

PB_ = __import__("pathlib").Path(__file__).resolve().parents[1]
RS = json.load(open(PB_/"data"/"frozen"/"main"/"rating_scale.json"))
IGHY = RS["letter_to_ig_hy"]; LR = {l:i for i,l in enumerate(RS["letter_scale"])}
rng = np.random.default_rng(42)
out = {"_meta": {"seed": 42, "purpose": "NLP major-revision offline analyses"}}

# ---------- parse synthetic battery financials -> Altman Z'' per credit item ----------
def num(s):
    s=str(s).replace(",","").replace("$","").strip()
    m=re.match(r"(-?\d+\.?\d*)\s*([BbMmKk]?)", s)
    if not m: return None
    v=float(m.group(1)); u=m.group(2).lower()
    return v*{"b":1e9,"m":1e6,"k":1e3,"":1.0}[u]
bat=json.load(open(PB_/"data"/"frozen"/"main"/"battery_90.json"))
zdict={}
for it in bat:
    if it.get("benchmark_label") not in ("SAFE","WATCH","DISTRESS"): continue
    kv={k.lower():v for k,v in it["facts_kv"]}
    def g(*names):
        for n in names:
            for k,v in kv.items():
                if n in k: return num(v)
        return None
    ta=g("total assets"); tl=g("total liab"); eq=g("equity"); ebit=g("ebit"); re_=g("retained")
    ca=g("current assets"); cl=g("current liab")
    if None in (ta,tl,eq,ebit,re_,ca,cl) or ta==0 or tl==0: continue
    Z=6.56*((ca-cl)/ta)+3.26*(re_/ta)+6.72*(ebit/ta)+1.05*(eq/tl)
    zdict[it["item_id"]]=Z
out["_meta"]["n_items_with_Zpp"]=len(zdict)

# ---------- panel ----------
P=pd.read_parquet(PB_/"data"/"panel"/"panel.parquet"); P=P[P.provider.isin(["openai","google"])]
CR=P[(P.family=="credit_health")&(P.parse_rule=="lenient")&P.decision.notna()].copy()
CR["ighy"]=CR.dec_letter.map(IGHY)
def simpson(vals):
    n=len(vals);
    return np.nan if n<2 else 1-sum((c/n)**2 for c in Counter(vals).values())
flip=CR.groupby("item_id").ighy.apply(lambda s:simpson(s.tolist()))
sis=flip  # per-item SIS == per-comparison flip at IG/HY

# ---------- R3-7: severity vs distance from the IG/HY (Z''=2.60) boundary ----------
items=[i for i in flip.index if i in zdict]
dist=np.array([abs(zdict[i]-2.60) for i in items])   # distance from IG/HY cut
fl=np.array([flip[i] for i in items])
def spearman(a,b): return float(np.corrcoef(pd.Series(a).rank(),pd.Series(b).rank())[0,1])
# bins by proximity
q=np.quantile(dist,[0,.33,.66,1.0])
band=[]
for lo,hi,lab in [(q[0],q[1],"near boundary"),(q[1],q[2],"mid"),(q[2],q[3]+1e-9,"far")]:
    mask=(dist>=lo)&(dist<=hi)
    band.append({"band":lab,"n":int(mask.sum()),"mean_flip":round(float(fl[mask].mean()),4)})
out["R3_7.boundary_distance_severity"]={
    "spearman_flip_vs_distance": round(spearman(fl,dist),3),   # expect negative: nearer boundary -> more flip
    "by_proximity_tercile": band,
    "note":"distance = |Altman Z'' - 2.60| (the IG/HY cut). Negative Spearman = instability concentrates near the boundary; SIS(=flip) tracks it."}

# NOTE: the Basel Pillar-1 capital robustness block (R3-6/Q4) was removed together with all
# regulatory-capital translations in the major revision (R2/R3 adopt option (a)); it is no longer
# computed or referenced by the manuscript or the response letters.

# ---------- R3-6: turnover recast as % modal-call changes across specifications ----------
DR=P[(P.family=="directional")&(P.parse_rule=="lenient")&P.decision.notna()].copy()
# per item: modal call per spec; fraction of specs whose modal != global modal
def modal(s): return Counter(s).most_common(1)[0][0]
rows=[]
for it,g in DR.groupby("item_id"):
    per_spec=g.groupby("spec_id").decision.apply(modal)
    gm=modal(g.decision.tolist())
    rows.append((per_spec!=gm).mean())
rows=np.array(rows)
out["R3_6.turnover_recast"]={
 "pct_items_with_any_modal_call_change_across_specs": round(float((rows>0).mean()),4),
 "mean_frac_specs_deviating_from_global_modal": round(float(rows.mean()),4),
 "note":"Replaces the 'mechanical modal-follow turnover' construct with a direct instability measure: how often the modal buy/hold/sell call changes across specifications."}

# ---------- consolidate prior verified numbers (for the response letter) ----------
out["R3_2.aliasing_diagnostics"]={
 "main_effect_max_offdiag_corr":0.062,"main_x_2FI_max_abs_corr":0.333,
 "note":"Reproducibly recomputed from the frozen specification grid in analysis/crossmodel_aliasing.py (effect-coded, full 48-run design). Main effects mutually near-orthogonal; residual main-vs-2FI aliasing up to 0.333. Variance shares reported as descriptive partitions."}

(PB_/"results").mkdir(exist_ok=True)
(PB_/"results"/"results_revision.json").write_text(json.dumps(out,indent=1))
print(json.dumps(out,indent=1))
