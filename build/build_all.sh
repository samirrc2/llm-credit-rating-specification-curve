#!/usr/bin/env bash
# Rebuild and propagate every deliverable, then run every gate.
#
# This exists because propagation kept getting missed by hand: manuscript_full.pdf would be rebuilt while
# revision_2/manuscript_full.pdf, submission/manuscript_full.pdf, the blinded copy and the highlighted
# copy silently kept older content. Nothing here is optional and nothing is copied by hand.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/Library/TinyTeX/bin/universal-darwin:$PATH"
PY="$(command -v python3)"
R="paper"
S="paper"
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
( cd paper
  for i in 1 2 3; do run_tex manuscript_full.tex; done
  bibtex manuscript_full >/dev/null 2>&1 || true
  settle manuscript_full )
ERR=$(grep -cE '^! ' paper/manuscript_full.log || true)
[ "$ERR" -eq 0 ] || { echo "   FAILED: $ERR TeX errors in manuscript_full"; grep -nE '^! ' paper/manuscript_full.log | head -5; exit 1; }

echo "== 3. response letter"
( cd "$R"; for i in 1 2; do run_tex response_to_reviewers.tex; done )
ERR=$(grep -cE '^! ' "$R/response_to_reviewers.log" || true)
[ "$ERR" -eq 0 ] || { echo "   FAILED: $ERR TeX errors in the letter"; exit 1; }

echo "== 4. blinded manuscript (derived, never hand-edited)"
"$PY" build/make_blinded.py
# The blinded copy used to live in its own directory and needed these support files copied in.
# paper/ is flat now, so they are already beside it and copying would be a file onto itself.
( cd "$S"
  for i in 1 2 3; do run_tex manuscript_anonymous.tex; done
  bibtex manuscript_anonymous >/dev/null 2>&1 || true
  settle manuscript_anonymous )
ERR=$(grep -cE '^! ' "$S/manuscript_anonymous.log" || true)
MISSFIG=$(grep -c 'not found' "$S/manuscript_anonymous.log" || true)
[ "$ERR" -eq 0 ] && [ "$MISSFIG" -eq 0 ] || { echo "   FAILED: $ERR TeX errors, $MISSFIG missing figures in blinded"; exit 1; }

echo "== 5. propagate -- nothing to do, by design"
# paper/ is flat, so the master IS the deliverable and there is nothing to copy. This step
# used to fan manuscript_full.pdf/.tex out to submission/ and revision_2/ under three different names,
# which is exactly how those copies went stale: the fan-out was easy to forget, and when it was
# forgotten the reviewer received an older manuscript than the one the gates had checked.
# Keeping one file per artifact removes the failure mode instead of guarding against it.

echo "== 6. highlighted copy (built last: it diffs the final manuscript)"
bash build/build_highlighted.sh

"$PY" build/make_highlights.py

echo "== 6b. anonymous tracked copy"
bash build/build_highlighted_blinded.sh

echo "== 6c. docx companions"
"$PY" build/make_docx.py

echo "== 6d. anonymised reproducibility capsule"
"$PY" build/make_capsule.py

echo "== 7. gates"
"$PY" "$HOME/.claude/skills/con1/scripts/check_citations.py" --online \
      --exemptions build/citation_exemptions.json | tail -1
"$PY" build/check_binding.py        | tail -1
"$PY" build/check_coverage.py       | tail -1
"$PY" build/check_tables_fresh.py   | tail -1
"$PY" build/check_denominators.py   | tail -1
"$PY" build/check_readme.py         | tail -1
"$PY" build/make_highlights.py --check | tail -1
"$PY" build/check_docx_parity.py    | tail -1
"$PY" build/make_capsule.py --check   | tail -1
"$PY" build/make_blinded.py --check | tail -1
"$PY" capture/freeze_decontam.py --verify | tail -1

echo "== 8. clean artefacts"
for d in paper "$R" "$S"; do
  for e in aux log out blg bbl abs spl toc; do rm -f "$d"/*."$e"; done
done
rm -f paper/_marked.tex paper/_marked.pdf

echo "== 9. every deliverable, by content"
"$PY" - <<'PYX'
import pymupdf, re, hashlib, os
def T(f): return re.sub(r"\s+", " ", "".join(p.get_text() for p in pymupdf.open(f)))
# Markers are PER DOCUMENT. The response letter legitimately contains neither "1,361" (it
# reports per-experiment denominators instead) nor the word "Decontamination" (it refers to
# Section 3.7), so applying the manuscript's markers to it produced a false STALE.
MS = ["4,316", "1,361", "62 attempted", "Decontamination"]
LT = ["4,316", "0.504", "0.644", "19.4", "0.176"]   # the letter's own figures
R = "paper/"; S = "paper/"
# One file per artifact. The old list named manuscript_full.pdf three times under three paths, which is
# what the flattening removed.
TARGETS = [("paper/manuscript_full.pdf", MS), ("paper/manuscript_anonymous.pdf", MS),
           ("paper/manuscript_full_tracked.pdf", MS), ("paper/manuscript_anonymous_tracked.pdf", MS),
           ("paper/response_to_reviewers.pdf", LT)]
for f, markers in TARGETS:
    if not os.path.exists(f):
        print(f"   {'--':>7}  {'-'*10}  ABSENT {f}"); continue
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
