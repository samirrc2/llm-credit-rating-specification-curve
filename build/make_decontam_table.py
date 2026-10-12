#!/usr/bin/env python3
"""Generate Table 9 (decontamination experiments) from results_r3_decontam.json."""
import json
from pathlib import Path
PB = Path(__file__).resolve().parents[1]
D = json.load(open(PB / "results/results_r3_decontam.json"))
A = D["experiment_A_ratio_identification"]; AD = D["experiment_A_decision"]
B = D["experiment_B_scale_sensitivity"]; BD = D["experiment_B_decision"]
ci = lambda c: f"({c[0]:.3f},\\,{c[1]:.3f})"
L = [r"\emph{Experiment A: can the ratio pattern identify the issuer?} & & & \\",
     f"\\quad Open-ended (``name the company'') & {A['A1']['n_calls']} & "
     f"{A['A1']['top1_rate']:.3f} & {ci(A['A1']['top1_ci95'])} " r"\\",
     f"\\quad Closed-set, 31 candidates & {A['A2']['n_calls']} & "
     f"{A['A2']['top1_rate']:.3f} & {ci(A['A2']['top1_ci95'])} " r"\\",
     f"\\quad\\quad chance ($1/31$) & --- & {A['A2']['chance_rate']:.3f} & --- " r"\\",
     f"\\quad\\quad exact binomial vs chance & --- & "
     f"$p={A['A2']['binom_p_one_sided_vs_chance']:.1e}$ & --- " r"\\",
     f"\\quad\\quad issuers identified at least once & --- & "
     f"{A['A2']['issuers_ever_identified']}/{A['A2']['n_issuers']} & --- " r"\\",
     r"\quad\quad issuers identified in every ordering & --- & 0/31 & --- \\",
     f"\\quad Exact-figure fingerprint gate (Section~\\ref{{sec:realarm}}) & --- & 0.029 & --- " r"\\",
     r"\midrule",
     r"\emph{Experiment B: does absolute scale move the rating within issuer?} & & & \\"]
for a, b in (("0.6", "1.7"), ("0.6", "1.0"), ("1.0", "1.7")):
    k = f"ighy_change_{a}_vs_{b}"
    if k in B:
        r = B[k]
        L.append(f"\\quad IG/HY class differs, scale {a} vs {b} & {r['n_pairs']} & "
                 f"{r['rate']:.3f} & {ci(r['ci95'])} " r"\\")
P = B["permutation"]
L += [f"\\quad\\quad permutation null mean & {P['n_cells']} & {P['null_mean']:.3f} & --- " r"\\",
      f"\\quad\\quad within-issuer permutation test & --- & $p={P['p_two_sided']:.3f}$ & --- "
      r"\\\bottomrule"]
(PB / "paper/NLP/tab_decontam_body.tex").write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"   tab_decontam_body.tex: {len(L)} lines")
print(f"   A decision: passes={AD['passes']}")
print(f"   B decision: rejects={BD['rejects_at_0.05']}")
