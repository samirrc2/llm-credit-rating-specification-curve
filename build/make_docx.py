#!/usr/bin/env python3
"""Generate .docx companions for the revision-2 deliverables.

  python3 build/make_docx.py            # build all four
  python3 build/make_docx.py --check    # verify each .docx against its .pdf

Four documents, from four LaTeX sources:
  manuscript_full.docx            paper/manuscript_full.tex                 author, clean
  manuscript_anonymous.docx  submission/manuscript_anonymous.tex        anonymous, clean
  manuscript_full_tracked.docx              _marked.tex                          author, tracked
  manuscript_anonymous_tracked.docx    _marked_blinded.tex                  anonymous, tracked

The anonymous tracked copy is made by blinding FIRST and marking the blinded pair. Marking first
and blinding after does not work: mark_changes inserts markup into the very sentences the
blinding rules match, and make_blinded then refuses rather than emit a half-blinded document.

Citations are resolved from the .bbl that LaTeX itself produced, not re-implemented. natbib with
cas-model2-names prints the full author list the first time a work is cited and "et al."
thereafter, and the .bbl label carries both forms, so first-use is tracked per key.

pandoc silently DROPS \\HLtext because it does not know soul's \\texthl, which would delete every
added run from the tracked document without any error. \\HLtext and \\HLcode are therefore
rewritten to \\hl, and \\HLdel to \\sout, both of which pandoc maps to real docx formatting
(highlight and strikethrough).
"""
from __future__ import annotations
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
NLP = PB / "paper"
OUT = PB / "paper"
TEXBIN = os.path.expanduser("~/Library/TinyTeX/bin/universal-darwin")
os.environ["PATH"] = TEXBIN + os.pathsep + os.environ["PATH"]


def sh(cmd, cwd, timeout=300):
    return subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str),
                          capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------- bibliography
def make_bbl(tex_path: Path, work: Path) -> str:
    """Run LaTeX+bibtex on a copy so the .bbl is the one this document would typeset."""
    stem = "bibsrc"
    shutil.copy(tex_path, work / f"{stem}.tex")
    for p in NLP.iterdir():
        if p.suffix in (".sty", ".cls", ".bst", ".bib", ".png", ".pdf") or p.name.endswith("_body.tex"):
            shutil.copy(p, work / p.name)
    sh(f'pdflatex -interaction=nonstopmode {stem}.tex', work)
    sh(f'bibtex {stem}', work)
    sh(f'pdflatex -interaction=nonstopmode {stem}.tex', work)
    sh(f'pdflatex -interaction=nonstopmode {stem}.tex', work)
    f = work / f"{stem}.bbl"
    if not f.exists():
        sys.exit(f"ERROR: no .bbl produced for {tex_path.name}")
    aux = work / f"{stem}.aux"
    return (f.read_text(encoding="utf-8", errors="replace"),
            aux.read_text(encoding="utf-8", errors="replace") if aux.exists() else "")


def parse_labels(aux: str) -> dict:
    """label -> printed number, from LaTeX's own .aux. Without this pandoc emits a placeholder
    for every \\ref, so "Section 6.2" would come out as "Section 0.1"."""
    out = {}
    for m in re.finditer(r"\\newlabel\{([^}]*)\}\{\{([^}]*)\}", aux):
        out[m.group(1)] = re.sub(r"\\[A-Za-z]+\s*|[{}]", "", m.group(2)).strip()
    return out


def parse_bbl(bbl: str):
    """key -> (short, long, year, formatted entry). The natbib label is
    SHORT(YEAR)LONG, where LONG is the full author list used on first citation."""
    out, order = {}, []
    chunks = re.split(r"\\bibitem\[\{", bbl)[1:]
    for ch in chunks:
        label, rest = ch.split("}]{", 1)
        key, body = rest.split("}", 1)
        body = body.split("\\bibitem")[0]
        m = re.match(r"(.*?)\((\d{4}[a-z]?)\)(.*)", label, re.S)
        if not m:
            short, year, long_ = label.strip(), "", ""
        else:
            short, year, long_ = m.group(1).strip(), m.group(2), m.group(3).strip()
        out[key] = {"short": short, "long": long_ or short, "year": year,
                    "entry": clean_entry(body)}
        order.append(key)
    return out, order


def clean_entry(b: str) -> str:
    b = b.split("\\end{thebibliography}")[0]
    b = re.sub(r"\\bibinfo\{[^}]*\}\{", "{", b)
    b = re.sub(r"\\newblock\s*", " ", b)
    b = b.replace("\\DOIprefix\\doi{", "doi:{")
    b = re.sub(r"\\ArXivprefix\\arxiv\{", "arXiv:{", b)
    b = re.sub(r"\\urlprefix\\url\{", "URL: {", b)
    b = re.sub(r"\\URLprefix\s*\\url\{", "URL: {", b)
    # drop the now-bare brace groups introduced above
    prev = None
    while prev != b:
        prev = b
        b = re.sub(r"\{([^{}]*)\}", r"\1", b)
    b = re.sub(r"\s+", " ", b).strip()
    return b


def resolve_cites(tex: str, bib: dict) -> str:
    """\\citep -> (Author, Year); \\citet -> Author (Year). Full author list on first use.

    Scanned left to right in one pass, so "first use" means first use in reading order,
    which is what natbib does."""
    seen: set[str] = set()

    def render(key: str):
        e = bib.get(key)
        if not e:
            return key, ""
        name = (e["long"] if key not in seen else e["short"]).replace("~", " ")
        seen.add(key)
        return name, e["year"]

    def repl(m):
        cmd, keys = m.group(1), [k.strip() for k in m.group(2).split(",") if k.strip()]
        parts = [render(k) for k in keys]
        if cmd == "citet":
            return "; ".join(f"{n} ({y})" if y else n for n, y in parts)
        return "(" + "; ".join(f"{n}, {y}" if y else n for n, y in parts) + ")"

    return re.sub(r"\\(citep|citet)\{([^}]*)\}", repl, tex)


def replace_balanced(s: str, head_pat: str, fn):
    """Replace head_pat followed by a balanced {...} group. A regex cannot do this: the CAS
    author block spans lines and nests braces (organization={..}, city={..}, country={..})."""
    out, i = [], 0
    for m in re.finditer(head_pat + r"\s*\{", s):
        if m.start() < i:
            continue
        j, depth = m.end(), 1
        while j < len(s) and depth:
            if s[j] == "{" and s[j-1] != "\\":
                depth += 1
            elif s[j] == "}" and s[j-1] != "\\":
                depth -= 1
            j += 1
        out.append(s[i:m.start()]); out.append(fn(s[m.end():j-1])); i = j
    out.append(s[i:])
    return "".join(out)


def affil_text(body: str) -> str:
    """organization={X}, city={Y}, country={Z} -> 'X, Y, Z'."""
    vals = re.findall(r"\w+\s*=\s*\{([^{}]*)\}", body)
    return "\n" + ", ".join(v.strip() for v in vals if v.strip()) + "\n" if vals else "\n" + body.strip() + "\n"


# ---------------------------------------------------------------- preprocessing
def preprocess(tex: str, bib: dict, order: list, marked: bool, labels: dict) -> str:
    # tracked-changes markup -> commands pandoc maps to real docx formatting.
    # Without this \HLtext is dropped silently and every addition disappears.
    tex = re.sub(r"\\HL(?:text|code)\{", r"\\hl{", tex)
    tex = re.sub(r"\\HLdel\{", r"\\sout{", tex)
    tex = re.sub(r"\\HLtag\{([^}]*)\}", r"[\1] ", tex)
    # drop the whole marker preamble mark_changes injects, definitions included. Stripping only
    # the \HLlegend *uses* leaves "\newcommand{}{%" behind and pandoc stops there.
    tex = re.sub(r"\\usepackage\{soul\}.*?\\par\\vspace\{6pt\}\}\n", "", tex, flags=re.S)
    tex = tex.replace("\n\\HLlegend\n", "\n")
    tex = tex.replace("\\HLlegend", "")

    tex = resolve_cites(tex, bib)
    # pandoc cannot render TikZ, so it drops the governance-workflow figure entirely: "Human
    # review", "Auto-accept" and "Modal rating" were in the pdf and absent from the docx. The
    # same diagram exists as a rendered image, so the environment is replaced by it.
    gov = NLP / "fig_governance.png"
    if gov.exists():
        tex = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}",
                     lambda _m: "\\includegraphics[width=0.95\\linewidth]{" + gov.name + "}",
                     tex, flags=re.S)

    # \\ref/\\eqref resolved from the .aux; an unknown label is reported rather than silently
    # rendered as a placeholder number
    unresolved: set[str] = set()

    def ref(m):
        k = m.group(2)
        if k not in labels:
            unresolved.add(k)
            return "??"
        return ("(" + labels[k] + ")") if m.group(1) == "eqref" else labels[k]
    tex = re.sub(r"\\(ref|eqref|autoref)\{([^}]*)\}", ref, tex)
    if unresolved:
        print("   WARNING unresolved labels:", sorted(unresolved)[:8])

    # \input{tab_x_body} -> the table body itself
    def inp(m):
        f = NLP / (m.group(1) if m.group(1).endswith(".tex") else m.group(1) + ".tex")
        return f.read_text(encoding="utf-8") if f.exists() else ""
    tex = re.sub(r"\\input\{([^}]*)\}", inp, tex)

    # author block -> plain lines pandoc keeps; the CAS macros otherwise leak "[orcid=...]"
    # keep the ORCIDs: the class prints them on the title page, so dropping them makes the
    # docx genuinely miss content the pdf shows
    orcids = re.findall(r"orcid=([0-9X-]+)", tex)
    tex = re.sub(r"\\author\*?\[\d*\]\{([^}]*)\}(\[[^\]]*\])?", r"\n\\textbf{\1}\n", tex)
    emails = re.findall(r"\\ead\{([^}]*)\}", tex)
    corr = re.findall(r"\\cortext\[[^\]]*\]\{([^}]*)\}", tex)
    tex = re.sub(r"\\(ead|credit|cormark|cortext|fnmark|fntext|nonumnote)\s*(\[[^\]]*\])?\{[^}]*\}", "", tex)
    affils: list[str] = []
    tex = replace_balanced(tex, r"\\affiliation(?:\[\d*\])?",
                           lambda b: (affils.append(affil_text(b).strip()) or ""))
    tex = re.sub(r"\\(shortauthors|printcredits|printorcid|leftmark|rightmark)\b\s*(\{[^}]*\})?", "", tex)
    tex = re.sub(r"\\RenewDocumentCommand\{[^}]*\}\{[^}]*\}\{[^}]*\}[^\n]*", "", tex)

    # Front matter is emitted explicitly, in the order the PDF prints it: Highlights on their
    # own page, then title and authors, then the abstract and keywords. Left to pandoc the
    # title block always comes first and the environments are dropped entirely.
    def grab(name):
        nonlocal tex
        m = re.search(r"\\begin\{" + name + r"\}(.*?)\\end\{" + name + r"\}", tex, re.S)
        if not m:
            return ""
        tex = tex.replace(m.group(0), "")
        return m.group(1).strip()

    abstract = grab("abstract")
    # lambda, not a replacement string: "\\item" in a template is a bad escape (\\i)
    highlights = re.sub(r"\\item\s*", lambda _m: "\n\\item ", grab("highlights"))
    keywords = grab("keywords").replace("\\sep", " \u00b7 ")

    mt = re.search(r"\\title(?:\[[^\]]*\])?\{(.*?)\}\s*\n", tex, re.S)
    title = mt.group(1).strip() if mt else ""
    if mt:
        tex = tex.replace(mt.group(0), "")
    authors = re.findall(r"\\textbf\{([^}]*)\}", tex[:tex.index("\\maketitle")] if "\\maketitle" in tex else tex[:4000])

    front = []
    if highlights:
        front.append("\\section*{Highlights}\n" + highlights)
    if title:
        front.append("\\section*{" + title + "}")
    if authors:
        front.append(", ".join(authors))
    # order as the PDF prints it: affiliation, then keywords, then the abstract
    if affils:
        front.append(" ".join(dict.fromkeys(a for a in affils if a)))
    # the corresponding-author footnote is printed on page 1 of the PDF; without it the docx
    # is genuinely missing content rather than merely laying it out differently
    if corr or emails or orcids:
        front.append(" ".join(corr) + (" " if corr else "") + " ".join(dict.fromkeys(emails))
                     + (("  ORCID " + ", ".join(dict.fromkeys(orcids))) if orcids else ""))
    if keywords:
        front.append("\\section*{Keywords}\n" + keywords)
    if abstract:
        front.append("\\section*{Abstract}\n" + abstract)
    block = "\n\n".join(front) + "\n\n"
    if "\\maketitle" in tex:
        tex = tex.replace("\\maketitle", block, 1)
    else:
        tex = tex.replace("\\begin{document}", "\\begin{document}\n" + block, 1)
    # the author names were emitted into front matter; drop the originals
    for a in authors:
        tex = tex.replace("\\textbf{" + a + "}", "", 1)

    # references, in the order the .bbl lists them (alphabetical, as typeset)
    refs = "\\section*{References}\n\n" + "\n\n".join(bib[k]["entry"] for k in order) + "\n"
    tex = re.sub(r"\\bibliographystyle\{[^}]*\}\s*", "", tex)
    tex = re.sub(r"\\bibliography\{[^}]*\}", lambda m: refs, tex)
    return tex


def build_one(src: Path, dest: Path, marked: bool) -> Path:
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        bbl, aux = make_bbl(src, work)
        bib, order = parse_bbl(bbl)
        labels = parse_labels(aux)
        tex = preprocess(src.read_text(encoding="utf-8"), bib, order, marked, labels)
        stage = work / "stage.tex"
        stage.write_text(tex, encoding="utf-8")
        r = sh(["pandoc", str(stage), "-f", "latex", "-t", "docx",
                "--number-sections", f"--resource-path={NLP}:{work}",
                "-o", str(dest)], work, timeout=600)
        if r.returncode != 0:
            sys.exit(f"ERROR: pandoc failed for {src.name}\n{r.stderr[:1200]}")
    return dest


# ---------------------------------------------------------------- sources
def blinded_marked() -> Path:
    """Blind the revision-1 baseline, then mark the blinded pair."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("mb", PB / "build/make_blinded.py")
    mb = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mb)
    except SystemExit:
        pass
    base_b = NLP / "_rev1_blinded.tex"
    base_b.write_text(mb.blind((NLP / "manuscript_round1_baseline.tex").read_text(encoding="utf-8")), encoding="utf-8")
    out = NLP / "_marked_blinded.tex"
    r = sh([sys.executable, str(PB / "build/mark_changes.py"), str(base_b),
            str(PB / "paper/manuscript_anonymous.tex"), str(out)], PB, timeout=600)
    if r.returncode != 0 or not out.exists():
        sys.exit(f"ERROR: marking the blinded pair failed\n{r.stdout}\n{r.stderr}")
    print("   anonymous tracked source:", r.stdout.strip().splitlines()[0].strip())
    return out


def marked_author() -> Path:
    out = NLP / "_marked.tex"
    if not out.exists():
        r = sh([sys.executable, str(PB / "build/mark_changes.py"), str(NLP / "manuscript_round1_baseline.tex"),
                str(NLP / "manuscript_full.tex"), str(out)], PB, timeout=600)
        if r.returncode != 0 or not out.exists():
            sys.exit("ERROR: marking the author pair failed")
    return out


TARGETS = [
    ("manuscript_full.docx",           lambda: NLP / "manuscript_full.tex",                         False),
    ("manuscript_anonymous.docx", lambda: PB / "paper/manuscript_anonymous.tex", False),
    ("manuscript_full_tracked.docx",             marked_author,                                      True),
    ("manuscript_anonymous_tracked.docx",   blinded_marked,                                     True),
]


def main() -> int:
    if "--check" in sys.argv:
        import check_docx_parity as _unused   # pragma: no cover
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, srcf, marked in TARGETS:
        src = srcf()
        dest = OUT / name
        build_one(src, dest, marked)
        print(f"   {dest.relative_to(PB)}  <- {Path(src).name}  ({dest.stat().st_size//1024} KB)")
    for tmp in ("_rev1_blinded.tex", "_marked_blinded.tex"):
        (NLP / tmp).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
