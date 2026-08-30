"""ADDITION 1b (POST-HOC, labelled) — market-priced spread translation. Re-prices each
name's cross-specification credit-verdict RANGE against the ACTUAL ICE BofA OAS curve on
every trading day 2023-2026 (FRED, cached in 01b_market_data). No model calls.
Writes 03_analysis/results_market.json.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd

PB = Path(__file__).resolve().parents[1]
MD = PB / "data" / "frozen" / "market_data"
SER = [("AAA", "BAMLC0A1CAAA"), ("AA", "BAMLC0A2CAA"), ("A", "BAMLC0A3CA"), ("BBB", "BAMLC0A4CBBB"),
       ("BB", "BAMLH0A1HYBB"), ("B", "BAMLH0A2HYB"), ("CCC", "BAMLH0A3HYC")]  # index 0..6 best..worst
IDX = {r: i for i, (r, _) in enumerate(SER)}

# load OAS (percent -> bps) into a date-aligned matrix
frames = []
for r, sid in SER:
    df = pd.read_csv(MD / f"{sid}.csv", names=["date", r], header=0)
    df[r] = pd.to_numeric(df[r], errors="coerce") * 100.0   # % -> bps
    frames.append(df.set_index("date")[r])
OAS = pd.concat(frames, axis=1).dropna()                    # common trading days x 7 buckets
DAYS = OAS.index.tolist()

# per-name best/worst bucket from the frozen panel
P = pd.read_parquet(PB / "data" / "panel" / "panel.parquet")
P = P[P.provider.isin(["openai","google"])].copy()  # two-vendor design
CR = P[(P.parse_rule == "lenient") & (P.family == "credit_health") & P.dec_letter.notna()]
def bkt(l):
    b = l.rstrip("+-")
    return {"AAA": 0, "AA": 1, "A": 2, "BBB": 3, "BB": 4, "B": 5, "CCC": 6, "CC": 6, "C": 6}[b]
NAMES = {}
for it, g in CR.groupby("item_id"):
    bs = sorted(set(bkt(l) for l in g.dec_letter))
    NAMES[it] = (bs[0], bs[-1])

cols = [r for r, _ in SER]
per_name = {}
for name, (b0, b1) in NAMES.items():
    daily = (OAS[cols[b1]] - OAS[cols[b0]]).values                # spread range in bps, each trading day
    per_name[name] = {"best": cols[b0], "worst": cols[b1],
                      "median_bps": float(np.median(daily)), "p25_bps": float(np.percentile(daily, 25)),
                      "p75_bps": float(np.percentile(daily, 75)), "min_bps": float(daily.min()),
                      "max_bps": float(daily.max())}

med_across_names = float(np.median([v["median_bps"] for v in per_name.values()]))
iqr = [float(np.percentile([v["median_bps"] for v in per_name.values()], 25)),
       float(np.percentile([v["median_bps"] for v in per_name.values()], 75))]
floor_any = float(min(v["min_bps"] for v in per_name.values()))     # smallest range any name on any day
median_name_floor = float(np.median([v["min_bps"] for v in per_name.values()]))

# ---- saturation diagnostics (median==IQR-upper is a ceiling artefact, not a distribution) ----
full_scale = [n for n, (b0, b1) in NAMES.items() if b0 == 0 and b1 == 6]     # AAA..CCC
worst_ccc = [n for n, (b0, b1) in NAMES.items() if b1 == 6]                   # verdict reaches CCC
nonsat = {n: v for n, v in per_name.items() if NAMES[n][1] < 6}              # verdict does NOT reach CCC
nonsat_med = ([round(float(np.median([v["median_bps"] for v in nonsat.values()])), 1),
               round(float(np.percentile([v["median_bps"] for v in nonsat.values()], 25)), 1),
               round(float(np.percentile([v["median_bps"] for v in nonsat.values()], 75)), 1)]
              if nonsat else None)

OUT = {"_label": "POST-HOC ADDITION (labelled): market-priced against ICE BofA OAS (FRED), no model calls.",
       "economic.market_priced.n_names": len(per_name),
       "economic.market_priced.n_trading_days": len(DAYS),
       "economic.market_priced.window": [DAYS[0], DAYS[-1]],
       "economic.market_priced.per_name_spread_range_median_bps": round(med_across_names, 1),
       "economic.market_priced.per_name_spread_range_IQR_bps": [round(iqr[0], 1), round(iqr[1], 1)],
       "economic.market_priced.floor_any_name_any_day_bps": round(floor_any, 1),
       "economic.market_priced.median_name_floor_bps": round(median_name_floor, 1),
       "economic.market_priced.share_verdict_reaches_CCC": round(len(worst_ccc) / len(per_name), 3),
       "economic.market_priced.share_full_scale_AAA_to_CCC": round(len(full_scale) / len(per_name), 3),
       "economic.market_priced.saturation_note": (
           f"{len(worst_ccc)}/{len(per_name)} names have a verdict reaching CCC, so their spread range "
           f"collapses to (CCC_OAS - best_OAS) and is near-identical across those names on a given day — "
           f"hence median==IQR-upper ({round(med_across_names)} bps) is a SCALE-SATURATION ceiling, not a "
           f"smooth distribution. The share reaching CCC ({round(len(worst_ccc)/len(per_name)*100)}%) is "
           f"itself a fragility statistic."),
       "economic.market_priced.nonsaturating_spread_range_median_IQR_bps": nonsat_med,
       "economic.market_priced.n_nonsaturating": len(nonsat),
       "economic.market_priced.reconciliation_413_vs_820": (
           "413 bps (earlier) came from a STATIC 3-band map (SAFE 150 / WATCH 300 / DISTRESS 700). 820 bps "
           "here is priced on the LIVE ICE BofA OAS curve, which is CCC-inclusive (CCC OAS ~1000 bps >> the "
           "static DISTRESS=700 proxy) and uses the finer letter elicitation that reaches CCC. Different "
           "instruments, not a revision: static map vs market curve, band vs letter granularity."),
       "economic.market_priced.statement": (
           "Re-pricing each name's cross-specification verdict range against the actual ICE BofA OAS curve on "
           f"all {len(DAYS)} trading days {DAYS[0]}..{DAYS[-1]}: the implied spread range per name is "
           f"{round(med_across_names)} bps (median across names of the per-name median-across-days), IQR "
           f"[{round(iqr[0])}, {round(iqr[1])}] bps; across all names the range is never below "
           f"{round(floor_any)} bps on any trading day in the window."),
       "economic.market_priced.cornaggia_anchor": "literature anchor retained: 80-140 bps per 2-3 notches (Cornaggia, Cornaggia & Israelsen)",
       "economic.market_priced.manifest": json.loads((MD / "MANIFEST_MARKET.json").read_text())["series"],
       "_per_name": per_name}
(PB / "results" / "results_market.json").write_text(json.dumps(OUT, indent=1))
print("trading days:", len(DAYS), DAYS[0], "->", DAYS[-1])
print("per-name spread range: median", round(med_across_names, 1), "bps  IQR", [round(x, 1) for x in iqr])
print("floor (any name, any day):", round(floor_any, 1), "bps  | median-name floor:", round(median_name_floor, 1), "bps")
print(OUT["economic.market_priced.statement"])
