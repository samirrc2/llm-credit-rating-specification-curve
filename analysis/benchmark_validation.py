"""POST-HOC VALIDATION (labelled) — independent Altman Z'' re-execution confirming the credit
benchmark construction rule. Deterministic; NO randomness; NO API calls. Reads ONLY the frozen
00_frozen_inputs/battery_90.json (45 credit_health items). Modifies no frozen artifact.

Pinned grid (fixed from published source BEFORE touching items; no tuning):
  Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4        (plain Z'', no +3.25 constant)
    X1 = (Current assets - Current liabilities) / Total assets
    X2 = Retained earnings / Total assets
    X3 = EBIT / Total assets
    X4 = Shareholders' equity (book) / Total liabilities
  Bands: Z'' > 2.60 SAFE ; 1.10 <= Z'' <= 2.60 WATCH ; Z'' < 1.10 DISTRESS
Source: Altman (2005) Emerging Markets Review 6(4), 311-323; Altman & Hotchkiss (2006) ch.12.

Writes 03_analysis/benchmark_validation.{json,csv} + MANIFEST_VALIDATION.sha256. Post-hoc.
"""
from __future__ import annotations
import json, csv, hashlib
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
BATTERY = PB / "data" / "frozen" / "main" / "battery_90.json"

# ---- pinned constants (published source; DO NOT tune) ----
COEF = {"X1": 6.56, "X2": 3.26, "X3": 6.72, "X4": 1.05}
CUT_SAFE, CUT_DISTRESS = 2.60, 1.10
RANK = {"SAFE": 0, "WATCH": 1, "DISTRESS": 2}

def parse_m(s: str) -> float:
    """'18,044M' / '-1,234M' / '1.34' -> float. Strips commas and trailing M."""
    t = str(s).strip().replace(",", "")
    if t.endswith("M") or t.endswith("m"):
        t = t[:-1]
    return float(t)

def band_of(z: float) -> str:
    if z > CUT_SAFE:
        return "SAFE"
    if z < CUT_DISTRESS:
        return "DISTRESS"
    return "WATCH"

B = json.loads(BATTERY.read_text())
cr = [x for x in B if x.get("family") == "credit_health"]
battery_sha = hashlib.sha256(BATTERY.read_bytes()).hexdigest()

rows = []
n_exact = n_within = 0
for it in cr:
    kv = {k: v for k, v in it["facts_kv"]}
    CA = parse_m(kv["Current assets"]); CL = parse_m(kv["Current liabilities"])
    TA = parse_m(kv["Total assets"]);   TL = parse_m(kv["Total liabilities"])
    RE = parse_m(kv["Retained earnings"]); EBIT = parse_m(kv["EBIT / operating income"])
    EQ = parse_m(kv["Shareholders' equity"])
    X1 = (CA - CL) / TA
    X2 = RE / TA
    X3 = EBIT / TA
    X4 = EQ / TL
    Z = COEF["X1"]*X1 + COEF["X2"]*X2 + COEF["X3"]*X3 + COEF["X4"]*X4
    reexec = band_of(Z)
    bench = it["benchmark_label"]
    exact = (reexec == bench)
    within = (abs(RANK[reexec] - RANK[bench]) <= 1)
    n_exact += exact; n_within += within
    dist_cut = min(abs(Z - CUT_SAFE), abs(Z - CUT_DISTRESS))  # distance to nearest band cutoff
    rows.append({
        "item_id": it["item_id"], "ticker": it["ticker"],
        "X1": round(X1, 4), "X2": round(X2, 4), "X3": round(X3, 4), "X4": round(X4, 4),
        "Zpp": round(Z, 4), "reexec_band": reexec, "benchmark_label": bench,
        "exact": bool(exact), "within_one": bool(within),
        "dist_to_nearest_cutoff": round(dist_cut, 4),
        "rounding_boundary_flag": bool((not exact) and dist_cut <= 0.10),
    })

N = len(cr)
misses = [r for r in rows if not r["exact"]]
beyond_one = [r for r in rows if not r["within_one"]]
boundary_misses = [r for r in misses if r["rounding_boundary_flag"]]

summary = {
    "_label": "POST-HOC VALIDATION (labelled): independent Altman Z'' re-execution of the frozen "
              "credit benchmark. Deterministic, no API calls, reads battery_90.json only. "
              "Grid pinned from Altman (2005) BEFORE touching items; no tuning.",
    "validation.source": "Altman, E.I. (2005), An emerging market credit scoring system for corporate "
                          "bonds, Emerging Markets Review 6(4), 311-323; Altman & Hotchkiss (2006) ch.12.",
    "validation.grid": {"coefficients": COEF, "band_cutoffs": {"SAFE_gt": CUT_SAFE, "DISTRESS_lt": CUT_DISTRESS},
                        "form": "plain Z'' (no +3.25 constant)"},
    "validation.n_items": N,
    "validation.exact_band": f"{n_exact}/{N}",
    "validation.exact_band_share": round(n_exact / N, 4),
    "validation.within_one_band": f"{n_within}/{N}",
    "validation.within_one_band_share": round(n_within / N, 4),
    "validation.n_misses": len(misses),
    "validation.n_beyond_one_band": len(beyond_one),
    "validation.n_misses_rounding_boundary": len(boundary_misses),
    "validation.miss_detail": [
        {"item_id": r["item_id"], "ticker": r["ticker"], "Zpp": r["Zpp"],
         "reexec_band": r["reexec_band"], "benchmark_label": r["benchmark_label"],
         "dist_to_nearest_cutoff": r["dist_to_nearest_cutoff"],
         "rounding_boundary_flag": r["rounding_boundary_flag"]} for r in misses],
    "validation.battery_sha256": battery_sha,
    "validation.frozen_artifacts_modified": "NONE",
    "_per_item": rows,
}

OUT_JSON = PB / "results" / "benchmark_validation.json"
OUT_CSV = PB / "results" / "benchmark_validation.csv"
OUT_JSON.write_text(json.dumps(summary, indent=1))
with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

# Own manifest hash over the two new outputs + this script (no frozen file touched).
# The script is hashed from __file__, not from a copy under results/. A copy lived there,
# left over from an earlier layout that still referenced 00_frozen_inputs/ and 03_analysis/,
# so the manifest certified a fossil rather than the source that produced the outputs -- and
# the capsule, which ships code and data but not results/, could not run this step at all.
h = hashlib.sha256()
for f in ["benchmark_validation.json", "benchmark_validation.csv"]:
    h.update((PB / "results" / f).read_bytes())
h.update(Path(__file__).resolve().read_bytes())
(PB / "results" / "MANIFEST_VALIDATION.sha256").write_text(
    h.hexdigest() + "  benchmark_validation.{json,csv,py}\n")

print(f"exact-band:      {n_exact}/{N}  ({n_exact/N:.1%})")
print(f"within-one-band: {n_within}/{N}  ({n_within/N:.1%})")
print(f"misses: {len(misses)} | beyond-one: {len(beyond_one)} | rounding-boundary misses (<=0.10 to cutoff): {len(boundary_misses)}")
print("MANIFEST_VALIDATION:", h.hexdigest()[:16])
if misses:
    print("\nper-miss diagnostic:")
    for r in misses:
        print(f"  {r['item_id']} {r['ticker']:5s} Z''={r['Zpp']:7.3f}  reexec={r['reexec_band']:8s} bench={r['benchmark_label']:8s}"
              f"  d(cutoff)={r['dist_to_nearest_cutoff']:.3f}  boundary={r['rounding_boundary_flag']}")
