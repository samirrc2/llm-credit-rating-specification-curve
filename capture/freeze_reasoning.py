#!/usr/bin/env python3
"""Freeze the reasoning-architecture arm: verify coverage, write a combined SHA-256 manifest
(same scheme as MANIFEST_FLAGSHIP). Run ONCE after run_reasoning.py reports 1620/1620.
  python3 freeze_reasoning.py
Writes manifest/MANIFEST_REASONING.sha256 + a freeze report. After this the corpus is immutable."""
from __future__ import annotations
import sys, json, hashlib
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
RUNS=HERE/"reasoning_runs"; MAN=ROOT/"manifest"; MAN.mkdir(exist_ok=True)
if len(sys.argv)>1: RUN=RUNS/(sys.argv[1] if sys.argv[1].startswith("run_") else f"run_{sys.argv[1]}")
elif (RUNS/".active_run").exists(): RUN=RUNS/f"run_{(RUNS/'.active_run').read_text().strip()}"
else:
    c=sorted(RUNS.glob("run_*")); RUN=c[-1] if c else sys.exit("no reasoning run folder")
RAW=RUN/"raw"; files=sorted(RAW.glob("*.json")); EXP=45*12*3
ok=empty=0; ig=Counter()
for p in files:
    try: d=json.loads(p.read_text())
    except: continue
    if d.get("ok") and d.get("parsed_ighy"): ok+=1; ig[d["parsed_ighy"]]+=1
    else: empty+=1
h=hashlib.sha256()
for p in files: h.update(p.read_bytes())
pan=RUN/"reasoning_panel.json"
if pan.exists(): h.update(pan.read_bytes())
dg=h.hexdigest()
model=""
if pan.exists(): model=json.loads(pan.read_text()).get("model","")
desc=f"REASONING-ARCHITECTURE ARM - {RUN.name} ({model}; 12 specs x 45 credit items x 3 seeds; cells {len(files)}/{EXP}, ok {ok})"
(MAN/"MANIFEST_REASONING.sha256").write_text(f"{dg}  {desc}\n")
rep=[f"# Reasoning-arm freeze report","",f"- run: {RUN.name}",f"- model: {model}",
     f"- cells: {len(files)}/{EXP}",f"- ok: {ok} | empty/failed: {empty}",f"- IG/HY dist: {dict(ig)}",
     f"- combined SHA-256: {dg}","","Frozen. Downstream analysis reads this corpus offline; do not modify."]
(RUN/"REASONING_FREEZE_REPORT.txt").write_text("\n".join(rep)); print("\n".join(rep))
print("\nwrote manifest/MANIFEST_REASONING.sha256")
if len(files)!=EXP or empty: print(f"\n!! incomplete ({len(files)}/{EXP}, {empty} empty) -- re-run run_reasoning.py before trusting this freeze.")
