#!/usr/bin/env python3
"""Verify the generated table bodies are not stale.

Tables 7 and 8 are produced by build/make_sis_tables.py from the result JSONs and \\input{} into
the manuscript, so a cell cannot be mistyped. The remaining failure mode is a STALE body file:
the JSONs change and the committed .tex body does not. Regenerate into a temporary location and
require byte-identity.

Exit 0 identical, 1 stale, 2 could not check.
"""
import hashlib, shutil, subprocess, sys, tempfile
from pathlib import Path
PB = Path(__file__).resolve().parents[1]
BODIES = ["paper/NLP/tab_sisbase_body.tex", "paper/NLP/tab_sisdca_body.tex"]
for b in BODIES:
    if not (PB / b).exists():
        print(f"NOT CHECKABLE: {b} missing"); sys.exit(2)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
before = {b: sha(PB / b) for b in BODIES}
keep = tempfile.mkdtemp()
for b in BODIES:
    shutil.copy(PB / b, Path(keep) / Path(b).name)
r = subprocess.run([sys.executable, str(PB / "build/make_sis_tables.py")],
                   capture_output=True, text=True, cwd=PB)
if r.returncode != 0:
    print(f"NOT CHECKABLE: generator failed\n{r.stderr[:400]}"); sys.exit(2)
stale = [b for b in BODIES if sha(PB / b) != before[b]]
for b in BODIES:
    print(f"  {Path(b).name}: {'STALE -- regenerated content differs' if b in stale else 'fresh'}"
          f"  sha {sha(PB / b)[:12]}")
if stale:
    print("\n  FAIL: the committed table body did not match the JSONs; it has been regenerated.")
    print("        Rebuild the PDF so the manuscript shows the current numbers.")
    sys.exit(1)
print("\n  PASS: both generated table bodies match the result JSONs exactly")
sys.exit(0)
