#!/usr/bin/env python3
"""R3 (direct question) — what IS identified under the 32-specification confirmatory design?

Reviewer 3 asks for formal identifiable bounds on (a) the answer-presentation main effect and
(b) the provider-by-item interaction, under all aliasing structures consistent with the observed
design matrix. This computes the alias matrix of the effect-coded main-effects model against the
omitted two-factor interactions, and reports the sensitivity of each main effect to them.
Offline, deterministic. No new data.
"""
import json
from pathlib import Path
from itertools import combinations
import numpy as np
import pandas as pd

PB = Path(__file__).resolve().parents[2]
G = json.load(open(PB / "config/grid_definition.json"))
specs = pd.DataFrame(G["specs"])
P = pd.read_parquet(PB / "data/panel/panel.parquet")
used = sorted(P[P.provider.isin(["openai", "google"])].spec_id.unique())
D = specs[specs.spec_id.isin(used)].reset_index(drop=True)
AX = [c for c in D.columns if c.startswith("A")]
print(f"  confirmatory design: {len(D)} specifications, axes {AX}")

def effect_code(df, cols):
    """effect (sum-to-zero) coding, the coding the design was optimised under"""
    blocks, names = [], []
    for c in cols:
        lv = sorted(df[c].unique())
        for l in lv[:-1]:
            v = np.where(df[c] == l, 1.0, np.where(df[c] == lv[-1], -1.0, 0.0))
            blocks.append(v); names.append(f"{c}={l}")
    return np.column_stack(blocks), names

Xm, mnames = effect_code(D, AX)
X = np.column_stack([np.ones(len(D)), Xm])
print(f"  main-effects model: {X.shape[1]} columns (intercept + {len(mnames)} contrasts)")

# omitted two-factor interaction columns
Zc, znames = [], []
for a, b in combinations(AX, 2):
    ia = [i for i, n in enumerate(mnames) if n.startswith(a + "=")]
    ib = [i for i, n in enumerate(mnames) if n.startswith(b + "=")]
    for i in ia:
        for j in ib:
            Zc.append(Xm[:, i] * Xm[:, j]); znames.append(f"{mnames[i]}*{mnames[j]}")
Z = np.column_stack(Zc)
print(f"  omitted two-factor interaction columns: {Z.shape[1]}")

# alias matrix A = (X'X)^-1 X'Z :  E[beta_hat] = beta + A gamma
A = np.linalg.pinv(X.T @ X) @ X.T @ Z
rows = {}
for i, n in enumerate(mnames):
    a = A[i + 1]                      # skip the intercept row
    rows[n] = {"l2_norm": float(np.linalg.norm(a)),
               "l1_norm": float(np.abs(a).sum()),
               "max_abs": float(np.abs(a).max()),
               "worst_partner": znames[int(np.argmax(np.abs(a)))]}
print("\n  alias sensitivity of each main-effect contrast to the omitted 2FIs:")
print("   %-28s %8s %8s %8s  %s" % ("contrast", "||a||_2", "||a||_1", "max|a|", "worst partner"))
for n, r in sorted(rows.items(), key=lambda kv: -kv[1]["l2_norm"]):
    print("   %-28s %8.3f %8.3f %8.3f  %s" % (n, r["l2_norm"], r["l1_norm"], r["max_abs"],
                                              r["worst_partner"]))

# is the provider-by-item interaction aliased? items are crossed with specs, so check directly
PC = P[P.provider.isin(["openai", "google"])]
ct = PC.groupby(["item_id", "spec_id"]).size()
crossed = len(ct) == PC.item_id.nunique() * PC.spec_id.nunique()
print(f"\n  item x specification crossing: {len(ct)} cells, "
      f"{PC.item_id.nunique()}x{PC.spec_id.nunique()} = "
      f"{PC.item_id.nunique()*PC.spec_id.nunique()}  -> fully crossed: {crossed}")

pres = [n for n in mnames if n.startswith("A7")]
out = {"_meta": {"n_specs": int(len(D)), "axes": AX,
                 "coding": "effect (sum-to-zero), as the design was optimised",
                 "n_main_contrasts": len(mnames), "n_omitted_2fi": int(Z.shape[1])},
       "alias_sensitivity": rows,
       "presentation_contrasts": pres,
       "presentation_l2": {n: round(rows[n]["l2_norm"], 4) for n in pres},
       "item_spec_fully_crossed": bool(crossed),
       "provider_by_item_identified": bool(crossed),
       "reading": ("E[beta_hat] = beta + A gamma. A main effect's bias is bounded by "
                   "||a_j||_2 * ||gamma||_2 (Cauchy-Schwarz), so no finite bound exists without an "
                   "external constraint on the omitted interaction vector gamma; the design alone "
                   "does not supply one. The provider-by-item interaction is in a different "
                   "position: items are fully crossed with specifications, so it is orthogonal to "
                   "the specification-axis contrasts and is identified without assumption.")}
json.dump(out, open(PB / "results/results_r3_alias_bounds.json", "w"), indent=1)
print("\n  -> results/results_r3_alias_bounds.json")
