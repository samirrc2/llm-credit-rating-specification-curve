#!/usr/bin/env python3
"""Mark revision-2 additions in the manuscript, in place, without restructuring it.

Why not latexdiff: three configurations were tried against this document and each failed
structurally. Markup inside \\cmidrule gave "Paragraph ended before \\@@@cmidrule was complete"
and a pdflatex that span at 100% CPU until killed; adding those to --append-safecmd moved the
failure to "Misplaced \\noalign" between \\\\ and \\midrule, the usual booktabs collision; and
treating tabulars as PICTUREENV compiled cleanly but SILENTLY DROPPED CONTENT -- table captions
fell from 30 to 11, three section headings vanished, and 156 sentences of the clean manuscript
were missing from the output. A marked copy that quietly loses two pages is worse than none.

This script inverts the approach. The NEW manuscript is the base and is never restructured:
nothing is deleted, moved, or re-emitted. Additions are located by diffing against the previous
version and are wrapped in place. The output therefore contains the final manuscript by
construction, and check_marked.py verifies that against the clean PDF.

Marking rules:
  * body prose      -- added word runs wrapped; plain runs highlighted yellow, runs containing
                       math or commands coloured (soul cannot swallow those)
  * floats          -- the tabular body is NEVER touched, because that is what broke latexdiff.
                       A float that is new or whose body changed gets a coloured tag in its
                       caption instead, so the reviewer is told the table changed and where.
  * preamble, labels, comments -- never marked.

Usage: python3 mark_changes.py <old.tex> <new.tex> <out.tex>
"""
import re
import sys
from difflib import SequenceMatcher

PREAMBLE = "\n".join([
    r"\usepackage{soul}",
    r"\usepackage{xcolor}",
    r"\definecolor{HLyellow}{rgb}{1,0.94,0.35}",
    r"\definecolor{HLink}{rgb}{0.75,0.18,0.04}",
    r"\sethlcolor{HLyellow}",
    r"\newcommand{\HLtext}[1]{\texthl{#1}}",
    r"\newcommand{\HLcode}[1]{\textcolor{HLink}{#1}}",
    r"\newcommand{\HLtag}[1]{{\color{HLink}\bfseries [#1]~}}",
    # The legend is an annotation, not manuscript text. unmark() in check_marked.py strips
    # \HLlegend whole, so adding it keeps the round-trip exact.
    r"\newcommand{\HLlegend}{%",
    r"\par\noindent\fbox{\parbox{0.95\linewidth}{\footnotesize\textbf{Marked copy, revision 2.}"
    r" Additions since revision 1 are shown as \HLtext{highlighted text}, or as"
    r" \HLcode{coloured text} where the passage contains mathematics or a cross-reference."
    r" Deletions are not shown. Table and algorithm bodies are reproduced in final form without"
    r" internal marks; a float that is new or revised is labelled in its caption, e.g."
    r" \HLtag{New in revision 2}. Page and float numbering match the clean manuscript.}}\par\vspace{6pt}}",
    "",
])

SOUL_UNSAFE = ("$", "\\", "&", "{", "}", "~", "^", "_", "#")
# environments whose internals must not be touched: this is what broke latexdiff
NO_TOUCH_ENV = ("tabular", "tabularx", "longtable", "align", "equation", "eqnarray",
                "verbatim", "lstlisting", "minipage", "thebibliography")


def tokenize(s):
    """Split into tokens where every LaTeX command-with-arguments and every math span is ONE
    atomic token. A run of added tokens can then never start inside a brace group and end
    outside it, which is how in-place markup stays balanced."""
    toks, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "%":                                   # comment to end of line
            j = s.find("\n", i)
            j = n if j < 0 else j + 1
            toks.append((s[i:j], False)); i = j
        elif c == "$":                                 # math span
            j = i + 2 if s.startswith("$$", i) else i + 1
            close = "$$" if s.startswith("$$", i) else "$"
            k = s.find(close, j)
            k = n if k < 0 else k + len(close)
            toks.append((s[i:k], False)); i = k
        elif c == "\\" and i + 1 < n and s[i + 1].isalpha():
            m = re.match(r"\\[A-Za-z@]+\*?", s[i:])
            j = i + m.end()
            while j < n and s[j] in "[{":              # consume options and arguments
                close = "]" if s[j] == "[" else "}"
                depth, k = 0, j
                while k < n:
                    if s[k] in "[{" and (k == 0 or s[k - 1] != "\\"):
                        depth += 1
                    elif s[k] in "]}" and s[k - 1] != "\\":
                        depth -= 1
                        if depth == 0:
                            k += 1; break
                    k += 1
                j = k
            toks.append((s[i:j], False)); i = j
        elif c == "\\":                                # \\ , \& , \% ...
            toks.append((s[i:i + 2], False)); i += 2
        elif c.isspace():
            m = re.match(r"\s+", s[i:])
            toks.append((s[i:i + m.end()], None)); i += m.end()
        else:
            m = re.match(r"[^\s$%\\]+", s[i:])
            toks.append((s[i:i + m.end()], True)); i += m.end()
    return toks


# A marked run may not span any of these: \textcolor and \texthl cannot cross a paragraph
# break, a list item, a sectioning command or an environment boundary.
RUN_BREAK = re.compile(r"\\\\(?:par|item|section|subsection|subsubsection|paragraph|caption|"
                       r"label|begin|end|input|include|bibliography|newpage|clearpage|"
                       r"footnote|footnotetext|maketitle|hline|midrule|toprule|bottomrule|"
                       r"cmidrule|multicolumn|multirow|\\\\)\b|\\\\\\\\")
# Only a CLEAN heading is marked: command, one brace group, no \label, no nested braces.
# (This pattern previously had a doubled backslash, so it matched nothing and every heading
# fell through to the generic wrapper -- which produced \HLcode{\subsection{..}\label{..}}
# and "Missing }" / "Too many }'s".)
HEADING = re.compile(r"^\\(paragraph|subsection|subsubsection|section)(\*?)\{([^{}]*)\}$")
STRUCTURAL = re.compile(r"\\(?:label|input|begin|end)|\\(?:sub)*section|\\paragraph")

UNMARKED = []          # runs that could not be marked safely; reported, never silent


def balanced(t):
    """True if braces in t are balanced (escaped braces ignored)."""
    depth = 0
    for i, c in enumerate(t):
        if i and t[i - 1] == "\\":
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def wrap_one(core):
    """Wrap a single safe chunk: yellow highlight for plain prose, colour otherwise."""
    if not any(u in core for u in SOUL_UNSAFE) and len(core) <= 600:
        return r"\HLtext{" + core + "}"
    return r"\HLcode{" + core + "}"


def mark_chunk(txt):
    """Mark one chunk that contains no run-breaking command. Falls back to plain + a report."""
    if not txt.strip():
        return txt, 0
    lead = txt[:len(txt) - len(txt.lstrip())]
    trail = txt[len(txt.rstrip()):]
    core = txt.strip()
    if not balanced(core):
        UNMARKED.append(core[:90])
        return txt, 0
    return lead + wrap_one(core) + trail, 1


def wrap(run):
    """Mark one maximal run of added tokens, splitting at everything markup cannot cross."""
    out, n = [], 0
    for tok, _ in run:
        t = tok.strip()
        m = HEADING.match(t)
        if not m and STRUCTURAL.search(tok):
            out.append(tok)        # never mark a structural token
            continue
        if m:
            # a wholly new heading: mark its TEXT, not the command, so the heading still works
            # Colour, not \texthl: soul produces NOTHING inside a sectioning command's
            # moving argument, and silently -- the two new \paragraph headings vanished from
            # the marked PDF while pdflatex reported no error.
            cmd, star, arg = m.group(1), m.group(2), m.group(3)
            out.append("\\" + cmd + star + "{" + r"\HLcode{" + arg.strip() + "}" + "}")
            n += 1
            continue
        if RUN_BREAK.search(tok):
            out.append(tok)                      # emit structural tokens unmarked
            continue
        out.append(("\x00", tok))                # mark-eligible
    # coalesce adjacent eligible tokens, splitting at blank lines
    res, buf = [], []
    def flush():
        nonlocal n
        if not buf:
            return
        txt = "".join(buf); buf.clear()
        for piece in re.split(r"(\n[ \t]*\n)", txt):
            if re.fullmatch(r"\n[ \t]*\n", piece or ""):
                res.append(piece)
            elif piece:
                marked, k = mark_chunk(piece)
                res.append(marked); n += k
    for item in out:
        if isinstance(item, tuple):
            buf.append(item[1])
        else:
            flush(); res.append(item)
    flush()
    return "".join(res)


def body_split(s):
    """(preamble, body) at \\begin{document}."""
    k = s.index(r"\begin{document}") + len(r"\begin{document}")
    return s[:k], s[k:]


def protected_spans(body):
    """Character spans that must not be marked: no-touch environments."""
    spans = []
    for env in NO_TOUCH_ENV:
        for m in re.finditer(r"\\begin\{" + env + r"\*?\}", body):
            e = re.search(r"\\end\{" + env + r"\*?\}", body[m.start():])
            if e:
                spans.append((m.start(), m.start() + e.end()))
    spans.sort()
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def mark_prose(old_body, new_body):
    prot = protected_spans(new_body)
    pieces, marked, pos = [], 0, 0
    for a, b in prot + [(len(new_body), len(new_body))]:
        seg = new_body[pos:a]
        if seg:
            o = tokenize(old_body); nt = tokenize(seg)
            ok = [t for t, _ in o]; nk = [t for t, _ in nt]
            sm = SequenceMatcher(None, ok, nk, autojunk=False)
            out, run = [], []
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag in ("insert", "replace"):
                    run.extend(nt[j1:j2])
                else:
                    if run:
                        out.append(wrap(run)); marked += 1; run = []
                    out.append("".join(nk[j1:j2]))
            if run:
                out.append(wrap(run)); marked += 1
            pieces.append("".join(out))
        if a < len(new_body):
            pieces.append(new_body[a:b])
        pos = b
    return "".join(pieces), marked


def tag_floats(old, new):
    """Tag each float whose body is new or changed, inside its caption. Tabulars untouched."""
    def floats(s):
        out = []
        for m in re.finditer(r"\\begin\{(table|figure)\*?\}", s):
            e = re.search(r"\\end\{" + m.group(1) + r"\*?\}", s[m.start():])
            if e:
                out.append((m.start(), m.start() + e.end()))
        return out
    def key(blk):
        lb = re.search(r"\\label\{([^}]*)\}", blk)
        return lb.group(1) if lb else None
    oldblocks = {key(old[a:b]): re.sub(r"\s+", " ", old[a:b]) for a, b in floats(old)}
    res, pos, n_new, n_chg = [], 0, 0, 0
    for a, b in floats(new):
        blk = new[a:b]; k = key(blk)
        norm = re.sub(r"\s+", " ", blk)
        if k not in oldblocks:
            tag, n_new = "New in revision 2", n_new + 1
        elif oldblocks[k] != norm:
            tag, n_chg = "Revised in revision 2", n_chg + 1
        else:
            tag = None
        if tag:
            cm = re.search(r"(\\caption\{)", blk)
            if cm:
                blk = blk[:cm.end()] + r"\HLtag{" + tag + "}" + blk[cm.end():]
        res.append(new[pos:a]); res.append(blk); pos = b
    res.append(new[pos:])
    return "".join(res), n_new, n_chg


def main():
    oldp, newp, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    old = open(oldp, encoding="utf-8").read()
    new = open(newp, encoding="utf-8").read()
    _, old_body = body_split(old)
    pre, new_body = body_split(new)

    body, n_runs = mark_prose(old_body, new_body)
    body, n_new, n_chg = tag_floats(old_body, body)
    assert n_runs > 0, "no additions marked -- is the baseline the same file?"
    out = (pre.replace(r"\begin{document}", PREAMBLE + r"\begin{document}", 1)
           + body)
    open(outp, "w", encoding="utf-8").write(out)
    print(f"   {n_runs} added prose runs marked; "
          f"{n_new} float(s) tagged new, {n_chg} tagged revised; tabular bodies untouched")
    if UNMARKED:
        print(f"   {len(UNMARKED)} run(s) left UNMARKED (unbalanced braces):")
        for u in UNMARKED[:8]:
            print(f"     - {u}")


if __name__ == "__main__":
    main()
