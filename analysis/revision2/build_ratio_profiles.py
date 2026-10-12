#!/usr/bin/env python3
"""Build scale-invariant (ratios-only) profiles for Experiment A, and PROVE they are invariant.

Spec: analysis/revision2/SPEC_r3_realarm_experiments.md (hashed before any model call).
Offline, deterministic, no model calls. The spec requires that multiplying every dollar quantity
by any factor leaves the ratios-only profile byte-identical; that is asserted here, so a leak of
absolute magnitude into the probe cannot pass unnoticed.
"""
import json
from pathlib import Path

PB = Path(__file__).resolve().parents[2]
B = json.load(open(PB / "data/frozen/realarm/battery_real45.json"))
ITEMS = B if isinstance(B, list) else B.get("items") or list(B.values())[0]

def dollars(kv):
    """Parse the dollar fields of one issuer into floats (all are '<number>M')."""
    out = {}
    for k, v in kv:
        s = str(v).replace(",", "").strip()
        mult = 1.0
        if s.endswith("M"):
            s = s[:-1]
        elif s.endswith("B"):
            s, mult = s[:-1], 1000.0
        try:
            out[k] = float(s) * mult
        except ValueError:
            pass
    return out

def ratio_profile(kv):
    """Scale-invariant profile. Every entry is a ratio or a percentage of another dollar field,
    so a common multiplicative factor cancels exactly."""
    d = dollars(kv)
    g = lambda *names: next((d[n] for n in names if n in d), None)
    rev = g("Revenue"); ebit = g("EBIT / operating income"); ni = g("Net income")
    ta = g("Total assets"); tl = g("Total liabilities"); eq = g("Shareholders' equity")
    ca = g("Current assets"); cl = g("Current liabilities"); re = g("Retained earnings")
    pct = lambda a, b: None if (a is None or not b) else round(100.0 * a / b, 1)
    rat = lambda a, b: None if (a is None or not b) else round(a / b, 3)
    fields = [
        ("Operating margin (% of revenue)", pct(ebit, rev)),
        ("Net margin (% of revenue)", pct(ni, rev)),
        ("Return on assets (% of total assets)", pct(ni, ta)),
        ("Asset turnover (revenue / total assets)", rat(rev, ta)),
        ("Total liabilities / total assets", rat(tl, ta)),
        ("Total liabilities / equity", rat(tl, eq)),
        ("Equity / total assets", rat(eq, ta)),
        ("Current ratio (current assets / current liabilities)", rat(ca, cl)),
        ("Working capital / total assets", rat(None if (ca is None or cl is None) else ca - cl, ta)),
        ("Retained earnings / total assets", rat(re, ta)),
        ("EBIT / total assets", rat(ebit, ta)),
    ]
    return [(k, v) for k, v in fields if v is not None]

def render(prof):
    return "; ".join(f"{k} {v}" for k, v in prof)

rows = []
for it in ITEMS:
    prof = ratio_profile(it["facts_kv"])
    # the invariance assertion the spec demands
    for f in (0.6, 1.0, 1.7, 3.3, 11.0):
        scaled = [[k, f"{dollars(it['facts_kv'])[k] * f:.6f}M"] for k, _ in it["facts_kv"]
                  if k in dollars(it["facts_kv"])]
        assert render(ratio_profile(scaled)) == render(prof), (
            f"SCALE LEAK: {it['item_id']} ratios-only profile changed at factor {f}")
    rows.append({"item_id": it["item_id"], "benchmark_label": it["benchmark_label"],
                 "n_fields": len(prof), "ratios_only_text": render(prof)})

assert len(rows) == 31, f"expected 31 issuers, built {len(rows)}"
op = PB / "data/frozen/realarm/ratio_profiles.json"
json.dump({"_meta": {"spec": "analysis/revision2/SPEC_r3_realarm_experiments.md",
                     "spec_sha256": open(PB / "results/SPEC_r3_realarm_experiments.sha256")
                                    .read().split()[0],
                     "n_issuers": len(rows), "model_calls": 0,
                     "scale_invariance_asserted_at": [0.6, 1.0, 1.7, 3.3, 11.0]},
           "profiles": rows}, open(op, "w"), indent=1)
print(f"  built {len(rows)} ratios-only profiles; scale-invariance asserted at 5 factors")
print(f"  field counts: min={min(r['n_fields'] for r in rows)} max={max(r['n_fields'] for r in rows)}")
print(f"  example ({rows[0]['item_id']}): {rows[0]['ratios_only_text'][:150]}")
print(f"  -> {op.relative_to(PB)}")
