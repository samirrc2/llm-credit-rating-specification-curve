#!/usr/bin/env python3
"""Anchored binding: each load-bearing figure tied to the claim it must equal AND the phrase it
must follow.

Coverage (build/check_coverage.py) is a set-membership test: it asks whether a printed number
appears somewhere in the results, not whether it appears in the RIGHT PLACE. con1 fault injection
showed the consequence -- swapping two real printed AUCs (0.936 <-> 0.951) passed coverage,
denominators, tables-fresh, freezing, blinding and the citation gate. Only binding catches it.

Each rule is (anchor, literal, json_path, decimals):
  anchor     a regex that must match the text immediately BEFORE the figure, exactly once
  literal    the figure as printed
  json_path  "file.json:/a/b/c" -- the single claim this occurrence must equal
  decimals   the precision the paper prints it at

Three ways a rule fails, all fatal:
  AMBIGUOUS ANCHOR  the (anchor, literal) pair matches more than once -> the rule cannot say
                    which occurrence it governs, so it is an authoring error, not a warning
  NO MATCH          the rule matches nothing -> the sentence was edited away
  VALUE             the printed literal does not equal the claim at the stated precision

Exit 0 all bound, 1 any failure, 2 could not check.
"""
import json, re, sys
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
MS = PB / "paper/NLP/cas-sc.tex"

# (anchor before the figure, printed literal, file:/path, decimals)
RULES = [
 # anchors taken verbatim from the manuscript, not guessed
 (r"with mean AUC\n",                         "0.936", "results_r2r3_followups.json:/semantic_entropy_benchmark/ighy/auc/sis", 3),
 (r"and weaker signal \(AUC \$",              "0.763", "results_r2r3_followups.json:/semantic_entropy_benchmark/ighy/auc/neg_boundary_dist", 3),
 (r"and weaker signal \(AUC \$0\.763\$ and \$", "0.655", "results_r2r3_followups.json:/semantic_entropy_benchmark/band/auc/neg_boundary_dist", 3),
 (r"interactions of other factors up to \$\|r\|=", "0.504", "results_r2r3_followups.json:/aliasing_on_analysed_design/main_x_2FI_max_abs_corr_nonparent", 3),
 (r"column of\nother axes is \$",             "0.504", "results_r2r3_followups.json:/aliasing_on_analysed_design/main_x_2FI_max_abs_corr_nonparent", 3),
 (r"\(maximum off-diagonal \$\|r\|=",         "0.125", "results_r2r3_followups.json:/aliasing_on_analysed_design/main_effect_max_offdiag_corr_distinct_axes", 3),
 (r"columns of distinct axes is \$",          "0.125", "results_r2r3_followups.json:/aliasing_on_analysed_design/main_effect_max_offdiag_corr_distinct_axes", 3),
 (r"p_\{\\mathrm\{agency\}\}\(c\)=",         "48.9", "results_r2_chance_baseline.json:/marginal_matching_baseline", 1),
 (r"disclosed agency ratings\n\$",            "53.7", "results_r2_chance_baseline.json:/observed_agreement", 1),
 (r"and Cohen's \$\\kappa\$ is \$",           "0.095", "results_r2_chance_baseline.json:/cohens_kappa_vs_marginals", 3),
 (r"for answer presentation it is \$",        "0.878", "results_r3_alias_bounds.json:/presentation_l2/A7_presentation=L0", 3),
 (r"of profiles at precision ",               "0.825", "results_canonical_fixes.json:/item8_canonical/rules/any_disagreement_sis_gt_0/precision", 3),
 (r"and recall ",                             "0.971", "results_canonical_fixes.json:/item8_canonical/rules/any_disagreement_sis_gt_0/recall", 3),
]
RULES = [r for r in RULES if r[1]]

def claim(spec):
    f, path = spec.split(":", 1)
    d = json.load(open(PB / "results" / f))
    cur = d
    for seg in [s for s in path.split("/") if s]:
        m = re.fullmatch(r"(.*)\[(\d+)\]", seg)
        if m:
            cur = cur[m.group(1)][int(m.group(2))] if m.group(1) else cur[int(m.group(2))]
        else:
            cur = cur[seg]
    return float(cur)

def main():
    if not MS.exists():
        print("NOT CHECKABLE: manuscript missing"); return 2
    s = MS.read_text(encoding="utf-8")
    bad, ok = [], 0
    for anchor, lit, spec, nd in RULES:
        pat = anchor + re.escape(lit)
        hits = list(re.finditer(pat, s))
        if len(hits) > 1:
            bad.append(f"AMBIGUOUS ANCHOR  {lit:>8}  matched {len(hits)}x  anchor={anchor[:46]!r}")
            continue
        if not hits:
            bad.append(f"NO MATCH          {lit:>8}  anchor={anchor[:46]!r}")
            continue
        try:
            want = claim(spec)
        except Exception as e:
            bad.append(f"CLAIM MISSING     {lit:>8}  {spec}  ({type(e).__name__})")
            continue
        for scale in (1.0, 100.0):
            if f"{round(want*scale, nd):.{nd}f}" == lit:
                ok += 1; break
        else:
            bad.append(f"VALUE             printed {lit}  claim {want}  at {nd}dp  {spec}")
    print(f"  binding rules: {len(RULES)}    bound: {ok}    failed: {len(bad)}")
    for b in bad: print(f"    {b}")
    if bad:
        print("\n  FAIL: anchored binding"); return 1
    print("\n  PASS: every bound figure follows its anchor exactly once and equals its claim")
    return 0

if __name__ == "__main__":
    sys.exit(main())
