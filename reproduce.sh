#!/usr/bin/env bash
# Reproduce every number/table/figure from the FROZEN data — offline, no API calls, zero cost.
# Requires: python3 with numpy, pandas, pyarrow, matplotlib, pyyaml.
set -euo pipefail
cd "$(dirname "$0")"
echo "== Main study (reads data/panel/panel.parquet + data/frozen/main) =="
python3 analysis/run_analysis.py
python3 analysis/addenda.py
python3 analysis/benchmark_validation.py
echo "== Real-firm arm (reads data/raw/realarm model-output panels) =="
python3 analysis/analyze_realarm.py
echo "== Real-firm external-benchmark specification curve (R3-1: agency ratings, not used in construction) =="
python3 analysis/realarm_speccurve.py
echo "== Real-firm scale-sensitivity (R3-4: does LLM output track absolute monetary scale?) =="
python3 analysis/realarm_scale_sensitivity.py
echo "== Model-tier robustness (flagship vs nano/flash on the frozen 12-spec grid) =="
python3 analysis/tier_analysis.py
echo "== Extended analyses (score validation, self-consistency, weighted agreement, strata, cost) =="
python3 analysis/extended_analysis.py
echo "== Revision analyses (boundary severity, capital robustness, turnover recast, aliasing) =="
python3 analysis/revision_analysis.py
echo "== Corrected rating-invariance permutation (R3-3) + SIS tau calibration (R3-5) =="
python3 analysis/permtest_and_tau.py
echo "== Variance explained by different model specifications (R3-2 option b) =="
python3 analysis/variance_model_range.py
echo "== Cross-model transfer of the instability score (R2-5/R3-5) + design aliasing (R2-4/R3-2) =="
python3 analysis/crossmodel_aliasing.py
echo "== Reasoning-architecture arm (offline; skips gracefully if corpus not yet collected) =="
python3 analysis/reasoning_analysis.py
echo "== Done. Outputs in results/ =="
