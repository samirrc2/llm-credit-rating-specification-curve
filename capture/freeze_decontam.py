#!/usr/bin/env python3
"""Freeze a decontamination run: copy it under data/frozen/ and hash every byte.

"Frozen" has to mean something checkable, so this writes a MANIFEST with the sha256 of every raw
call file plus a single root hash over the sorted (path, sha256) list. verify_frozen() recomputes
both and fails on any edit, addition or deletion. The frozen copy is made read-only.

  python3 capture/freeze_decontam.py            # freeze the active run
  python3 capture/freeze_decontam.py --verify   # re-verify an existing frozen arm
"""
import hashlib, json, os, shutil, stat, sys
from datetime import datetime, timezone
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
RUNS = PB / "capture/decontam_runs"
DEST = PB / "data/frozen/realarm_decontam"

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def manifest_for(root):
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.json":
            rows.append({"path": str(p.relative_to(root)), "sha256": sha(p), "bytes": p.stat().st_size})
    root_hash = hashlib.sha256(
        "\n".join(f"{r['path']} {r['sha256']}" for r in rows).encode()).hexdigest()
    return rows, root_hash

def verify():
    mf = DEST / "MANIFEST.json"
    if not mf.exists():
        print("NOT FROZEN: no MANIFEST.json"); return 2
    m = json.load(open(mf))
    rows, root_hash = manifest_for(DEST)
    have = {r["path"]: r["sha256"] for r in rows}
    want = {r["path"]: r["sha256"] for r in m["files"]}
    changed = [p for p in want if p in have and have[p] != want[p]]
    missing = [p for p in want if p not in have]
    added = [p for p in have if p not in want]
    ok = not (changed or missing or added) and root_hash == m["root_sha256"]
    print(f"  frozen files: {len(want)}   root {m['root_sha256'][:16]}")
    print(f"  recomputed  : {len(have)}   root {root_hash[:16]}")
    for lab, lst in (("CHANGED", changed), ("MISSING", missing), ("ADDED", added)):
        if lst:
            print(f"  {lab}: {len(lst)}")
            for p in lst[:5]:
                print(f"     {p}")
    print("\n  " + ("PASS: frozen arm is intact and matches its manifest"
                    if ok else "FAIL: the frozen arm has been modified"))
    return 0 if ok else 1

def freeze():
    active = (RUNS / ".active_run")
    if not active.exists():
        print("no active run to freeze"); return 2
    src = RUNS / f"run_{active.read_text().strip()}"
    if not src.exists():
        print(f"missing {src}"); return 2
    meta = json.load(open(src / "run_meta.json")) if (src / "run_meta.json").exists() else {}
    if meta.get("mock"):
        print("refusing to freeze a MOCK run"); return 2
    if DEST.exists():
        # never silently overwrite a frozen arm
        print(f"{DEST.relative_to(PB)} already exists; refusing to overwrite. "
              f"Move it aside first."); return 2
    DEST.mkdir(parents=True)
    for p in sorted(src.rglob("*")):
        if p.is_file():
            d = DEST / p.relative_to(src)
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, d)
    rows, root_hash = manifest_for(DEST)
    json.dump({"frozen_utc": datetime.now(timezone.utc).isoformat(),
               "source_run": src.name, "run_meta": meta,
               "spec": meta.get("spec"), "spec_sha256": meta.get("spec_sha256"),
               "n_files": len(rows), "root_sha256": root_hash, "files": rows},
              open(DEST / "MANIFEST.json", "w"), indent=1)
    for p in DEST.rglob("*"):
        if p.is_file():
            os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)   # read-only
    print(f"  froze {len(rows)} files from {src.name}")
    print(f"  root sha256 {root_hash}")
    print(f"  -> {DEST.relative_to(PB)} (read-only)")
    return 0

if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else freeze())
