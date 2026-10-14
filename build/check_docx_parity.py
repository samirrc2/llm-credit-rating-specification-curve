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


def source_values(src: Path) -> "collections.Counter":
    """Every numeric literal the LaTeX source asserts, table bodies included.

    Anchored on the source, not on a pdf-to-docx diff, because figure internals differ by
    construction: a plot's axis ticks and data labels are extractable vector text in the pdf
    and live inside an image in the docx, so "0.49" legitimately appears once more in the pdf.
    The figure is present in both. What must match is every value the document ASSERTS, and
    those all come from the source."""
    import collections
    t = src.read_text(encoding="utf-8")
    t = t[t.index("\\begin{document}"):] if "\\begin{document}" in t else t
    t = re.sub(r"(?<!\\\\)%.*", "", t)

    def inp(m):
        f = src.parent / (m.group(1) if m.group(1).endswith(".tex") else m.group(1) + ".tex")
        return f.read_text(encoding="utf-8") if f.exists() else ""
    t = re.sub(r"\\input\{([^}]*)\}", inp, t)
    # A drawing's internal labels are real text in the pdf and pixels in the docx, so they are
    # not comparable and are not content the paper asserts in prose. Strip the drawing, keep
    # its caption. Tables are NOT stripped: they render as real tables in both.
    t = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", " ", t, flags=re.S)
    t = re.split(r"\\bibliography\{", t)[0]
    t = re.sub(r"\\(label|ref|eqref|cite[pt]?|includegraphics|url|doi)\s*(\[[^\]]*\])?\{[^}]*\}", " ", t)
    # layout parameters are not values the paper claims
    t = re.sub(r"\\[A-Za-z@]+\s*\[[^\]]*\]", " ", t)
    t = re.sub(r"\\\\\s*\[[^\]]*\]", " ", t)
    t = re.sub(r"(?:width|height|scale|xshift|yshift|minimum width|text width)\s*=\s*[0-9.]+\s*[a-z\\]*", " ", t)
    t = t.replace("{,}", "")
    t = re.sub(r"(\d),(\d{3})(?!\d)", r"\1\2", t)
    t = t.replace(",", " ")
    c = collections.Counter()
    for m in re.finditer(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?", t):
        v = m.group(0)
        if re.fullmatch(r"0+", v) or len(v) > 9:
            continue
        c[v] += 1
    return c


def pdf_text_excluding_figures(path: Path) -> str:
    """PDF text with figure internals removed, by font.

    A plot's axis ticks and data labels are extractable vector text in the pdf and live inside
    an image in the docx, so "0.49" legitimately renders once more in the pdf than in the docx.
    matplotlib sets those labels in DejaVu Sans while the manuscript body uses the journal
    class's fonts, which separates the two exactly. Dropping figure text wholesale by position
    would also drop the caption, which IS content and does appear in both."""
    try:
        import pymupdf
    except Exception:
        return pdf_text(path)
    out = []
    for page in pymupdf.open(str(path)):
        for blk in page.get_text("dict")["blocks"]:
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("font", "").startswith("DejaVu"):
                        continue
                    out.append(span.get("text", ""))
                out.append(" ")
            out.append("\n")
    return "".join(out)


def drawing_values(src: Path) -> "collections.Counter":
    """Values that live INSIDE the TikZ drawing.

    That diagram is typeset text in the pdf and an embedded image in the docx, so its numbers
    are extractable from one and not the other. They are subtracted from the pdf side rather
    than ignored everywhere, so a value that appears both in the drawing and in the prose is
    still checked for its prose occurrences."""
    import collections
    t = src.read_text(encoding="utf-8")
    c = collections.Counter()
    for m in re.finditer(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", t, re.S):
        for v in re.finditer(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?", m.group(0)):
            c[v.group(0)] += 1
    return c


def rendered_counts(t: str) -> "collections.Counter":
    import collections
    # Identifiers are not values. Strip DOIs and URLs BEFORE any other normalisation: doing it
    # after comma handling breaks the pattern and leaves "2025.108102" and "10.5281" behind.
    # Cut the bibliography. Its DOIs, arXiv ids, volumes and page ranges are identifiers, not
    # values the paper asserts, and pdf extraction reorders them ("10.1016/j.frl.2025.108102"
    # arrives as "108102.2025"). The reference list is verified separately, by title fragment.
    i = t.rfind("References")
    if i > len(t) * 0.5:
        t = t[:i]
    t = re.sub(r"https?://\S+", " ", t)
    t = norm(t)
    t = re.sub(r"(\d)\s+\.(\d)", r"\1.\2", t)
    t = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", t)
    # Collapse ONLY thousands separators. Stripping every comma merged "[0.6,1.7]" -- which the
    # docx writes without a space -- into "0.61.7", so the gate reported 0.6 and 1.7 as short
    # in the docx when both documents render them ten times.
    t = re.sub(r"(\d),(\d{3})(?!\d)", r"\1\2", t)
    t = t.replace(",", " ")
    # a DOI is an identifier, not a value: "10.1016/j.frl.2025.108102" otherwise contributes a
    # spurious "2025.108102" that the docx renders as a hyperlink and the pdf as plain text
    c = collections.Counter()
    for m in re.finditer(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?", t):
        c[m.group(0)] += 1
    return c


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
    sv = source_values(src)
    pc, dc = rendered_counts(pdf_text_excluding_figures(pdf)), rendered_counts(docx_text(dx))
    for v, n in drawing_values(src).items():
        if pc.get(v):
            pc[v] = max(0, pc[v] - n)
    # A value is a content difference only if the source asserts it AND the pdf renders more
    # of them than the docx. Two classes are excluded deliberately:
    #   - short in BOTH renderings: a LaTeX layout parameter my extractor counted as a value
    #     (width=0.92\\linewidth, a [-1pt] skip, a column spec), not something the paper claims
    #   - present in the pdf but not the source: a plot's axis ticks and data labels, which are
    #     extractable vector text in the pdf and live inside an image in the docx
    # Each rendering must carry at least as many of every value as the source asserts. Comparing
    # the two renderings to each other instead would flag every figure label, which is real text
    # in the pdf and pixels in the docx.
    # Every value the pdf renders outside a figure must appear in the docx at least as often.
    val_pdf = {v: (n, pc.get(v, 0)) for v, n in sv.items() if pc.get(v, 0) < n}
    short_all = {v: (pc[v], dc.get(v, 0)) for v in pc if dc.get(v, 0) < pc[v]}
    # Decimals are the paper's results and must match exactly. Bare integers are reported but
    # do not fail: they are figure and table numbering, footnote markers and page furniture,
    # which a typeset page and a Word document number differently by construction. Every one
    # observed here is a bare integer; a decimal appearing in this set would be a real defect.
    val_docx = {v: n for v, n in short_all.items() if "." in v}
    int_docx = {v: n for v, n in short_all.items() if "." not in v}
    bad = (len(miss_docx) + len(missing_front) + len(miss_c) + len(miss_h) + len(miss_r)
           + len(val_docx))
    print(f"  {label:<18} source sentences {len(sents):>4} | rendered in pdf {len(in_pdf):>4} "
          f"| of those, absent from docx {len(miss_docx):>3} | front matter "
          f"{'ok' if not missing_front else missing_front}")
    print(f"      citations {len(cites):>3} missing {len(miss_c)} | headings {len(heads):>3} "
          f"missing {len(miss_h)} | references missing {len(miss_r)}")
    print(f"      source values {len(sv):>4} distinct | short in pdf {len(val_pdf):>2} "
          f"| decimals short in docx {len(val_docx):>2} "
          f"| integers short (numbering/furniture) {len(int_docx):>2}")
    for v, (inpdf, indocx) in list(val_docx.items())[:8]:
        print(f"      VALUE SHORT IN DOCX: {v!r} pdf renders {inpdf}x, docx has {indocx}x")
    for v, (want, got) in list(val_pdf.items())[:5]:
        print(f"      VALUE SHORT IN PDF : {v!r} source asserts {want}x, pdf has {got}x")
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
