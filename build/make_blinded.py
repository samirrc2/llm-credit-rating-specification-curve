#!/usr/bin/env python3
"""Derive the double-blind manuscript from the master, instead of hand-maintaining a copy.

submission/manuscript_anonymous.tex had drifted 389 lines behind manuscript_full.tex -- it carried none of
revision 2. A hand-maintained duplicate of a generated document is a drift waiting to happen, so
the blinding is now expressed as the seven transformations that actually distinguish the two
(recovered by diffing the revision-1 master against the revision-1 blinded copy, same era, so the
diff is pure blinding and no content).

Every rule must fire exactly the expected number of times, or the script fails rather than
silently producing a half-blinded manuscript -- which is the one failure mode that matters here.

  python3 build/make_blinded.py            # write submission/manuscript_anonymous.tex
  python3 build/make_blinded.py --check     # verify the committed blinded copy is current
"""
import re, sys
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
SRC = PB / "paper/manuscript_full.tex"
DST = PB / "paper/manuscript_anonymous.tex"

# (name, pattern, replacement, expected occurrences)
RULES = [
    ("short authors",
     r"\\shortauthors\{S\. Chincholikar and R\. Chawla\}",
     r"\\shortauthors{Anonymous}", 1),
    ("author block",
     r"\\author\[1\]\{Samir Chincholikar\}\[orcid=[^\]]*\]\s*\n"
     r"\\ead\{[^}]*\}\s*\n\\credit\{[^}]*\}\s*\n\s*\n"
     r"\\author\[1\]\{Robin Chawla\}\[orcid=[^\]]*\]\s*\n"
     r"\\cormark\[1\]\s*\n\\ead\{[^}]*\}\s*\n\\credit\{[^}]*\}\s*\n\s*\n"
     r"\\affiliation\[1\]\{organization=\{Independent researcher\},\s*\n"
     r"\s*city=\{New York\},\s*\n\s*country=\{USA\}\}\s*\n\s*\n"
     r"\\cortext\[1\]\{Corresponding author\}",
     "\\\\author[1]{Anonymous}\n\n\\\\affiliation[1]{organization={Author affiliations withheld "
     "for double-blind review}}", 1),
    ("credits list",
     r"\n\\printcredits", "", 1),
    ("zenodo capsule sentence",
     r"reproducibility capsule archived on Zenodo \\citep\{chincholikar2026capsule\}\s*\n"
     # punctuation-tolerant: a later copy-edit changed "; MIT license" to ", MIT license"
     # and this rule stopped matching, which (correctly) failed the build rather than emitting a
     # half-blinded manuscript.
     r"\(\\url\{[^}]*\}[;,] MIT license\), mirrored in the source repository at\s*\n\\url\{[^}]*\}\.",
     "reproducibility capsule (MIT license) provided as anonymized supplementary material with "
     "this submission;\nthe public repository and its citable DOI are withheld here for "
     "double-blind review and will be provided\non acceptance.", 1),
    ("reproducibility doc location",
     r"\(in the repository and the Zenodo deposit\), documents the",
     r"(provided with this submission), documents the", 1),
]
# \printorcid must be suppressed or the class prints an empty "orcid(s)" label
PREAMBLE_INS = (r"\RenewDocumentCommand{\printorcid}{}{} % double-blind: suppress empty orcid(s) label")


def blind(s):
    for name, pat, rep, n in RULES:
        found = len(re.findall(pat, s))
        if found != n:
            sys.exit(f"ERROR: blinding rule {name!r} matched {found} times, expected {n}. "
                     f"The master changed shape; update build/make_blinded.py rather than "
                     f"hand-editing the blinded copy.")
        s = re.sub(pat, rep, s)
    anchor = "\\begin{document}"
    if PREAMBLE_INS not in s:
        i = s.index("\\usepackage")
        s = s[:i] + PREAMBLE_INS + "\n" + s[i:]
    return s


def residual_identity(s):
    """Anything identifying that survived. This is the check that matters."""
    pats = {"author name": r"Chincholikar|Chawla", "email": r"samir\.|robin\.chawla|@gmail|@iitbhu",
            "orcid": r"orcid=0009", "github": r"github\.com/samirrc2",
            "zenodo doi": r"10\.5281/zenodo", "affiliation city": r"New York"}
    return {k: len(re.findall(v, s)) for k, v in pats.items() if re.search(v, s)}


def check_figures(s):
    """Every \\includegraphics target must exist next to the blinded source.

    A missing figure is NOT a LaTeX error by default -- pdftex.def falls back to a draft box and
    the build still reports 27 pages. One figure was deleted from submission/ as a "duplicate"
    of the copy in paper/, and the only symptom was a framed filename in the PDF.
    """
    missing = [f for f in re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]*)\}", s)
               if not (DST.parent / f).exists()]
    return missing


def main():
    src = SRC.read_text(encoding="utf-8")
    out = blind(src)
    leaks = residual_identity(out)
    if leaks:
        sys.exit(f"ERROR: identifying material survived blinding: {leaks}")
    if "--check" in sys.argv:
        if not DST.exists():
            print("blinded copy missing"); return 1
        cur = DST.read_text(encoding="utf-8")
        if cur == out:
            print(f"  PASS: manuscript_anonymous.tex is current ({len(out)} bytes)")
            return 0
        import difflib
        d = list(difflib.unified_diff(cur.splitlines(), out.splitlines(), lineterm="", n=0))
        print(f"  FAIL: blinded copy is stale -- {len(d)} diff lines vs the master")
        return 1
    miss = check_figures(out)
    if miss:
        sys.exit(f"ERROR: figures missing from {DST.parent.relative_to(PB)}: {miss}. "
                 f"pdflatex would substitute a draft box and still report success.")
    DST.write_text(out, encoding="utf-8")
    print(f"  wrote {DST.relative_to(PB)} ({len(out)} bytes)")
    print(f"  figures: all {len(re.findall(chr(92)+chr(92)+'includegraphics', out))} present")
    print(f"  identity check: no author name, email, ORCID, GitHub, DOI or city survives")
    return 0


if __name__ == "__main__":
    sys.exit(main())
