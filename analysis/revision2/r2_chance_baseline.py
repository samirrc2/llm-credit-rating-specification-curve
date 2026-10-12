#!/usr/bin/env python3
"""R2.4 — what is the correct chance baseline for the machine-vs-agency band comparison?

The manuscript says 54% agreement is "above the ~33% expected by chance on 3 bands". That 1/3 is a
UNIFORM three-class reference. Reviewer 2 asks whether it is uniform or marginal-corrected, and for
the calculation if the latter. This computes both, offline and deterministically, from the frozen
real-arm panel. No new data.
"""
import json, glob
from collections import Counter
from pathlib import Path
import numpy as np

PB = Path(__file__).resolve().parents[2]
rng = np.random.default_rng(42)
panel = sorted(glob.glob(str(PB / "data/raw/realarm/arm_runs/run_*/arm_panel.json")))[-1]
rows = [r for r in json.load(open(panel))["rows"] if r.get("parsed_band") and r.get("benchmark_label")]
print(f"  panel {Path(panel).parent.name}: {len(rows)} scored elicitations")

# the manuscript's three-band comparison excludes the single DISTRESS issuer (a singleton stratum)
bench_by_item = {r["item_id"]: r["benchmark_label"] for r in rows}
distress = [i for i, b in bench_by_item.items() if b == "DISTRESS"]
keep = [r for r in rows if r["benchmark_label"] != "DISTRESS"]
print(f"  excluded singleton DISTRESS issuer(s): {distress}")
print(f"  comparison set: {len(keep)} elicitations, {len({r['item_id'] for r in keep})} issuers, "
      f"{len({r['spec_id'] for r in keep})} specifications")

m = [r["parsed_band"] for r in keep]        # machine band
a = [r["benchmark_label"] for r in keep]    # agency band
n = len(m)
observed = float(np.mean([x == y for x, y in zip(m, a)]))
pm = {k: v / n for k, v in Counter(m).items()}
pa = {k: v / n for k, v in Counter(a).items()}
classes = sorted(set(pm) | set(pa))
marginal = float(sum(pm.get(c, 0.0) * pa.get(c, 0.0) for c in classes))
uniform = 1.0 / 3.0
kappa = (observed - marginal) / (1 - marginal)

print(f"\n  machine band marginals: " + ", ".join(f"{c} {pm.get(c,0):.3f}" for c in classes))
print(f"  agency  band marginals: " + ", ".join(f"{c} {pa.get(c,0):.3f}" for c in classes))
print(f"\n  observed agreement                 {observed:.4f}")
print(f"  uniform three-class reference      {uniform:.4f}   (what the manuscript cites)")
print(f"  marginal-matching chance baseline  {marginal:.4f}   = sum_c p_machine(c) p_agency(c)")
print(f"  Cohen's kappa against marginals    {kappa:.4f}")

# issuer-clustered bootstrap on the excess over each baseline
items = sorted({r["item_id"] for r in keep})
by = {it: [(r["parsed_band"], r["benchmark_label"]) for r in keep if r["item_id"] == it] for it in items}
def draw():
    s = [p for it in rng.choice(items, len(items), replace=True) for p in by[it]]
    mm = [x for x, _ in s]; aa = [y for _, y in s]; k = len(s)
    o = float(np.mean([x == y for x, y in zip(mm, aa)]))
    qm = {q: v / k for q, v in Counter(mm).items()}; qa = {q: v / k for q, v in Counter(aa).items()}
    mb = float(sum(qm.get(c, 0.0) * qa.get(c, 0.0) for c in set(qm) | set(qa)))
    return o, mb
B = np.array([draw() for _ in range(2000)])
ci = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
exc_u = B[:, 0] - uniform
exc_m = B[:, 0] - B[:, 1]
print(f"\n  excess over uniform    {observed-uniform:+.4f}  95% CI {ci(exc_u)}")
print(f"  excess over marginals  {observed-marginal:+.4f}  95% CI {ci(exc_m)}")
out = {"panel": Path(panel).parent.name, "n_elicitations": n,
       "n_issuers": len({r["item_id"] for r in keep}), "excluded_distress_items": distress,
       "observed_agreement": round(observed, 4),
       "uniform_three_class_reference": round(uniform, 4),
       "marginal_matching_baseline": round(marginal, 4),
       "cohens_kappa_vs_marginals": round(kappa, 4),
       "machine_marginals": {c: round(pm.get(c, 0.0), 4) for c in classes},
       "agency_marginals": {c: round(pa.get(c, 0.0), 4) for c in classes},
       "excess_over_uniform": round(observed - uniform, 4), "excess_over_uniform_ci": ci(exc_u),
       "excess_over_marginals": round(observed - marginal, 4),
       "excess_over_marginals_ci": ci(exc_m),
       "bootstrap": "issuer-clustered, 2000 draws, seed 42"}
json.dump(out, open(PB / "results/results_r2_chance_baseline.json", "w"), indent=1)
print(f"\n  -> results/results_r2_chance_baseline.json")
