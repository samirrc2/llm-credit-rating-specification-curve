#!/usr/bin/env bash
# Build paper/manuscript_anonymous_tracked.pdf: the anonymous tracked-changes manuscript.
#
# Blind FIRST, then mark the blinded pair. Marking first and blinding after does not work:
# mark_changes inserts markup into the very sentences make_blinded's rules match, and
# make_blinded then refuses rather than emit a half-blinded document. That refusal is correct,
# so the order is the fix.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/Library/TinyTeX/bin/universal-darwin:$PATH"
PY="${PY:-python3}"

BASE="paper/_rev1_blinded.tex"
NEW="paper/manuscript_anonymous.tex"
STEM="_marked_blinded"
OUT="paper/manuscript_anonymous_tracked.pdf"

"$PY" - <<'PYX'
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("mb", "build/make_blinded.py")
mb = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(mb)
except SystemExit: pass
src = pathlib.Path("paper/manuscript_round1_baseline.tex").read_text(encoding="utf-8")
pathlib.Path("paper/_rev1_blinded.tex").write_text(mb.blind(src), encoding="utf-8")
PYX

"$PY" build/mark_changes.py "$BASE" "$NEW" "paper/$STEM.tex"

run_tex() { perl -e 'alarm 180; exec @ARGV' pdflatex -interaction=nonstopmode "$1" >/dev/null 2>&1 || true; }
( cd paper
  for i in 1 2 3; do run_tex "$STEM.tex"; done
  bibtex "$STEM" >/dev/null 2>&1 || true
  for j in 1 2 3 4 5 6; do
    run_tex "$STEM.tex"
    tot=$(grep -o 'lastpage}{[0-9]*}' "$STEM.aux" 2>/dev/null | tail -1 | grep -oE '[0-9]+')
    pages=$(grep -o "Output written on $STEM.pdf ([0-9]* pages" "$STEM.log" | tail -1 | grep -oE '[0-9]+')
    # an if, not "[ ] && break": as a loop's last statement that returns 1 when the
    # condition is false, which aborts the subshell under set -e
    if [ -n "$tot" ] && [ "$tot" = "$pages" ]; then break; fi
  done )

[ -f "paper/$STEM.pdf" ] || { echo "   FAILED: no anonymous tracked PDF produced" >&2
  grep -E '^! ' "paper/$STEM.log" | head -5 >&2 || true; exit 1; }
ERRS=$(grep -cE '^! ' "paper/$STEM.log" || true)
[ "$ERRS" -eq 0 ] || { echo "   FAILED: $ERRS LaTeX errors in the anonymous tracked copy" >&2
  grep -nE '^! ' "paper/$STEM.log" | head -5 >&2; exit 1; }

# the anonymous copy must not carry an identity
"$PY" - <<'PYX'
import re, sys, pymupdf
t = "".join(p.get_text() for p in pymupdf.open("paper/_marked_blinded.pdf"))
leaks = [w for w in ("Chincholikar", "Chawla", "samir", "robin.chawla", "New York",
                     "0009-0007", "github.com", "zenodo") if w.lower() in t.lower()]
if leaks:
    sys.exit(f"   FAILED: identity leak in the anonymous tracked copy: {leaks}")
print("   identity check: no author name, email, ORCID, city, repo or DOI survives")
PYX

cp "paper/$STEM.pdf" "$OUT"
grep -o "Output written on $STEM.pdf ([0-9]* pages" "paper/$STEM.log" | head -1 | sed 's/^/   /'
echo "   -> $OUT"
rm -f paper/$STEM.aux paper/$STEM.log paper/$STEM.out paper/$STEM.bbl paper/$STEM.blg paper/$STEM.pdf paper/_rev1_blinded.tex
