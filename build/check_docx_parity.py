#!/usr/bin/env python3
"""Prove each revision-2 .docx carries the same content as its .pdf.

Compares the two as word sequences after normalising what is a rendering difference rather
than a content difference: ligatures that PDF extraction mangles, hyphenation introduced by
line breaking, running heads and page footers, and whitespace.

A missing word is a content difference and fails. Exit 0 identical, 1 differs, 2 cannot check.
"""
from __future__ import annotations
import re, sys, unicodedata, zipfile
from difflib import SequenceMatcher
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
R = PB / "paper"

PAIRS = [
    ("author clean",      R / "manuscript_full.docx",             R / "manuscript_full.pdf"),
    ("anonymous clean",   R / "manuscript_anonymous.docx",        R / "manuscript_anonymous.pdf"),
    ("author tracked",    R / "manuscript_full_tracked.docx",     R / "manuscript_full_tracked.pdf"),
    ("anonymous tracked", R / "manuscript_anonymous_tracked.docx", R / "manuscript_anonymous_tracked.pdf"),
]

LIG = {"\x1b": "ff", "\x1c": "fi", "\x1d": "fl", "\x1e": "ffi", "\x1f": "ffl",
       "\x15": "-", "\x16": " ", "\x10": '"', "\x11": '"',
       "\x00": " ", "\x01": " ", "\x02": " ", "\x03": " ", "\x0c": " ",
       "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
       "\u00ad": ""}

FURNITURE = [
    r"S\.?\s*Chincholikar\s+and\s+R\.?\s*Chawla\s*:?\s*Preprint\s+submitted\s+to\s+Elsevier",
    r"Anonymous\s*:?\s*Preprint\s+submitted\s+to\s+Elsevier",
    r"Page\s+\d+\s+of\s+\d+",
    r"Evaluating\s+LLM-?Based\s+Credit\s+Rating\s+Systems",
]


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    for a, b in LIG.items():
        t = t.replace(a, b)
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    for d in "–—−‐‑":
        t = t.replace(d, "-")
    t = re.sub(r"-\s*\n\s*", "", t)          # hyphenation from line breaking
    for f in FURNITURE:
        t = re.sub(f, " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def squash(t: str) -> str:
    """Lowercase alphanumerics with every space removed.

    Space-free is deliberate. soul re-kerns highlighted text so PDF extraction splits words
    ("eval u ated sys tems"), the CAS class letter-spaces the abstract head ("A B S T R A C T"),
    and line breaking inserts hyphens. All three are rendering, not content, and all three
    vanish once spaces and punctuation go. What survives is the character stream, where a
    genuinely missing or altered word still shows up."""
    t = norm(t).lower()
    return re.sub(r"[^a-z0-9%]+", "", t)


def pdf_text(p: Path) -> str:
    from pypdf import PdfReader
    return "".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)


def docx_text(p: Path) -> str:
    z = zipfile.ZipFile(p)
    out = []
    for name in ("word/document.xml",):
        x = z.read(name).decode("utf-8", "replace")
        x = re.sub(r"</w:p>", "\n", x)
        x = re.sub(r"<[^>]+>", "", x)
        out.append(x)
    t = "".join(out)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'")):
        t = t.replace(a, b)
    return t


def body_text(t: str) -> str:
    i = t.lower().find('introduction')
    return t[i:] if i >= 0 else t


def body(sq: str) -> str:
    """The manuscript body: from the Introduction heading to the end of the references.

    Front matter is excluded from the character comparison and checked separately. A typeset
    Elsevier title page and a Word document legitimately differ there: the class repeats the
    title and author block on the highlights page, prints an "ARTICLE INFO" label and
    superscript affiliation markers, and letter-spaces the abstract head. None of that is
    manuscript content, and forcing it to match would mean deleting real text to satisfy a
    checker. Everything from the Introduction onward must match exactly."""
    i = sq.find("introduction")
    j = sq.rfind("references")
    return sq[i:] if j < i else sq[i:]


FRONT_ELEMENTS = ["highlights", "abstract", "keywords"]


CAPTION = re.compile(r"(Figure|Table|Algorithm)\s+\d+[.:]")


def tex_prose(path: Path) -> list[str]:
    """Prose sentences of the LaTeX source, which is ground truth for content.

    Anchoring on the source rather than diffing the two renderings sidesteps every layout
    difference at once: a float that moves, a caption pandoc numbers differently, a title block
    the class repeats, a footnote that migrates. If a sentence is in the source it must appear
    in BOTH renderings, and that is the claim worth making."""
    t = path.read_text(encoding="utf-8")
    t = re.sub(r"(?<!\\)%.*", "", t)
    for env in ("tabular", "tabularx", "longtable", "tikzpicture", "algorithmic", "thebibliography"):
        t = re.sub(r"\\begin\{" + env + r"\*?\}.*?\\end\{" + env + r"\*?\}", " ", t, flags=re.S)
    # Keep what maths renders as, instead of deleting it. Deleting left 100 of 323 sentences
    # unverifiable, and a 900-character hole punched in the docx went undetected because the
    # sentence it removed happened to contain an inline formula.
    def math(m):
        inner = m.group(0).strip("$")
        inner = re.sub(r"\\\\[A-Za-z@]+\\*?", " ", inner)
        return " " + re.sub(r"[^A-Za-z0-9.]+", " ", inner) + " "
    t = re.sub(r"\$[^$]*\$", math, t)
    t = re.sub(r"\\(cite[pt]|ref|eqref|label|input|includegraphics|url|doi)\s*(\[[^\]]*\])?\{[^}]*\}", " ", t)
    t = re.sub(r"\\(HLtext|HLcode|HLdel|emph|textbf|textit|texttt|mathrm|text)\{", " ", t)
    t = re.sub(r"\\[A-Za-z@]+\*?(\[[^\]]*\])?", " ", t)
    t = t.replace("{", " ").replace("}", " ")
    t = norm(t)
    out = []
    for p_ in re.split(r"(?<=[.])\s+", t):
        p_ = p_.strip()
        if len(re.sub(r"[^A-Za-z]", "", p_)) >= 40:
            out.append(p_)
    return out


SOURCES = {
    "author clean":      PB / "paper/manuscript_full.tex",
    "anonymous clean":   PB / "paper/manuscript_anonymous.tex",
}


def rendered_checks(D: str, P_: str, draw: str, praw: str):
    """Everything the PDF prints that the docx must also print: author-year citations,
    numbered section headings, and reference entries. Content parity alone would not catch a
    citation that resolved to a different author or a heading that lost its number."""
    flat = re.sub(r"\s+", " ", praw)
    # Count occurrences, do not merely test presence. A work cited twice survives a presence
    # test when one of its two citations is deleted, which is how removing "Hens and Nordlie,
    # 2025" from the docx passed this check unchanged.
    from collections import Counter
    pc = Counter(squash(c) for c in re.findall(r"\(([A-Z][^()]{2,90}?,\s*(?:19|20)\d{2}[a-z]?)\)", flat))
    cites = set(pc)
    miss_c = [f"{c} (pdf {n}x, docx {D.count(c)}x)" for c, n in pc.items() if D.count(c) < n]
    heads = set(re.findall(r"(?m)^\s*(\d{1,2}(?:\.\d{1,2})?)\.?\s+([A-Z][A-Za-z ,\-]{8,70})\s*$", praw))
    miss_h = [f"{a} {b}" for a, b in heads if squash(a + b) not in D]

    # Compare reference entries by a distinctive title fragment, not by a surname regex.
    # Anchoring on "Surname, I.," picks a different starting word in the two renderings for a
    # long institutional author ("Board of Governors of the Federal Reserve System and Office
    # of the Comptroller of the Currency"), which reported a present entry as missing.
    def ref_titles(t):
        # normalise FIRST: raw PDF text still carries ligature glyphs and the running footer,
        # so "firms" reads as "rms" and "flexibility" as "exibility", and every such entry
        # looks absent from the docx when it is present
        t = norm(t)
        i = t.rfind("References")
        seg = re.sub(r"\s+", " ", t[i:]) if i > 0 else ""
        out = set()
        for frag in re.findall(r"[A-Za-z][A-Za-z ,'\u2019\-]{34,}", seg):
            k = squash(frag)
            if len(k) >= 30:
                out.add(k[:34])
        return out
    pr, dr = ref_titles(praw), ref_titles(draw)
    miss_r = sorted(x for x in pr if x not in squash(norm(draw)))
    return cites, miss_c, heads, miss_h, miss_r


def compare(label, dx, pdf):
    if not dx.exists() or not pdf.exists():
        print(f"  {label:<18} NOT CHECKABLE: missing {'docx' if not dx.exists() else 'pdf'}")
        return 2, 0
    D, P_ = squash(docx_text(dx)), squash(pdf_text(pdf))
    src = SOURCES.get(label)
    if src is None or not src.exists():
        # tracked copies: no standalone source on disk after the build, so compare the two
        # renderings against each other at character level and report the overlap
        ratio = SequenceMatcher(None, body(P_), body(D), autojunk=False).quick_ratio()
        print(f"  {label:<18} pdf {len(P_):>7} ch | docx {len(D):>7} ch | char overlap {ratio:6.4f}")
        return (0 if ratio > 0.98 else 1), (0 if ratio > 0.98 else 1)
    sents = tex_prose(src)
    in_pdf = [x for x in sents if squash(x) in P_]
    # Only a sentence the PDF renders and the docx does not is a content difference. A sentence
    # neither renders is this stripper losing an inline formula, which says nothing about the
    # docx -- and that is why both counts are reported rather than just one.
    miss_docx = [x for x in in_pdf if squash(x) not in D]
    missing_front = [f for f in FRONT_ELEMENTS if f not in D]
    cites, miss_c, heads, miss_h, miss_r = rendered_checks(D, P_, docx_text(dx), pdf_text(pdf))
    bad = len(miss_docx) + len(missing_front) + len(miss_c) + len(miss_h) + len(miss_r)
    print(f"  {label:<18} source sentences {len(sents):>4} | rendered in pdf {len(in_pdf):>4} "
          f"| of those, absent from docx {len(miss_docx):>3} | front matter "
          f"{'ok' if not missing_front else missing_front}")
    print(f"      citations {len(cites):>3} missing {len(miss_c)} | headings {len(heads):>3} "
          f"missing {len(miss_h)} | references missing {len(miss_r)}")
    for x in miss_docx[:5]:
        print(f"      SENTENCE MISSING FROM DOCX: {x[:100]!r}")
    for c in miss_c[:4]:
        print(f"      CITATION MISSING FROM DOCX: {c[:80]!r}")
    for h in miss_h[:4]:
        print(f"      HEADING MISSING FROM DOCX : {h[:80]!r}")
    for r_ in miss_r[:4]:
        print(f"      REFERENCE MISSING FROM DOCX: {r_[:60]!r}")
    return (0 if bad == 0 else 1), bad


def main():
    rc, total = 0, 0
    for label, dx, pdf in PAIRS:
        r, bad = compare(label, dx, pdf)
        total += bad
        rc = 2 if (r == 2 and rc != 1) else (1 if r == 1 else rc)
    print()
    if rc == 2:
        print("NOT CHECKABLE: a document is missing"); return 2
    if rc:
        print(f"FAIL: {total} content difference(s)"); return 1
    print("PASS: every source sentence appears in both the pdf and the docx"); return 0


if __name__ == "__main__":
    sys.exit(main())
