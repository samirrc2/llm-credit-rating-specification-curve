#!/usr/bin/env python3
"""Reverse coverage: every numeric literal printed in the manuscript must be reachable from data.

con1's weakest-link finding for this paper was that the existing gates (denominators, generated
table bodies, frozen-arm integrity, blinding) cover only a slice of the manuscript. Fault
injection showed a swap of two REAL printed AUCs (0.936 <-> 0.951) passing all four, and an
invented number inserted into Results passing all four.

This walks every numeric literal in the manuscript body and demands each one be either
  (a) present in some results/*.json at the precision the paper prints, or
  (b) listed in build/coverage_exemptions.json with a stated reason.

It does NOT catch a swap between two numbers that are both real results -- that needs anchored
binding, which is reported as still missing. Exit 0 all covered, 1 uncovered literals, 2 not
checkable.
"""
import json, re, sys
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
MS = PB / "paper/manuscript_full.tex"
EX = PB / "build/coverage_exemptions.json"
if not MS.exists():
    print("NOT CHECKABLE: manuscript missing"); sys.exit(2)
res = sorted((PB / "results").glob("*.json"))
if not res:
    print("NOT CHECKABLE: no result JSONs"); sys.exit(2)

# every number any analysis produced, at several roundings
pool = set()
def harvest(o):
    if isinstance(o, dict):
        for v in o.values(): harvest(v)
    elif isinstance(o, list):
        for v in o: harvest(v)
    elif isinstance(o, bool):
        pass
    elif isinstance(o, (int, float)):
        for nd in range(0, 7):
            for v in (float(o), float(o) * 100):
                # Python's round() is banker's rounding, so a deposited 0.3545 never produced
                # the 0.355 the paper prints. Offer both conventions.
                import decimal
                for rounding in (decimal.ROUND_HALF_EVEN, decimal.ROUND_HALF_UP):
                    t = str(decimal.Decimal(repr(v)).quantize(
                        decimal.Decimal(1).scaleb(-nd), rounding=rounding))
                    pool.add(t); pool.add(t.rstrip("0").rstrip(".") or "0")
                t = f"{round(v, nd):.{nd}f}"
                pool.add(t)                                    # as printed, e.g. 0.690
                pool.add(t.rstrip("0").rstrip(".") or "0")     # and trimmed, e.g. 0.69
                # stripping trailing zeros alone made the pool miss every figure the paper
                # prints with a trailing zero, which produced six phantom uncovered literals.
    elif isinstance(o, str):
        for m in re.finditer(r"-?\d+\.?\d*", o): pool.add(m.group(0))
for f in res:
    try: harvest(json.load(open(f)))
    except Exception: pass

s = MS.read_text(encoding="utf-8")
s = s[s.index(r"\begin{document}"):]
# strip what is not a reported quantity: comments, labels/refs/cites, paths, tikz, the bib
s = re.sub(r"%.*", "", s)
for cmd in ("label","ref","eqref","cite","citet","citep","path","texttt","url","includegraphics",
            "input","usepackage","definecolor","newcommand","RenewDocumentCommand","AtBeginDocument",
            "AtEndDocument","bibliography","bibliographystyle","csxdef","pageref"):
    s = re.sub(r"\\" + cmd + r"\*?(?:\[[^\]]*\])?\{[^{}]*\}", " ", s)
s = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", " ", s, flags=re.S)
s = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ", s, flags=re.S)
# LaTeX writes thousands as 4{,}316. Without collapsing that, the scanner saw "4" and "316"
# as separate literals and reported eight phantom uncovered numbers.
s = s.replace("{,}", "")

exempt = json.load(open(EX)) if EX.exists() else {}
lits, uncovered = {}, {}
for m in re.finditer(r"(?<![\d.A-Za-z-])(\d+(?:\.\d+)?)(?![\d]*[A-Za-z])", s):
    v = m.group(1)
    ctx = re.sub(r"\s+", " ", s[max(0, m.start()-70):m.end()+30]).strip()
    lits.setdefault(v, ctx)
norm = lambda v: v.lstrip("0") or "0"
for v, ctx in lits.items():
    if v in exempt or norm(v) in exempt: continue
    if v in pool or norm(v) in pool or v.replace("{,}", "") in pool: continue
    if re.fullmatch(r"\d{1,2}", v): continue          # small integers: counts, k, section-like
    uncovered[v] = ctx
# Unsubstituted placeholders and digit-letter run-ons are not numeric literals, so the scan
# above cannot see them. They are the classic months-long survivors, so check separately.
STRAY = []
for pat, what in ((r"@[A-Z][A-Z0-9_]*@", "unsubstituted placeholder"),
                  (r"(?<![A-Za-z\\])\d+\.?\d*(?:LO|HI|TODO|XX|FIXME)\b", "digit-letter run-on"),
                  (r"TODO-VERIFY", "unverified citation marker")):
    for m in re.finditer(pat, s):
        STRAY.append((what, m.group(0)))
if STRAY:
    print(f"  STRAY MARKERS: {len(STRAY)}")
    for what, tok in STRAY[:10]:
        print(f"    {what}: {tok}")

print(f"  manuscript numeric literals: {len(lits)}")
print(f"  reachable from results/*.json: {len(lits)-len(uncovered)-sum(1 for v in lits if v in exempt)}")
print(f"  declared exemptions matched: {sum(1 for v in lits if v in exempt)}")
print(f"  UNCOVERED: {len(uncovered)}")
for v, ctx in sorted(uncovered.items())[:25]:
    print(f"    {v:>10}  ...{ctx[-66:]}")
if uncovered or STRAY: sys.exit(1)
print("\n  PASS: every printed literal is reachable from data or declared exempt")
sys.exit(0)
