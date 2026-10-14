#!/usr/bin/env python3
"""Derive paper/highlights.txt from the manuscript's own highlights environment.

The shipped file had drifted: it carried an older, shorter wording than the manuscript
("About 25% of matched elicitation pairs disagree on the IG/HY classification" against
"In the evaluated systems, about 25% ... investment-grade/high-yield classification").
A hand-maintained copy of generated text is a drift waiting to happen, so it is generated.
"""
import re, sys
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
SRC = PB / "paper/manuscript_full.tex"
DST = PB / "paper/highlights.txt"

tex = SRC.read_text(encoding="utf-8")
m = re.search(r"\\begin\{highlights\}(.*?)\\end\{highlights\}", tex, re.S)
if not m:
    print("NOT CHECKABLE: no highlights environment in the manuscript"); sys.exit(2)


# Map the symbols to what they render as before stripping anything. Stripping first silently
# turned "Fleiss $\\kappa\\le0.49$" into "Fleiss 0.49" and "$\\sim$8\\%" into "8%".
SYM = {r"\\kappa": "\u03ba", r"\\le(?![a-zA-Z])": "\u2264 ", r"\\ge(?![a-zA-Z])": "\u2265 ", r"\\sim": "~",
       r"\\times": "\u00d7", r"\\approx": "\u2248", r"\\pm": "\u00b1",
       r"R\^2": "R\u00b2", r"\\%": "%"}


def plain(s: str) -> str:
    for pat, rep in SYM.items():
        s = re.sub(pat, rep, s)
    s = re.sub(r"\$([^$]*)\$", lambda x: re.sub(r"\\[A-Za-z]+|[{}]", "", x.group(1)), s)
    s = s.replace("--", "\u2013")
    s = re.sub(r"\\[A-Za-z]+\s*", "", s)
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


items = [plain(x) for x in re.split(r"\\item", m.group(1)) if x.strip()]
out = "Highlights\n\n" + "\n".join(items) + "\n"
if "--check" in sys.argv:
    cur = DST.read_text(encoding="utf-8") if DST.exists() else ""
    if cur != out:
        print("FAIL: paper/highlights.txt is not current with the manuscript"); sys.exit(1)
    print(f"PASS: highlights.txt matches the manuscript ({len(items)} items)"); sys.exit(0)
DST.write_text(out, encoding="utf-8")
print(f"   wrote {DST.relative_to(PB)} ({len(items)} items)")
