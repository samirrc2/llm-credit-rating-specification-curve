#!/usr/bin/env python3
"""Audit every design-dependent quantity for the scope error found in the aliasing diagnostic.

The previously reported aliasing figures (0.062 / 0.333) came from grid_definition.json, which has
48 specifications across THREE providers, while the variance decomposition is fitted on the
two-provider 32-specification arm. Having found one scope error we establish whether any other
reported quantity shares it, rather than assert that none does.

Spec: analysis/revision2/SPEC_r3_heldout_issuer_and_audit.md (hashed before this ran).
"""
import json, re
from pathlib import Path
import pandas as pd

PB = Path(__file__).resolve().parents[2]
P = pd.read_parquet(PB / "data/panel/panel.parquet")
TWO = P[P.provider.isin(["openai", "google"])]
ANALYSED = sorted(TWO[(TWO.family == "credit_health") & (TWO.parse_rule == "lenient")]
                  .spec_id.unique())
GRID = [s.get("spec_id") for s in json.load(
    open(PB / "data/frozen/main/grid_definition.json"))["specs"]]
print(f"  analysed arm: {len(ANALYSED)} specs (two providers)")
print(f"  grid file   : {len(GRID)} specs (three providers)\n")

# every script that could derive a quantity from the specification design
SCRIPTS = sorted([p for p in (PB / "analysis").rglob("*.py")])
DESIGN_TOKENS = ("grid_definition", "spec_id", "A1_provider", "X'X", "effect cod", "alias",
                 "logdet", "offdiag", "canonical", "2FI", "twofi", "design")
rows = []
for sp in SCRIPTS:
    src = sp.read_text(encoding="utf-8", errors="replace")
    if not any(t in src for t in DESIGN_TOKENS):
        continue
    reads_grid = "grid_definition" in src
    filters_two = bool(re.search(r'provider\.isin\(\[\s*["\']openai', src)) or \
                  bool(re.search(r'isin\(\["openai", "google"\]\)', src))
    rows.append({"script": str(sp.relative_to(PB)),
                 "reads_48_spec_grid": reads_grid,
                 "filters_to_two_providers": filters_two})
w = max(len(r["script"]) for r in rows)
print(f"  {'script'.ljust(w)}  reads_48_grid  filters_2_providers  verdict")
suspect = []
for r in rows:
    # a script that reads the 48-spec grid WITHOUT filtering to the analysed two providers is
    # reporting a design-level quantity for a design that is not the one analysed
    v = "SCOPE RISK" if (r["reads_48_spec_grid"] and not r["filters_to_two_providers"]) else "ok"
    if v != "ok":
        suspect.append(r["script"])
    print(f"  {r['script'].ljust(w)}  {str(r['reads_48_spec_grid']).ljust(13)}  "
          f"{str(r['filters_to_two_providers']).ljust(19)}  {v}")

out = {"_meta": {"spec": "analysis/revision2/SPEC_r3_heldout_issuer_and_audit.md",
                 "spec_sha256": open(PB / "results/SPEC_r3_heldout_issuer_and_audit.sha256")
                                .read().split()[0]},
       "analysed_spec_count": len(ANALYSED), "grid_spec_count": len(GRID),
       "scripts_examined": len(rows), "scope_risk_scripts": suspect, "detail": rows}
json.dump(out, open(PB / "results/results_design_audit.json", "w"), indent=1)
print(f"\n  {len(rows)} design-dependent scripts examined; "
      f"{len(suspect)} read the 48-spec grid without filtering to the analysed arm")
if suspect:
    print("  -> each must be checked for whether its OUTPUT is reported for the two-provider arm:")
    for s in suspect:
        print(f"     {s}")
print("  -> results/results_design_audit.json")
