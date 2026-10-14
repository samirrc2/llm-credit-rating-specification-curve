#!/usr/bin/env python3
"""Bind each result quoted in README.md to the manuscript sentence that states it.

A coverage check -- "does this number appear somewhere in the paper?" -- is not enough. Changing
the README's Fleiss kappa from 0.49 to 0.52 passes such a check, because 0.52 occurs elsewhere in
the manuscript as an unrelated quantity. Only an anchored rule catches it: the value must follow
the phrase that names it, in BOTH documents.

Each rule is (readme anchor, manuscript anchor, value). Exit 0 bound, 1 failed, 2 could not check.
"""
import re
import sys
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
try:
    md = PB.joinpath("README.md").read_text(encoding="utf-8")
    tex = re.sub(r"\s+", " ", PB.joinpath("paper/manuscript_full.tex").read_text(encoding="utf-8"))
except Exception as e:
    print(f"NOT CHECKABLE: {e}"); sys.exit(2)
if len(md) < 2000 or len(tex) < 50000:
    print(f"NOT CHECKABLE: README {len(md)}B, manuscript {len(tex)}B"); sys.exit(2)
def _norm(t):
    # one minus sign, so a rule need not spell three different dashes
    return (t.replace("{,}", ",").replace("\\%", "%")
             .replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-"))
tex = _norm(tex)
mdf = _norm(re.sub(r"\s+", " ", md))

# (what it is, README anchor, manuscript anchor, value)
RULES = [
    ("IG/HY flip",            r"per-comparison IG/HY flip \*\*",      r"Holding fundamentals fixed, ",        "25.2%"),
    ("Fleiss kappa",          r"Fleiss' κ = \*\*|Fleiss' κ = ",      r"Fleiss' \$\\kappa=",                  "0.49"),
    ("pure seed variance",    r"Pure within-cell seed variance is \*\*", r"seed variation accounts for ",     "8.1%"),
    ("joint R2 low",          r"jointly explain \*\*R² = ",           r"axes jointly\s*explain a small, model-dependent share \(\$R\^2=|explain a small, model-dependent share \(\$R\^2=", "0.083"),
    ("permutation p",         r"gives\s*\*\*p = ",                    r"permutation \$p=",                    "0.0005"),
    ("flagship delta",        r"paired Δ ",                           r"IG/HY flip \(pooled\)",               "-1.1"),
    ("reasoning arm flip",    r"reasoning arm shows comparable instability \(", r"deepseek-r1} \(single model\) & ", "25.5"),
    ("held-out AUC",          r"SIS predicts held-out instability at \*\*ROC-AUC ", r"predicts held-out IG/HY instability \(ROC-AUC ", "0.94"),
    ("profile-split gate",    r"mean AUC ",                           r"mean AUC ",                           "0.936"),
    ("profile-split 3 bands", r"at the gate and ",                    r"at the gate and ",                    "0.950"),
    ("boundary AUC a",        r"weaker and different signal\s*\(AUC ", r"weaker signal \(AUC \$",             "0.763"),
    ("aliasing main",         r"off-diagonal correlation of \*\*",    r"columns of distinct axes is \$",      "0.125"),
    ("aliasing main x 2FI",   r"two-factor-interaction correlation of \*\*", r"two-factor-interaction column of other axes is \$", "0.504"),
    ("issuer-ID probe",       r"scale-invariant ratios alone at \*\*", r"scale-invariant financial ratios above chance \(", "19.4"),
    ("decontam new calls",    r"decontamination experiments \(\*\*",  r"In total ",                           "1,364"),
    ("decontam substantive",  r"1,364 new elicitations, ",            r"new elicitations across both providers, of which ", "1,361"),
]

fails = []
for what, a_md, a_tex, val in RULES:
    v = re.escape(val)
    if not re.search(a_md + r".{0,130}?" + v, mdf):
        fails.append(f"README    [{what}] '{val}' does not follow /{a_md}/")
    if not re.search(a_tex + r".{0,170}?" + v, tex):
        fails.append(f"MANUSCRIPT[{what}] '{val}' does not follow /{a_tex}/")

for f in fails:
    print("  " + f)
if fails:
    print(f"FAIL: {len(fails)} of {len(RULES)} README results are not bound to the manuscript")
    sys.exit(1)
print(f"PASS: all {len(RULES)} results quoted in README.md are bound to the manuscript sentence "
      f"that states them")
sys.exit(0)
