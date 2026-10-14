#!/usr/bin/env bash
# Reproduce every number/table/figure from the FROZEN data — offline, no API calls, zero cost.
# Requires: "$PY" with numpy, pandas, pyarrow, matplotlib, pyyaml.
set -euo pipefail
cd "$(dirname "$0")"

# Honour an externally supplied interpreter. Without this the script runs whatever "python3"
# happens to be first on PATH -- an anaconda base environment, for instance, whose scipy and
# statsmodels disagree and abort run_analysis.py at the variance decomposition. Quoted at every
# call site because this repository's own path contains a space.
PY="${PY:-python3}"
echo "== Main study (reads data/panel/panel.parquet + data/frozen/main) =="
"$PY" analysis/run_analysis.py
"$PY" analysis/addenda.py
"$PY" analysis/benchmark_validation.py
echo "== Real-firm arm (reads data/raw/realarm model-output panels) =="
"$PY" analysis/analyze_realarm.py
echo "== Real-firm external-benchmark specification curve (R3-1: agency ratings, not used in construction) =="
"$PY" analysis/realarm_speccurve.py
echo "== Real-firm scale-sensitivity (R3-4: does LLM output track absolute monetary scale?) =="
"$PY" analysis/realarm_scale_sensitivity.py
echo "== Model-tier robustness (flagship vs nano/flash on the frozen 12-spec grid) =="
"$PY" analysis/tier_analysis.py
echo "== Extended analyses (score validation, self-consistency, weighted agreement, strata, cost) =="
"$PY" analysis/extended_analysis.py
echo "== Revision analyses (boundary severity, capital robustness, turnover recast, aliasing) =="
"$PY" analysis/revision_analysis.py
echo "== Corrected rating-invariance permutation (R3-3) + SIS tau calibration (R3-5) =="
"$PY" analysis/permtest_and_tau.py
echo "== Variance explained by different model specifications (R3-2 option b) =="
"$PY" analysis/variance_model_range.py
echo "== Cross-model transfer of the instability score (R2-5/R3-5) + design aliasing (R2-4/R3-2) =="
"$PY" analysis/crossmodel_aliasing.py
echo "== Reasoning-architecture arm (offline; skips gracefully if corpus not yet collected) =="
"$PY" analysis/reasoning_analysis.py
echo "== Revision-2 analyses (offline, deterministic; feed Tables 1, 4, 5, 7, 8, 9) =="
"$PY" analysis/revision2/r2_chance_baseline.py
"$PY" analysis/revision2/r3_sis_baselines.py
"$PY" analysis/revision2/r3_alias_bounds.py
"$PY" analysis/revision2/r3_decision_curve.py
"$PY" analysis/revision2/r2r3_followups.py
"$PY" analysis/revision2/r3_heldout_issuer.py
"$PY" analysis/revision2/r3_decontam_analysis.py
"$PY" analysis/revision2/design_audit.py
"$PY" analysis/revision2/canonical_fixes.py
echo "== Regenerate the generated table bodies from the result JSONs =="
"$PY" build/make_sis_tables.py
"$PY" build/make_decontam_table.py
echo "== Done. Outputs in results/ =="
