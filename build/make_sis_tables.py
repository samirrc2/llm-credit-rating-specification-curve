#!/usr/bin/env python3
"""Generate the bodies of Table 7 (baseline discrimination) and Table 8 (net benefit) from the
result JSONs, so no cell is hand-maintained. An earlier hand-typed Table 8 had three wrong cells.

Writes paper/tab_sisbase_body.tex and tab_sisdca_body.tex, which manuscript_full.tex \\input{}s.
"""
import json
from pathlib import Path
PB = Path(__file__).resolve().parents[1]
SB = json.load(open(PB / "results/results_r3_sis_baselines.json"))["by_resolution"]
FU = json.load(open(PB / "results/results_r2r3_followups.json"))["semantic_entropy_benchmark"]
DC = json.load(open(PB / "results/results_r3_decision_curve.json"))["by_resolution"]
HO = json.load(open(PB / "results/results_r3_heldout_issuer.json"))["by_resolution"]

ROWS = [("Instability index (Gini--Simpson)", "sis"),
        ("Discrete semantic (Shannon) entropy", "sem_entropy"),
        ("Number of dissenting elicitations", "dissent"),
        ("Self-consistency vote margin", "neg_margin"),
        ("Distance to IG/HY boundary", "neg_boundary_dist")]
RES = ["ighy", "band", "letter"]
f3 = lambda v: "---" if v is None else f"{v:.3f}"

# ---- Table 7
L = []
for lab, k in ROWS:
    L.append(lab + " & " + " & ".join(f3(FU[r]["auc"].get(k)) for r in RES) + r" \\")
L.append(r"\midrule")
L.append("Event base rate & " + " & ".join(f"{FU[r]['event_base_rate']:.2f}" for r in RES) + r" \\")
L.append("Spearman (index, dissent count) & "
         + " & ".join(f"{FU[r]['spearman_vs_dissent']['sis']:.3f}" for r in RES) + r" \\")
L.append("Spearman (entropy, dissent count) & "
         + " & ".join(f"{FU[r]['spearman_vs_dissent']['sem_entropy']:.3f}" for r in RES) + r" \\")
def d(r, key, ci=False):
    v = SB[r].get(key)
    if v is None:
        return "---"
    return (f"({v[0]:.3f},\\,{v[1]:.3f})" if ci else f"{v:.3f}")
L.append("AUC difference, index $-$ dissent count & "
         + " & ".join(d(r, "auc_diff_sis_minus_dissent") for r in RES) + r" \\")
L.append(r"\quad 95\% CI (issuer-clustered, 2{,}000 draws) & "
         + " & ".join(d(r, "auc_diff_ci95", ci=True) for r in RES) + r" \\")
L.append("AUC difference, entropy $-$ dissent count & "
         + " & ".join("---" if "auc_diff_sementropy_minus_dissent" not in FU[r]
                      else f"{FU[r]['auc_diff_sementropy_minus_dissent']:.3f}" for r in RES)
         + r" \\")
# held-out-ISSUER setting, reported separately rather than merged into the AUCs above
L.append(r"\midrule")
L.append(r"\emph{Profile-split subsampling (300 random splits of the 45 profiles)} & & & \\")
for lab, k in ROWS:
    L.append(r"\quad " + lab + " & "
             + " & ".join("---" if not HO[r].get("computable")
                          else f3(HO[r]["mean_auc"].get(k)) for r in RES) + r" \\")
L.append(r"\quad AUC difference, index $-$ dissent count & "
         + " & ".join("---" if not HO[r].get("computable")
                      else f"{HO[r]['auc_diff_sis_minus_dissent_mean']:.3f}" for r in RES)
         + r" \\")
L.append(r"\quad\quad maximum $|$difference$|$ across splits & "
         + " & ".join("---" if not HO[r].get("computable")
                      else f"{HO[r]['auc_diff_max_abs']:.3f}" for r in RES)
         + r" \\\bottomrule")
(PB / "paper").mkdir(parents=True, exist_ok=True)   # the capsule ships no manuscript tree; a generator makes its own output directory
(PB / "paper/tab_sisbase_body.tex").write_text("\n".join(L) + "\n", encoding="utf-8")

# ---- Table 8
COLS = ["0.10", "0.20", "0.30", "0.45", "0.60"]
ig = DC["ighy"]; nb = ig["net_benefit"]; nbf = FU["ighy"]["net_benefit"]
def row(lab, key):
    src = nb if key in nb else nbf
    return lab + " & " + " & ".join(f"{src[key][c]:.3f}" for c in COLS) + r" \\"
M = [row("Instability index (own best threshold)", "sis"),
     row("Discrete semantic (Shannon) entropy", "sem_entropy"),
     row("Number of dissenting elicitations", "dissent"),
     row("Self-consistency vote margin", "neg_margin"),
     row("Distance to IG/HY boundary", "neg_boundary_dist"),
     row("``Refer on any disagreement'' (fixed)", "any_disagreement"),
     r"\midrule",
     row("Refer all issuers", "flag_all"), row("Refer none", "flag_none"), r"\midrule",
     r"\multicolumn{6}{l}{\emph{Maximum absolute gap across the full $p_t$ grid, $0.05$--$0.60$:}} \\"]
for lab, key, src in [("index $-$ dissent count", "max_abs_gap_sis_vs_dissent", ig),
                      ("entropy $-$ dissent count", "max_abs_gap_sementropy_vs_dissent", FU["ighy"]),
                      ("index $-$ vote margin", "max_abs_gap_sis_vs_vote_margin", ig),
                      ("index $-$ boundary distance", "max_abs_gap_sis_vs_boundary_dist", ig),
                      ("attainable envelope $-$ ``any disagreement''",
                       "max_abs_gap_sis_vs_any_disagreement", ig)]:
    v = src[key]
    tail = r"$ (exact)} \\" if v == 0.0 else r"$} \\"
    M.append(r"\quad " + lab + r" & \multicolumn{5}{c}{$" + f"{v:.3f}" + tail)
M[-1] = M[-1].replace(r"\\", r"\\\bottomrule")
(PB / "paper/tab_sisdca_body.tex").write_text("\n".join(M) + "\n", encoding="utf-8")
print(f"   tab_sisbase_body.tex: {len(L)} lines;  tab_sisdca_body.tex: {len(M)} lines")
