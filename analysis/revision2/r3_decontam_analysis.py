#!/usr/bin/env python3
"""Score the two decontamination experiments. Reviewer 3, Concern 2.

Reads the FROZEN arm (data/frozen/realarm_decontam/), verifying its manifest first, so the
analysis cannot silently run on a half-collected or edited run. Decision rules are those fixed in
analysis/revision2/SPEC_r3_realarm_experiments.md before any call was made; they are applied here
mechanically, including the branch that demotes the real-issuer arm.

Scoring key (sealed_scoring_key.json) is opened HERE and never entered a prompt for Experiment A1.
For A2 the candidate names are necessarily in the prompt -- that is the closed-set design, and it
makes A2 an upper bound on identifiability rather than a realistic leakage estimate.
"""
import json, re, sys
from collections import Counter
from pathlib import Path
import numpy as np

PB = Path(__file__).resolve().parents[2]
FROZ = PB / "data/frozen/realarm_decontam"
rng = np.random.default_rng(42)

# ---- refuse to score an unverified arm
sys.path.insert(0, str(PB / "capture"))
import freeze_decontam as FD
if not (FROZ / "MANIFEST.json").exists():
    print("NOT CHECKABLE: the arm is not frozen yet; run capture/freeze_decontam.py"); sys.exit(2)
rows, root = FD.manifest_for(FROZ)
MF = json.load(open(FROZ / "MANIFEST.json"))
if root != MF["root_sha256"]:
    print(f"REFUSING: frozen arm does not match its manifest\n  manifest {MF['root_sha256']}\n"
          f"  actual   {root}"); sys.exit(1)
print(f"  frozen arm verified: {MF['n_files']} files, root {root[:16]}")
print(f"  spec {MF.get('spec')} sha {str(MF.get('spec_sha256'))[:16]}")

CALLS = [json.loads(p.read_text()) for p in sorted((FROZ / "raw").glob("*.json"))]
SEALED = {r["item_id"]: r for r in json.load(
    open(PB / "data/frozen/realarm/sealed_scoring_key.json"))["key"]}
RS = json.load(open(PB / "data/frozen/main/rating_scale.json"))
LETTERS = RS["letter_scale"]; LRANK = {l: i for i, l in enumerate(LETTERS)}
IGHY = RS["letter_to_ig_hy"]; BAND = RS["letter_to_band"]
out = {"_meta": {"frozen_root_sha256": root, "spec_sha256": MF.get("spec_sha256"),
                 "n_calls": len(CALLS), "bootstrap": "issuer-clustered, 2000 draws, seed 42"}}

# ================= Experiment A =================
STOP = {"corp", "corporation", "inc", "co", "company", "the", "holdings", "group", "ltd", "plc",
        "llc", "international", "industries", "and", "technologies", "technology", "de"}
norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
def hit(resp, iid):
    k = SEALED[iid]; r = norm(resp)
    tk = k["ticker"].lower()
    if k["ticker"].isalpha() and len(tk) >= 2 and re.search(rf"(?<![a-z0-9]){re.escape(tk)}(?![a-z0-9])", r):
        return True
    toks = [t for t in norm(k["entity_name"]).split() if t not in STOP and len(t) > 2]
    return bool(toks) and all(t in r for t in toks)

def boot_rate(per_issuer):
    """Issuer-clustered bootstrap of a rate. Unit = issuer, as pre-registered."""
    ids = list(per_issuer)
    if not ids:
        return None, [None, None]
    est = float(np.mean([np.mean(per_issuer[i]) for i in ids]))
    draws = []
    for _ in range(2000):
        s = rng.choice(len(ids), len(ids), replace=True)
        draws.append(np.mean([np.mean(per_issuer[ids[j]]) for j in s]))
    return round(est, 4), [round(float(np.percentile(draws, 2.5)), 4),
                           round(float(np.percentile(draws, 97.5)), 4)]

A = {}
for exp in ("A1", "A2"):
    sub = [c for c in CALLS if c["experiment"] == exp and c.get("ok")]
    if not sub:
        A[exp] = {"n_calls": 0, "computable": False}; continue
    per = {}
    for c in sub:
        per.setdefault(c["item_id"], []).append(1.0 if hit(c["raw_response"], c["item_id"]) else 0.0)
    rate, ci = boot_rate(per)
    unk = np.mean([1.0 if re.search(r"\bunknown\b", (c["raw_response"] or "").lower()) else 0.0
                   for c in sub])
    entry = {"n_calls": len(sub), "n_issuers": len(per), "top1_rate": rate, "top1_ci95": ci,
             "unknown_rate": round(float(unk), 4),
             "issuers_ever_identified": int(sum(1 for i in per if max(per[i]) > 0))}
    if exp == "A2":
        k = int(sum(sum(v) for v in per.values())); n = len(sub); p0 = 1.0 / len(per)
        # exact one-sided binomial test against chance 1/31
        from math import comb
        pv = sum(comb(n, x) * p0 ** x * (1 - p0) ** (n - x) for x in range(k, n + 1))
        entry.update({"chance_rate": round(p0, 4), "successes": k, "trials": n,
                      "binom_p_one_sided_vs_chance": float(f"{pv:.3e}")})
    A[exp] = entry
    print(f"\n  == {exp}: {len(sub)} calls, {len(per)} issuers")
    print(f"     top-1 identification {rate}  CI {ci}   UNKNOWN rate {unk:.3f}")
    if exp == "A2":
        print(f"     chance 1/{len(per)} = {entry['chance_rate']}  exact binomial p = "
              f"{entry['binom_p_one_sided_vs_chance']}")
out["experiment_A_ratio_identification"] = A

# pre-registered decision rule for A (applies to the closed-set arm)
PREREG_THRESHOLD = 0.05
a2 = A.get("A2", {})
if a2.get("top1_rate") is not None:
    passes = (a2["binom_p_one_sided_vs_chance"] >= 0.05) and (a2["top1_ci95"][1] < PREREG_THRESHOLD)
    out["experiment_A_decision"] = {
        "rule": "not significantly above 1/31 AND bootstrap upper bound < 0.05",
        "binom_p": a2["binom_p_one_sided_vs_chance"], "ci_upper": a2["top1_ci95"][1],
        "threshold": PREREG_THRESHOLD, "passes": bool(passes),
        "verdict": ("no residual ratio-pattern identification detected" if passes else
                    "RESIDUAL IDENTIFICATION DETECTED -- the pre-registered fallback applies: "
                    "the real-issuer arm is demoted to an illustrative descriptive limitation")}
    print(f"\n  PRE-REGISTERED DECISION (A): {out['experiment_A_decision']['verdict']}")

# ================= Experiment B =================
def parse_letter(txt):
    t = (txt or "").upper()
    m = re.search(r'"RATING"\s*:\s*"([A-Z+\-]{1,4})"', t) or re.search(
        r"\b(AAA|AA[+-]?|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?|CCC[+-]?|CC|C)\b", t)
    if not m:
        return None
    L = m.group(1)
    return L if L in LRANK else None

B = [c for c in CALLS if c["experiment"] == "B" and c.get("ok")]
if B:
    recs = []
    for c in B:
        L = parse_letter(c["raw_response"])
        if L:
            recs.append({"item": c["item_id"], "spec": c["spec_id"], "scale": float(c["scale"]),
                         "letter": L, "ighy": IGHY.get(L), "band": BAND.get(L)})
    import pandas as pd
    D = pd.DataFrame(recs)
    print(f"\n  == B: {len(B)} calls, {len(D)} parsed ({100*len(D)/max(1,len(B)):.1f}%), "
          f"{D.item.nunique()} issuers, {D.spec.nunique()} specs")
    # paired: for each (item, spec) compare scale 0.6 vs 1.7
    piv = D.pivot_table(index=["item", "spec"], columns="scale", values="ighy",
                        aggfunc="first")
    def pair_rate(col_a, col_b, piv):
        both = piv.dropna(subset=[col_a, col_b])
        return both, float((both[col_a] != both[col_b]).mean()) if len(both) else None
    res = {}
    for a, b in ((0.6, 1.7), (0.6, 1.0), (1.0, 1.7)):
        if a in piv.columns and b in piv.columns:
            both, r = pair_rate(a, b, piv)
            per = {}
            for (it, sp), row in both.iterrows():
                per.setdefault(it, []).append(1.0 if row[a] != row[b] else 0.0)
            est, ci = boot_rate(per)
            res[f"ighy_change_{a}_vs_{b}"] = {"n_pairs": int(len(both)), "rate": est, "ci95": ci}
            print(f"     IG/HY class differs, scale {a} vs {b}: {est}  CI {ci}  (n={len(both)} pairs)")
    # within-issuer permutation test: scale labels exchangeable within (item, spec)
    obs = res.get("ighy_change_0.6_vs_1.7", {}).get("rate")
    if obs is not None:
        cells = [g for _, g in D.groupby(["item", "spec"]) if g.scale.nunique() == 3]
        null = []
        for _ in range(10000):
            diff = 0; tot = 0
            for g in cells:
                v = g.ighy.values.copy(); rng.shuffle(v)
                diff += int(v[0] != v[2]); tot += 1
            null.append(diff / max(1, tot))
        null = np.array(null)
        pval = float((np.abs(null - null.mean()) >= abs(obs - null.mean())).mean())
        res["permutation"] = {"n_cells": len(cells), "observed_rate": obs,
                              "null_mean": round(float(null.mean()), 4),
                              "p_two_sided": round(pval, 4), "n_perm": 10000}
        print(f"     within-issuer permutation: observed {obs:.4f} vs null mean "
              f"{null.mean():.4f}, p = {pval:.4f} (10,000 perms, {len(cells)} cells)")
        out["experiment_B_decision"] = {
            "rule": "permutation test on exchangeable scale labels within (issuer, specification)",
            "p_two_sided": round(pval, 4), "rejects_at_0.05": bool(pval < 0.05),
            "verdict": ("absolute scale does not materially move the rating within issuer; the "
                        "earlier between-issuer correlation is replaced by a properly paired null"
                        if pval >= 0.05 else
                        "SCALE ITSELF MOVES RATINGS -- the perturbation is not innocuous and the "
                        "pre-registered fallback applies")}
        print(f"\n  PRE-REGISTERED DECISION (B): {out['experiment_B_decision']['verdict']}")
    out["experiment_B_scale_sensitivity"] = res

json.dump(out, open(PB / "results/results_r3_decontam.json", "w"), indent=1)
print(f"\n  -> results/results_r3_decontam.json")
