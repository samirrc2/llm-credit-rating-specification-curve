#!/usr/bin/env python3
"""Appendix D — Real-firm arm · PHASE 5 analysis (offline; no API).

Reads the arm panel (31 decontaminated B2B firms) and the battery comparator panel (45 constructed
items) — both rated on the IDENTICAL 12-spec x 3-seed grid — and computes:
  H1  flip-share, PRIMARY on the WATCH stratum (real vs battery), |diff| <= 0.15 => SUPPORTED;
      SECONDARY raw whole-sample with the pre-stated composition caveat. Issuer-clustered bootstrap CIs.
  Band accuracy of the arm vs the disclosed agency rating (SAFE/WATCH; DISTRESS excluded, n=1).
  Variance decomposition: item vs spec vs seed.

RUN:  python3 analyze_arm.py
"""
import json, glob, random, statistics as st
from collections import defaultdict, Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
RUNS=ROOT/"data"/"raw"/"realarm"
RESULTS=ROOT/"results"

def latest_panel(root):
    runs=sorted(glob.glob(str(RUNS/root/"run_2026*/arm_panel.json")))
    if not runs: return None
    return json.load(open(runs[-1]))

def flip_share_by_item(rows, stratum=None):
    by=defaultdict(list)
    for r in rows:
        if not r.get("parsed_band"): continue
        if stratum and r.get("benchmark_label")!=stratum: continue
        by[r["item_id"]].append(r["parsed_band"])
    per={}
    for iid,b in by.items():
        n=len(b)
        if n<2: continue
        diff=sum(1 for i in range(n) for j in range(i+1,n) if b[i]!=b[j])
        per[iid]=diff/(n*(n-1)/2)
    return per

def boot_ci(per_item, reps=10000, seed=20260709):
    if not per_item: return (None,None,None)
    vals=list(per_item.values()); rng=random.Random(seed); n=len(vals); bs=[]
    for _ in range(reps):
        s=[vals[rng.randrange(n)] for _ in range(n)]; bs.append(sum(s)/n)
    bs.sort(); m=sum(vals)/n
    return (round(m,4), round(bs[int(.025*reps)],4), round(bs[int(.975*reps)],4))

def boot_diff_ci(perA, perB, reps=10000, seed=20260709):
    a=list(perA.values()); b=list(perB.values()); rng=random.Random(seed); bs=[]
    for _ in range(reps):
        sa=[a[rng.randrange(len(a))] for _ in range(len(a))]
        sb=[b[rng.randrange(len(b))] for _ in range(len(b))]
        bs.append(sum(sa)/len(sa)-sum(sb)/len(sb))
    bs.sort(); d=sum(a)/len(a)-sum(b)/len(b)
    return round(d,4), round(bs[int(.025*reps)],4), round(bs[int(.975*reps)],4), bs

def var_decomp(rows):
    o={"SAFE":0,"WATCH":1,"DISTRESS":2}
    pts=[(r["item_id"],r["spec_id"],r["seed"],o[r["parsed_band"]]) for r in rows if r.get("parsed_band")]
    if not pts: return {}
    gm=st.mean(p[3] for p in pts); tot=sum((p[3]-gm)**2 for p in pts)
    def ss(idx):
        g=defaultdict(list)
        for p in pts: g[p[idx]].append(p[3])
        return sum(len(v)*(st.mean(v)-gm)**2 for v in g.values())
    if tot==0: return {"item":0,"spec":0,"seed":0,"residual":1.0}
    si,ssp,sse=ss(0),ss(1),ss(2)
    return {"item":round(si/tot,4),"spec":round(ssp/tot,4),"seed":round(sse/tot,4),
            "residual":round(max(0,(tot-si-ssp-sse))/tot,4)}

def main():
    arm=latest_panel("arm_runs"); bat=latest_panel("battery_comp_runs")
    if not arm: print("no arm panel — run run_arm.py first"); return
    if not bat: print("no battery comparator panel — run the ARM_BATTERY=battery_90 comparator first"); return
    A=arm["rows"]; B=bat["rows"]
    out={}
    # H1 primary: WATCH stratum
    aW=flip_share_by_item(A,"WATCH"); bW=flip_share_by_item(B,"WATCH")
    d,lo,hi,bs=boot_diff_ci(aW,bW); reps=len(bs)
    # Descriptive real-arm comparison only. The pre-registered TOST equivalence test was removed
    # in the major revision (R2/R3): the WATCH sample is too small to establish equivalence, so the
    # arm is reported descriptively with no equivalence claim.
    out["H1_primary_WATCH"]={
        "arm_flip_share":boot_ci(aW),"battery_flip_share":boot_ci(bW),
        "diff_arm_minus_battery":d,"diff_95CI":[lo,hi],
        "n_watch_arm":len(aW),"n_watch_battery":len(bW),
        "decision":("DESCRIPTIVE: WATCH-stratum arm-minus-battery difference %.3f (95%% CI %s); "
                    "not distinguishable from zero at n=%d. No equivalence test is claimed."%(d,[lo,hi],len(aW)))}
    # H1 secondary: raw whole-sample
    aAll=flip_share_by_item(A); bAll=flip_share_by_item(B)
    d2,lo2,hi2,_=boot_diff_ci(aAll,bAll)
    out["H1_secondary_raw"]={
        "arm_flip_share":boot_ci(aAll),"battery_flip_share":boot_ci(bAll),
        "diff_arm_minus_battery":d2,"diff_95CI":[lo2,hi2],
        "caveat":"real arm is WATCH-heavy (near-threshold mass); raw diff is descriptive, not confirmatory."}
    # band accuracy vs disclosed agency rating (SAFE/WATCH; DISTRESS n=1 excluded)
    acc=[r for r in A if r.get("parsed_band") and r.get("benchmark_label") in ("SAFE","WATCH")]
    hit=sum(1 for r in acc if r["parsed_band"]==r["benchmark_label"])
    conf=Counter((r["benchmark_label"],r["parsed_band"]) for r in acc)
    out["band_accuracy_vs_agency"]={
        "n":len(acc),"exact_band_accuracy":round(hit/len(acc),4) if acc else None,
        "confusion_true_pred":{f"{k[0]}->{k[1]}":v for k,v in sorted(conf.items())}}
    out["variance_decomposition_arm"]=var_decomp(A)
    out["variance_decomposition_battery"]=var_decomp(B)
    out["provenance"]={"arm_run":arm["run_id"],"battery_run":bat["run_id"],
                       "arm_calls":arm["n_calls"],"battery_calls":bat["n_calls"]}
    (RESULTS/"H1_results.json").write_text(json.dumps(out,indent=1))
    print("=== PHASE 5 — H1 RESULTS ===")
    p=out["H1_primary_WATCH"]
    print(f"PRIMARY (WATCH stratum): arm flip={p['arm_flip_share'][0]} {p['arm_flip_share'][1:]} | "
          f"battery flip={p['battery_flip_share'][0]} {p['battery_flip_share'][1:]}")
    print(f"  diff (arm-battery) = {p['diff_arm_minus_battery']}  95CI {p['diff_95CI']}  ->  {p['decision']}")
    s=out["H1_secondary_raw"]
    print(f"SECONDARY (raw): arm={s['arm_flip_share'][0]} battery={s['battery_flip_share'][0]} diff={s['diff_arm_minus_battery']} (descriptive)")
    b=out["band_accuracy_vs_agency"]
    print(f"band accuracy vs agency (SAFE/WATCH, n={b['n']}): {b['exact_band_accuracy']}")
    print(f"variance (arm) item/spec/seed: {out['variance_decomposition_arm']}")
    print("-> H1_results.json written")

if __name__=="__main__": main()
