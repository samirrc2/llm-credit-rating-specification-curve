#!/usr/bin/env python3
"""Regenerate the three manuscript figures from the current results (offline).
Reads results/results.json + results/spec_curves.json; writes the figures into
paper/ISWA so they always match the reported numbers.
Requires matplotlib (optional dependency; not needed to reproduce the numbers)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PB = Path(__file__).resolve().parents[1]
R = json.load(open(PB / "results" / "results.json"))
SC = json.load(open(PB / "results" / "spec_curves.json"))
OUT_DIRS = [PB / "paper" / "ISWA"]

def find(key):
    for b in R.values():
        if isinstance(b, dict) and key in b:
            return b[key]
    return None

plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 200})

# ---- Figure 1: specification curve, two panels --------------------------------------
# (a) per-spec design-label recovery vs the constructed Altman strata (not external accuracy)
# (b) per-spec investment-grade share (benchmark-free: pure dispersion of the verdict)
c1 = sorted(SC["C1"].values())
import pandas as pd
_P = pd.read_parquet(PB / "data" / "panel" / "panel.parquet")
_P = _P[_P.provider.isin(["openai", "google"])]
_CR = _P[(_P.family == "credit_health") & (_P.parse_rule == "lenient") & _P.decision.notna()]
ig_share = sorted((_CR.assign(ig=(_CR.dec_ighy == "IG").astype(float))
                   .groupby("spec_id").ig.mean()).values)
fig, (axL, axR) = plt.subplots(1, 2, figsize=(7.4, 3.3))
axL.scatter(range(1, len(c1) + 1), c1, s=16, color="#1f4e79", zorder=3)
axL.axhline(0.5, color="#c0392b", lw=1, ls="--", label="majority threshold (0.5)")
axL.set_xlabel(f"specification (ordered), n={len(c1)}")
axL.set_ylabel("design-label recovery vs Altman Z'' strata")
axL.set_ylim(0, 1); axL.legend(frameon=False, fontsize=8, loc="upper left")
axL.set_title("(a) design-label recovery", fontsize=9)
axR.scatter(range(1, len(ig_share) + 1), ig_share, s=16, color="#2e6f4e", zorder=3)
axR.set_xlabel(f"specification (ordered), n={len(ig_share)}")
axR.set_ylabel("investment-grade share")
axR.set_ylim(0, 1)
axR.set_title("(b) benchmark-free (IG share)", fontsize=9)
fig.tight_layout()
for d in OUT_DIRS: fig.savefig(d / "fig_spec_curve.png")
plt.close(fig)

# ---- Figure 2: disagreement share by rating granularity ----
kl = find("table5.chance_corrected_POSTHOC")
gran = ["letter", "notch", "band", "ig_hy"]
labels = ["Letter\n(21)", "Notch\n(9)", "Band\n(3)", "IG/HY\n(2)"]
disagree = [100 * (1 - kl[g]["raw_agreement"]) for g in gran]
fig, ax = plt.subplots(figsize=(5.6, 3.4))
bars = ax.bar(labels, disagree, color="#1f4e79", width=0.62)
for b, v in zip(bars, disagree):
    ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9)
ax.set_ylabel("matched-pair disagreement (%)")
ax.set_ylim(0, 100)
fig.tight_layout()
for d in OUT_DIRS: fig.savefig(d / "figure1_ighy.pdf")
plt.close(fig)

# ---- Figure 3: Fleiss kappa by rating granularity ----
import decimal
def r2(v):  # round half up to 2 dp so labels match the manuscript text
    return decimal.Decimal(str(v)).quantize(decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP)
kappa = [kl[g]["fleiss_kappa"] for g in gran]
fig, ax = plt.subplots(figsize=(5.6, 3.4))
bars = ax.bar(labels, kappa, color="#2e6f4e", width=0.62)
for b, v in zip(bars, kappa):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{r2(v)}", ha="center", fontsize=9)
ax.axhline(0.6, color="#c0392b", lw=1, ls="--", label="substantial-agreement threshold (0.60)")
ax.set_ylabel("Fleiss' $\\kappa$")
ax.set_ylim(0, 0.7); ax.legend(frameon=False, fontsize=8, loc="upper left")
fig.tight_layout()
for d in OUT_DIRS: fig.savefig(d / "figureA_kappa.pdf")
plt.close(fig)

print("figures written:", [str(d) for d in OUT_DIRS])
print(f"Fig1 spec points: {len(c1)} | Fig2 disagree: {[round(x) for x in disagree]} | Fig3 kappa: {[round(k,2) for k in kappa]}")
