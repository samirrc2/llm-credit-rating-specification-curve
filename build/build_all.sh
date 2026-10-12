#!/usr/bin/env bash
# Rebuild and propagate every deliverable, then run every gate.
#
# This exists because propagation kept getting missed by hand: cas-sc.pdf would be rebuilt while
# revision_2/cas-sc-revised-r2.pdf, submission/cas-sc.pdf, the blinded copy and the highlighted
# copy silently kept older content. Nothing here is optional and nothing is copied by hand.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/Library/TinyTeX/bin/universal-darwin:$PATH"
PY="$(command -v python3)"
R="paper/NLP/submission/revision_2"
S="paper/NLP/submission"
run_tex() { perl -e 'alarm 240; exec @ARGV' pdflatex -interaction=nonstopmode "$1" >/dev/null 2>&1 || true; }

echo "== 1. regenerate table bodies from the result JSONs"
"$PY" build/make_sis_tables.py
"$PY" build/make_decontam_table.py

echo "== 2. master manuscript"
# cas-common.sty writes \lastpage into the .aux at end of document, so the page-total in the
# footer is always one pass behind. With five passes the footer read "Page 28 of 27" on a
# 29-page document. Keep running until the recorded total equals the real page count.
settle() {
  local stem="$1" i tot pages
  for i in 1 2 3 4 5 6; do
    run_tex "$stem.tex"
    tot=$(grep -o 'csxdef{lastpage}{[0-9]*}' "$stem.aux" 2>/dev/null | tail -1 | grep -oE '[0-9]+')
    pages=$(grep -o "Output written on $stem.pdf ([0-9]* pages" "$stem.log" | tail -1 | grep -oE '[0-9]+')
    if [ -n "$tot" ] && [ "$tot" = "$pages" ]; then return 0; fi
  done
  echo "   WARNING: page total ($tot) still differs from page count ($pages) for $stem" >&2
  return 0
}
( cd paper/NLP
  for i in 1 2 3; do run_tex cas-sc.tex; done
  bibtex cas-sc >/dev/null 2>&1 || true
  settle cas-sc )
ERR=$(grep -cE '^! ' paper/NLP/cas-sc.log || true)
[ "$ERR" -eq 0 ] || { echo "   FAILED: $ERR TeX errors in cas-sc"; grep -nE '^! ' paper/NLP/cas-sc.log | head -5; exit 1; }

echo "== 3. response letter"
( cd "$R"; for i in 1 2; do run_tex RESPONSE_TO_REVIEWERS_R2.tex; done )
ERR=$(grep -cE '^! ' "$R/RESPONSE_TO_REVIEWERS_R2.log" || true)
[ "$ERR" -eq 0 ] || { echo "   FAILED: $ERR TeX errors in the letter"; exit 1; }

echo "== 4. blinded manuscript (derived, never hand-edited)"
"$PY" build/make_blinded.py
for f in references.bib tab_sisbase_body.tex tab_sisdca_body.tex tab_decontam_body.tex highlights.txt; do
  cp "paper/NLP/$f" "$S/$f"
done
( cd "$S"
  for i in 1 2 3; do run_tex cas-sc-blinded.tex; done
  bibtex cas-sc-blinded >/dev/null 2>&1 || true
  settle cas-sc-blinded )
ERR=$(grep -cE '^! ' "$S/cas-sc-blinded.log" || true)
MISSFIG=$(grep -c 'not found' "$S/cas-sc-blinded.log" || true)
[ "$ERR" -eq 0 ] && [ "$MISSFIG" -eq 0 ] || { echo "   FAILED: $ERR TeX errors, $MISSFIG missing figures in blinded"; exit 1; }

echo "== 5. propagate (the step that kept being missed)"
cp paper/NLP/cas-sc.pdf      "$R/cas-sc-revised-r2.pdf"
cp paper/NLP/cas-sc.tex      "$R/cas-sc-revised-r2.tex"
cp paper/NLP/highlights.txt  "$R/highlights.txt"
cp paper/NLP/cas-sc.pdf      "$S/cas-sc.pdf"
cp paper/NLP/cas-sc.tex      "$S/cas-sc.tex"

echo "== 6. highlighted copy (built last: it diffs the final manuscript)"
bash build/build_highlighted.sh

echo "== 7. gates"
"$PY" build/check_tables_fresh.py   | tail -1
"$PY" build/check_denominators.py   | tail -1
"$PY" build/make_blinded.py --check | tail -1
"$PY" capture/freeze_decontam.py --verify | tail -1

echo "== 8. clean artefacts"
for d in paper/NLP "$R" "$S"; do
  for e in aux log out blg bbl abs spl toc; do rm -f "$d"/*."$e"; done
done
rm -f paper/NLP/_marked.tex paper/NLP/_marked.pdf

echo "== 9. every deliverable, by content"
"$PY" - <<'PYX'
import pymupdf, re, hashlib
def T(f): return re.sub(r"\s+", " ", "".join(p.get_text() for p in pymupdf.open(f)))
# Markers are PER DOCUMENT. The response letter legitimately contains neither "1,361" (it
# reports per-experiment denominators instead) nor the word "Decontamination" (it refers to
# Section 3.7), so applying the manuscript's markers to it produced a false STALE.
MS = ["4,316", "1,361", "62 attempted", "Decontamination"]
LT = ["4,316", "62 attempted", "0.504", "0.644", "19.4"]
R = "paper/NLP/submission/revision_2/"; S = "paper/NLP/submission/"
TARGETS = [(R+"cas-sc-revised-r2.pdf", MS), (R+"RESPONSE_TO_REVIEWERS_R2.pdf", LT),
           (R+"highlighted_pdf.pdf", MS), (S+"cas-sc-blinded.pdf", MS),
           (S+"cas-sc.pdf", MS), ("paper/NLP/cas-sc.pdf", MS)]
for f, markers in TARGETS:
    t = T(f); d = pymupdf.open(f)
    miss = [k for k in markers if k not in t]
    # The footer total must equal the LAST PRINTED page number, not the physical page count:
    # the title page carries no footer, so printed = physical - 1 by design. Comparing against
    # d.page_count reported a false mismatch.
    foot = re.findall(r"Page (\d+) of (\d+)", t)
    if foot:
        tot = {b for _, b in foot}
        last_printed = max(int(a) for a, _ in foot)
        if len(tot) > 1:
            miss.append(f"footer totals disagree across pages: {sorted(tot)}")
        elif int(next(iter(tot))) != last_printed:
            miss.append(f"footer total {sorted(tot)} != last printed page {last_printed}")
    sha = hashlib.sha256(open(f, "rb").read()).hexdigest()[:10]
    print(f"   {d.page_count:3d}pp  {sha}  {'OK   ' if not miss else 'STALE'}  "
          f"{f}{'  missing ' + str(miss) if miss else ''}")
PYX
