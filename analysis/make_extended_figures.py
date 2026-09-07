#!/usr/bin/env python3
"""Regenerate the revision figures (offline) from results/results_extended.json:
  fig_selfconsistency.pdf  — residual IG/HY flip vs k-of-n majority vote
Writes into paper/NLP/. Requires matplotlib (optional dependency)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PB = Path(__file__).resolve().parents[1]
E = json.load(open(PB / "results" / "results_extended.json"))
OUT = PB / "paper" / "NLP"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 200})

curve = E["B1.self_consistency_residual_flip_by_k"]
ks = [int(k) for k in curve]; ys = [100 * curve[str(k)] for k in ks]
fig, ax = plt.subplots(figsize=(5.6, 3.4))
ax.plot(ks, ys, "-o", color="#1f4e79", zorder=3)
for k, y in zip(ks, ys):
    ax.annotate(f"{y:.1f}%", (k, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
ax.set_xlabel("elicitations aggregated per issuer (k, majority vote)")
ax.set_ylabel("residual IG/HY flip (%)")
ax.set_xticks(ks); ax.set_ylim(0, max(ys) * 1.25)
fig.tight_layout()
fig.savefig(OUT / "fig_selfconsistency.pdf")
plt.close(fig)
print("wrote", OUT / "fig_selfconsistency.pdf", "| ks:", ks, "residual flip %:", [round(y, 1) for y in ys])
