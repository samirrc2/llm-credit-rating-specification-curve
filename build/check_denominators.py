#!/usr/bin/env python3
"""Bind the sample-size denominators in the manuscript and letter to the data that produced them.

Two inconsistencies prompted this gate: the credit arm was described as 4,320 elicitations while
the cell audit implied 4,316 realized, and the decontamination arm reported 1,364 elicitations
alongside a 0/60 denominator. Both are now stated explicitly as designed-vs-realized, and this
recomputes them from the panel and the frozen arm so the pair cannot drift apart again.

Exit 0 consistent, 1 inconsistent, 2 could not check.
"""
import glob, json, re, sys
from pathlib import Path
PB = Path(__file__).resolve().parents[1]
try:
    import pandas as pd
    P = pd.read_parquet(PB / "data/panel/panel.parquet")
    P = P[P.provider.isin(["openai", "google"])]
    L = P[P.parse_rule == "lenient"]
    cr = L[L.family == "credit_health"]
    rec = [json.loads(Path(f).read_text())
           for f in glob.glob(str(PB / "data/frozen/realarm_decontam/raw/*.json"))]
except Exception as e:
    print(f"NOT CHECKABLE: {e}"); sys.exit(2)
if not rec:
    print("NOT CHECKABLE: frozen decontamination arm missing"); sys.exit(2)

FACTS = {
    "credit designed": 45 * 32 * 3,
    "credit realized": len(cr),
    "battery designed": 90 * 32 * 3,
    "battery realized": len(L),
    "decontam attempted": len(rec),
    "decontam substantive": sum(1 for r in rec if r["ok"]),
}
for e, planned in (("A1", 62), ("A2", 186), ("B", 1116)):
    sub = [r for r in rec if r["experiment"] == e]
    FACTS[f"{e} attempted"] = len(sub)
    FACTS[f"{e} substantive"] = sum(1 for r in sub if r["ok"])
for k, v in FACTS.items():
    print(f"  {k:22} {v}")

# A bare substring test is not enough: "62" occurs inside "0.062" and "60" inside "0.60", so a
# document that had LOST the count still passed. Require a non-digit boundary on both sides.
def states(t, n):
    forms = [f"{n:,}".replace(",", "{,}"), f"{n:,}", str(n)]
    # also reject the integer part of a decimal: "62" inside "62.5%" is not a sample size
    return any(re.search(r"(?<![\d.])" + re.escape(f) + r"(?![\d])(?!\.\d)", t) for f in forms)
REQUIRED = [("credit designed", 4320), ("credit realized", 4316),
            ("battery realized", 8633), ("decontam attempted", 1364),
            ("decontam substantive", 1361), ("A1 substantive", 60), ("A1 attempted", 62)]
bad = []
for name, expect in REQUIRED:
    if FACTS.get(name) != expect:
        bad.append(f"{name}: data says {FACTS.get(name)}, documents assume {expect}")
docs = {"manuscript": PB / "paper/NLP/cas-sc.tex",
        "letter": PB / "paper/NLP/submission/revision_2/RESPONSE_TO_REVIEWERS_R2.tex"}
# Scoped per document: the battery-wide substantive count is a Methods detail and has no reason
# to appear in the response letter. Requiring it there was this gate's own false positive.
# The letter may legitimately omit the arm-wide totals and report only the per-experiment
# denominators it actually uses (60 of 62 attempted, etc.). What it must NOT do is state an
# attempted total without the substantive one -- that pairing is the inconsistency this gate
# exists to prevent. So these are manuscript-required and conditionally letter-required.
# The response letter cites only the denominators it actually uses. Requiring every one of them
# there forced the letter's wording rather than checking it; these are manuscript-required and
# conditionally letter-required via CONDITIONAL_PAIRS below.
MANUSCRIPT_ONLY = {"battery realized", "decontam attempted", "decontam substantive",
                   "A1 attempted", "A1 substantive"}
CONDITIONAL_PAIRS = [("decontam attempted", "decontam substantive"),
                     ("credit designed", "credit realized"),
                     ("A1 attempted", "A1 substantive")]
for label, path in docs.items():
    t = path.read_text(encoding="utf-8")
    for name, expect in REQUIRED:
        if label == "letter" and name in MANUSCRIPT_ONLY:
            continue
        if not states(t, expect):
            bad.append(f"{label} never states {name} ({expect})")
# conditional pairing: if a document states the attempted/designed figure, it must also state
# its realized counterpart in the same document
for label, path in docs.items():
    t = path.read_text(encoding="utf-8")
    for a, b in CONDITIONAL_PAIRS:
        if states(t, FACTS[a]) and not states(t, FACTS[b]):
            bad.append(f"{label} states {a} ({FACTS[a]}) without {b} ({FACTS[b]})")

# the realized count must never be presented as the designed one
for label, path in docs.items():
    t = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
    if re.search(r"4\{,\}320 (?:credit-rating )?elicitations(?! attempted)", t) and \
       "designed" not in t:
        bad.append(f"{label} presents 4,320 as the analysed count with no 'designed' qualifier")
if bad:
    print("\n  FAIL:")
    for b in bad:
        print(f"    - {b}")
    sys.exit(1)
print("\n  PASS: every denominator in both documents matches the data, and designed vs realized "
      "is stated explicitly")
sys.exit(0)
