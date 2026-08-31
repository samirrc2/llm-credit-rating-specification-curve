#!/usr/bin/env bash
# Reproduce every number/table/figure from the FROZEN data — offline, no API calls, zero cost.
# Requires: python3 with numpy, pandas, pyarrow, matplotlib, pyyaml.
set -euo pipefail
cd "$(dirname "$0")"
echo "== Main study (reads data/panel/panel.parquet + data/frozen/main) =="
python3 analysis/run_analysis.py
python3 analysis/capital_analysis.py
python3 analysis/market_analysis.py
python3 analysis/addenda.py
python3 analysis/benchmark_validation.py
echo "== Real-firm arm (reads data/raw/realarm model-output panels) =="
python3 analysis/analyze_realarm.py
echo "== Model-tier robustness (flagship vs nano/flash on the frozen 12-spec grid) =="
python3 analysis/tier_analysis.py
echo "== Extended analyses (score validation, self-consistency, weighted agreement, strata, cost) =="
python3 analysis/extended_analysis.py
echo "== Done. Outputs in results/ =="
