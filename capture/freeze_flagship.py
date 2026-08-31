#!/usr/bin/env python3
"""Freeze the flagship tier sub-run: verify coverage, then write a combined SHA-256
manifest in the SAME format as the other stages (single digest over sorted raw cells).
Run ONCE, after run_flagship.py reports 1620/1620.

  python3 freeze_flagship.py                 # freeze the active/latest flagship run
  python3 freeze_flagship.py run_20260830_XXXXXX   # freeze a specific run folder

Writes:  ../manifest/MANIFEST_FLAGSHIP.sha256   (digest + one-line description)
         <run>/FLAGSHIP_FREEZE_REPORT.txt       (human-readable coverage report)
After this is written, treat the corpus as immutable (like MANIFEST_RAW/REALARM)."""
from __future__ import annotations
import sys, json, hashlib
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = HERE / "flagship_runs"
MANIFEST = ROOT / "manifest"; MANIFEST.mkdir(exist_ok=True)

# ---- locate the run folder ------------------------------------------------------
if len(sys.argv) > 1:
    arg = sys.argv[1]
    RUN_DIR = RUNS / (arg if arg.startswith("run_") else f"run_{arg}")
elif (RUNS / ".active_run").exists():
    RUN_DIR = RUNS / f"run_{(RUNS / '.active_run').read_text().strip()}"
else:
    cands = sorted(RUNS.glob("run_*"))
    if not cands: sys.exit("No flagship run folder found under capture/flagship_runs/")
    RUN_DIR = cands[-1]
RAW = RUN_DIR / "raw"
if not RAW.exists(): sys.exit(f"No raw/ under {RUN_DIR}")

# ---- coverage check -------------------------------------------------------------
files = sorted(RAW.glob("*.json"))
EXPECTED = 45 * 12 * 3   # 1620
ok = empty = bad = 0
by_prov_ok = Counter(); by_prov_empty = Counter(); ighy = Counter()
for p in files:
    try:
        d = json.loads(p.read_text())
    except Exception:
        bad += 1; continue
    prov = d.get("provider", "?")
    if d.get("ok") and (d.get("raw_response") or "").strip() and d.get("parsed_ighy"):
        ok += 1; by_prov_ok[prov] += 1; ighy[d["parsed_ighy"]] += 1
    else:
        empty += 1; by_prov_empty[prov] += 1

# ---- combined SHA-256 over sorted raw cells (+ panel) — same scheme as MANIFEST_RAW
h = hashlib.sha256()
for p in files:
    h.update(p.read_bytes())
panel = RUN_DIR / "flagship_panel.json"
if panel.exists(): h.update(panel.read_bytes())
digest = h.hexdigest()

# ---- write manifest + report ----------------------------------------------------
desc = (f"FLAGSHIP TIER SUB-RUN - {RUN_DIR.name} (gpt-5.4 + gemini-3.1-pro-preview; "
        f"12 specs x 45 credit items x 3 seeds; cells {len(files)}/{EXPECTED}, ok {ok})")
(MANIFEST / "MANIFEST_FLAGSHIP.sha256").write_text(f"{digest}  {desc}\n")

report = [
    "# Flagship tier sub-run — freeze report", "",
    f"- run folder      : {RUN_DIR.name}",
    f"- cells on disk   : {len(files)} / {EXPECTED} expected",
    f"- ok (parsed)     : {ok}",
    f"- empty/failed    : {empty}" + (f"  {dict(by_prov_empty)}" if empty else ""),
    f"- unreadable      : {bad}",
    f"- ok by provider  : {dict(by_prov_ok)}",
    f"- IG/HY dist (ok) : {dict(ighy)}",
    f"- combined SHA-256: {digest}", "",
    "Frozen. Downstream tier analysis reads this corpus; do not modify after this point.",
]
(RUN_DIR / "FLAGSHIP_FREEZE_REPORT.txt").write_text("\n".join(report))
print("\n".join(report))
print(f"\nwrote manifest/MANIFEST_FLAGSHIP.sha256")
if len(files) != EXPECTED or empty:
    print(f"\n!! coverage incomplete ({len(files)}/{EXPECTED}, {empty} empty) — "
          f"re-run run_flagship.py to fill gaps BEFORE trusting this freeze.")
