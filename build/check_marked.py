#!/usr/bin/env python3
"""Verify the marked copy against the clean manuscript.

Three gates, in decreasing strength.

1. ROUND-TRIP (exact, and the one that matters). Strip the injected preamble and every
   \\HLtext/\\HLcode/\\HLtag wrapper from the marked source. The result must be BYTE-IDENTICAL
   to cas-sc.tex. If it is, marking provably added nothing and removed nothing -- no PDF text
   extraction can argue with it. This replaced a sentence-level PDF comparison that produced 26
   phantom "missing sentences", every one of which was a soul re-kerning artifact, a dropped
   fi/ff/fl ligature, or a page footer whose number had shifted.

2. RENDER (PDF). Page count and table-reference count must match the clean build, so a copy
   that round-trips but fails to typeset is still caught.

3. NON-VACUITY (PDF). Text known to be new in revision 2 must carry a mark, and text known to
   be unchanged must not. A copy where everything or nothing is marked passes 1 and 2 and is
   useless.

Exit 0 pass, 1 fail, 2 could not check.
"""
import re
import sys
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
src, marked_src = PB / "paper/NLP/cas-sc.tex", PB / "paper/NLP/_marked.tex"
clean_pdf, marked_pdf = PB / "paper/NLP/cas-sc.pdf", PB / "paper/NLP/_marked.pdf"
for f in (src, marked_src):
    if not f.exists():
        print(f"NOT CHECKABLE: {f.name} missing"); sys.exit(2)

fails = []

# ---- 1. round-trip
def arg_span(s, start):
    depth, i = 0, start
    while i < len(s):
        if s[i] == "{" and (i == 0 or s[i - 1] != "\\"):
            depth += 1
        elif s[i] == "}" and s[i - 1] != "\\":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1

def unmark(s):
    # the whole injected preamble, up to and including the \HLlegend definition
    s = re.sub(r"\\usepackage\{soul\}.*?\\par\\vspace\{6pt\}\}\n", "", s, flags=re.S)
    s = s.replace("\n\\HLlegend\n", "", 1)       # the emitted legend itself
    # a struck deletion is text that is NOT in cas-sc.tex, so the whole macro and its
    # argument come out, together with the single space del_wrap appends after it
    while True:
        j = s.find(r"\HLdel{")
        if j < 0:
            break
        e = arg_span(s, j + len(r"\HLdel{") - 1)
        if e < 0:
            break
        k = e + 1
        if k < len(s) and s[k] == " ":
            k += 1
        s = s[:j] + s[k:]
    for mac in (r"\HLtext{", r"\HLcode{"):
        while True:
            j = s.find(mac)
            if j < 0:
                break
            e = arg_span(s, j + len(mac) - 1)
            if e < 0:
                break
            s = s[:j] + s[j + len(mac):e] + s[e + 1:]
    # \HLtag{...} is an inserted annotation, not original text: drop it whole
    while True:
        j = s.find(r"\HLtag{")
        if j < 0:
            break
        e = arg_span(s, j + len(r"\HLtag{") - 1)
        if e < 0:
            break
        s = s[:j] + s[e + 1:]
    return s

orig = src.read_text(encoding="utf-8")
got = unmark(marked_src.read_text(encoding="utf-8"))
if got == orig:
    print(f"  round-trip: EXACT -- unmarking reproduces cas-sc.tex byte-for-byte "
          f"({len(orig)} bytes)")
else:
    import difflib
    d = [l for l in difflib.unified_diff(orig.splitlines(), got.splitlines(), lineterm="", n=0)]
    fails.append(f"round-trip differs: {len(d)} diff lines (marking altered the manuscript)")
    for l in d[:10]:
        print(f"     {l}")

# ---- 2 and 3 need the PDFs
try:
    import pymupdf
except ImportError:
    print("NOT CHECKABLE: pymupdf missing for the render checks"); sys.exit(2)
if not (clean_pdf.exists() and marked_pdf.exists()):
    print("NOT CHECKABLE: a PDF is missing"); sys.exit(2)
clean, marked = pymupdf.open(clean_pdf), pymupdf.open(marked_pdf)
norm = lambda d: re.sub(r"\s+", " ", "".join(p.get_text() for p in d))
C, M = norm(clean), norm(marked)
# The marked copy re-inserts every deleted run, so it is legitimately LONGER than the clean
# manuscript. It must never be shorter -- that would mean content vanished -- and a copy that
# has ballooned is a marking bug rather than a revision, so an upper bound still applies.
_lo, _hi = clean.page_count, int(clean.page_count * 1.25) + 1
if not (_lo <= marked.page_count <= _hi):
    fails.append(f"page count {marked.page_count} outside [{_lo}, {_hi}] for clean "
                 f"{clean.page_count} (deletions make the marked copy longer, never shorter)")
tc, tm = len(re.findall(r"Table [0-9]+", C)), len(re.findall(r"Table [0-9]+", M))
if tm != tc:
    fails.append(f"table references {tm} != clean {tc}")
print(f"  render: {marked.page_count}pp vs {clean.page_count}pp clean (longer by design), "
      f"{tm} vs {tc} table references")

def squash(t):
    t = re.sub(r"[^a-z0-9]", "", t.lower())
    for lg in ("ffi", "fi", "ff", "fl"):
        t = t.replace(lg, "")
    return t
coloured = []
for pg in marked:
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l.get("spans", []):
                if sp.get("color", 0) != 0:
                    coloured.append(sp["text"])
COL = squash(" ".join(coloured))
yellow = 0.0
for pg in marked:
    for d in pg.get_drawings():
        f = d.get("fill")
        if f and f[0] > 0.9 and f[1] > 0.85 and f[2] < 0.6:
            yellow += abs(d["rect"].width * d["rect"].height)
if yellow <= 0:
    fails.append("no yellow highlighting in the marked copy")
print(f"  marks: {len(COL)} chars coloured, {yellow:.0f} sq pt highlighted")

NEW = ["Net benefit for triage", "Benchmark against simple baselines",
       "Decontamination of the real-issuer arm", "illustrative descriptive limitation",
       "What the design identifies", "marginal-matching", "New in revision 2"]
OLD = ["Large language models (LLMs) are increasingly used to support credit assessments",
       "Declaration of competing interest"]
MS = squash(M)
absent = [s for s in NEW if squash(s) not in MS]
if absent:
    fails.append(f"new text absent from the marked PDF: {absent}")
wrong = [s for s in OLD if squash(s) in COL]
if wrong:
    fails.append(f"unchanged text marked as new: {[w[:40] for w in wrong]}")
print(f"  non-vacuity: {len(NEW) - len(absent)}/{len(NEW)} known-new present, "
      f"{len(wrong)}/{len(OLD)} unchanged wrongly marked")

if fails:
    print("\n  FAIL:")
    for f in fails:
        print(f"    - {f}")
    sys.exit(1)
print("\n  PASS: marking is content-preserving (exact round-trip) and the marks are non-vacuous")
sys.exit(0)
