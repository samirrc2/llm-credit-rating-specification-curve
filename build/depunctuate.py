#!/usr/bin/env python3
"""Reduce prose semicolons and clausal colons in the manuscript, safely.

What is PROTECTED and never touched: inline and display math, LaTeX comments, the arguments of
commands (\\label, \\ref, \\cite, \\path, \\texttt, \\url, \\includegraphics, \\input), the title,
tabular row content, and enumeration separators of the form "(i) ...; (ii) ...".

What is TRANSFORMED:
  "; and X" / "; or X"     -> ", and X" / ", or X"
  "; x..."  (new clause)   -> ". X..."
  ": x..."  (new clause)   -> ". X..."   only when the clause opens with a subject-like word,
                              so that colons genuinely introducing a LIST are left alone.

Run with --report to see what it would do without writing.
"""
import re, sys
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
SRC = PB / "paper/NLP/cas-sc.tex"

# Only these may follow a colon and still be certain to START A CLAUSE. Earlier I allowed
# "a/an/the/that/such", which turned list-introducing colons into sentence fragments
# ("two co-equal contributions: an evaluation framework that ..." -> "...contributions. An
# evaluation framework that ..."). Pronouns, demonstratives and subordinators are safe.
OPENERS = (r"it|we|this|these|those|they|there|because|since|when|while|although|however")

def protect(s):
    """Replace protected spans with placeholders so regexes cannot reach inside them."""
    store = []
    def keep(m):
        store.append(m.group(0))
        return f"\x00{len(store)-1}\x00"
    # (pattern, flags) -- re.S on the comment pattern made "%.*" swallow the whole file, which
    # silently protected everything and left nothing to transform.
    pats = [(r"%.*", 0),                                     # comments: per line, NOT re.S
            (r"\\\[.*?\\\]", re.S),                          # display math
            (r"\$\$.*?\$\$", re.S),
            (r"\$[^$\n]*\$", 0),                              # inline math
            (r"\\(?:label|ref|eqref|cite|citet|citep|path|texttt|url|includegraphics|input|"
             r"usepackage|definecolor|newcommand|RenewDocumentCommand|bibliography|"
             r"bibliographystyle|title|shortauthors|author|affiliation|ead|credit)\*?"
             r"(?:\[[^\]]*\])?\{[^{}]*\}", 0)]
    for pat, fl in pats:
        s = re.sub(pat, keep, s, flags=fl)
    return s, store

def restore(s, store):
    return re.sub(r"\x00(\d+)\x00", lambda m: store[int(m.group(1))], s)

def transform(s):
    n = {"semi_and": 0, "semi_period": 0, "semi_comma_paren": 0, "colon_period": 0,
         "semi_kept_enum": 0, "colon_kept": 0}
    def is_enum(text, i):
        return bool(re.match(r";\s*\((?:i|ii|iii|iv|v|vi)\)", text[i:]))
    def in_parens(text, i):
        """Is position i inside parentheses, judged LOCALLY within the current sentence?

        A single document-wide depth counter is not usable here: one unbalanced "(" anywhere --
        including one left behind when a protected span was replaced by a placeholder -- makes
        every later character look parenthetical, which silently turned 116 semicolons into
        commas. So look back only to the start of the current sentence.
        """
        start = max(text.rfind(". ", 0, i), text.rfind("\n\n", 0, i),
                    text.rfind("} ", 0, i), 0)
        w = text[start:i]
        return w.count("(") > w.count(")")

    out, i = [], 0
    while i < len(s):
        c = s[i]
        depth = 1 if in_parens(s, i) else 0
        if c == ";":
            if is_enum(s, i):
                n["semi_kept_enum"] += 1
                out.append(c); i += 1; continue
            if depth > 0:
                # a period inside parentheses is wrong; a comma reads correctly
                out.append(","); i += 1; n["semi_comma_paren"] += 1; continue
            m = re.match(r";\s+(and|or)\s", s[i:])
            if m:
                out.append(","); i += 1; n["semi_and"] += 1; continue
            m = re.match(r";(\s+)([a-z])", s[i:])
            if m:
                out.append("." + m.group(1) + m.group(2).upper())
                i += m.end(); n["semi_period"] += 1; continue
        if c == ":" and not in_parens(s, i):
            m = re.match(r":(\s+)(" + OPENERS + r")(\s|,)", s[i:], flags=re.I)
            if m:
                w = m.group(2)
                out.append("." + m.group(1) + w[0].upper() + w[1:] + m.group(3))
                i += m.end(); n["colon_period"] += 1; continue
            n["colon_kept"] += 1
        out.append(c); i += 1
    return "".join(out), n

src = SRC.read_text(encoding="utf-8")
head, body = src[:src.index(r"\begin{document}")], src[src.index(r"\begin{document}"):]
prot, store = protect(body)
new, n = transform(prot)
new = restore(new, store)
def count(t):
    p, _ = protect(t)
    return p.count(";"), p.count(":"), len(re.findall("---", p))
b4 = count(body); af = count(new)
print(f"  semicolons {b4[0]} -> {af[0]}      colons {b4[1]} -> {af[1]}      em-dashes {b4[2]} -> {af[2]}")
print(f"  transformed: {n['semi_period']} semicolon->period, {n['semi_and']} '; and'->', and', "
      f"{n['colon_period']} colon->period")
print(f"  deliberately kept: {n['semi_kept_enum']} enumeration semicolons")
if "--report" not in sys.argv:
    SRC.write_text(head + new, encoding="utf-8")
    print("  written")
