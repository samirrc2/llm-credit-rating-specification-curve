# Manuscript edit log — cas-sc.tex (NLP major revision)

Backup of pre-revision manuscript: `paper/ISWA/cas-sc.PREREV.bak` (1061 lines).
Legend: ✅ done · ⬜ pending. Each row records the exact surgical change.

## A. Abstract
- ✅ A1 — REMOVE turnover + Pillar-1 capital sentence.
- ✅ A2 — EDIT permutation p=0.001 → 0.0005.
- ✅ A3 — EDIT flagship "no evidence…attenuates" → "does not detect attenuation" + reasoning-model clause.

## B. Introduction
- ✅ B1 — EDIT contribution (iii): drop turnover/spread/capital, keep boundary migration.
- ✅ B2 — EDIT add "elicitation reliability" framing (light).

## C. §3.1 + Fig 1 + Table 2
- ✅ C1 — EDIT residual "structured sensitivity" → descriptive/aliasing-aware.
- ✅ C2 — EDIT per-axis 4.6% qualified as descriptive.
- ✅ C3 — EDIT spec-curve text: label-recovery reframe (drop correct/incorrect).
- ✅ C4 — EDIT Fig 1 caption panel (a): design-label recovery.
- ✅ C5 — ADD aliasing diagnostics (0.054 / 0.354) to Table 2 note.

## D. §3.2 permutation
- ✅ D1 — EDIT rating-invariance null (2000 perms, spread 1.59, null SD 0.050, 0/2000, p=0.0005, η²=0.46).

## E. §3.4 resolutions
- ✅ E1 — ADD boundary-distance severity (ρ=−0.05, no monotonic association).

## F. §3.5 economics
- ✅ F1 — EDIT retitle → IG/HY migration; opening keeps only migration.
- ✅ F2 — REMOVE turnover + spread + capital + RCAP paragraphs.
- ✅ F3 — REMOVE turnover/spread/capital rows in tab:frag; permutation row → p=0.0005.

## G. §3.6 real-arm
- ✅ G1 — REMOVE TOST sentence.
- ✅ G2 — ADD external-benchmark spec curve (42.2–61.1%, perm p=0.021).
- ✅ G3 — ADD Z″-invariance + scale-sensitivity + confound caveat.
- ✅ G4 — REMOVE TOST row in tab:realarm; interpretation → descriptive.

## H. §3.7 tiers
- ✅ H1 — EDIT "no evidence…attenuates" → "do not detect attenuation" + CI/absence-of-evidence.

## I. NEW §3.9 reasoning arm
- ✅ I1 — ADD reasoning-architecture subsection.
- ✅ I2 — ADD reasoning results table.

## J. §4 SIS
- ✅ J1 — EDIT τ=0.08 discreteness + precision/recall + 67%→33% referral.
- ✅ J2 — EDIT Algorithm 1 note: k-dependence + continuous-score use.

## K. Discussion/Limitations/Conclusion
- ✅ K1 — EDIT residual wording (mirror C1).
- ✅ K2 — REMOVE spread/capital limitation sentence.
- ✅ K3 — EDIT "not an artifact of model scale" → does-not-detect + reasoning arm.
- ✅ K4 — EDIT conclusion: case-study/conditional clause.

## L. Methods
- ✅ L1 — EDIT directional items "used only for turnover" → not analyzed.
- ✅ L2 — EDIT permutation Methods → rating-invariance null.
- ✅ L3 — REMOVE TOST Methods sentence.
- ✅ L4 — REMOVE Economic-translation Methods subsection.
- ✅ L5 — ADD DeepSeek-R1 row to tab:models + provenance footnote.
- ✅ L6 — ADD Methods note for new offline analyses.

## M. Data availability
- ✅ M1 — REMOVE "Basel capital map" from materials list.
- ✅ M2 — ADD reasoning arm + MANIFEST_REASONING.

---
## Status: ALL EDITS IMPLEMENTED ✅
- Compiled clean: **22 pages, 0 undefined refs/citations, 0 errors**, bibtex clean.
- Source: `paper/ISWA/cas-sc.tex` (1061 → 1116 lines; +55 net, driven by the reasoning subsection/table and the added analyses, offset by economics removal).
- Backup of original: `paper/ISWA/cas-sc.PREREV.bak`.
- Revised PDF staged: `paper/ISWA/NLP_submission/cas-sc-revised.pdf`; response at `NLP_submission/RESPONSE_TO_REVIEWERS.pdf`.
- Removed cleanly: economics translations (turnover/spread/Pillar-1/RCAP), TOST (both), 53.5%, $45bn, p=0.179, 999-perm.
- Verified present: p=0.0005, reasoning 25.5% + deepseek-r1 + MANIFEST_REASONING, design-label recovery, aliasing 0.354, issuer-preserving perm, external curve 42.2–61.1%, τ any-disagreement rule, "do not detect attenuation".

---
## Round 2 — consistency sweep (constructed-label "accuracy" / persist / external-validity)
- ✅ Figure 1 regenerated (make_figures.py labels): "(a) design-label recovery", "design-label recovery vs Altman Z'' strata", "majority threshold (0.5)" — old benchmark-referenced/majority-correct/accuracy removed. Verified by rendering the PNG.
- ✅ §3.2 "majority-accuracy threshold" → "majority label-recovery threshold"; "benchmark-consistent credit-band accuracy" → "consistency with the constructed credit-band labels".
- ✅ tab:frag "Credit-band accuracy range" → "Design-label recovery range".
- ✅ Flagship prose + tab:tier "Band accuracy vs. Altman" → "Design-label recovery vs. Altman"; "not more accurate" → "do not recover the constructed labels more often".
- ✅ Discussion: deleted "qualitative pattern persists" sentence → illustrative descriptive check + no equivalence.
- ✅ Abstract "instability persists on 31" → "Specification variation is also observed in 31".
- ✅ Intro "(iv) test external validity" → "explore external validity descriptively".
- ✅ §3.6 "substantial specification instability remains observable" → "specification variation is also observed".
- ✅ Limitations "checks external validity"→"explores external validity descriptively"; removed "lacks power to detect the pre-specified equivalence margin" (TOST remnant) → "WATCH-stratum sample is small; quantitative equivalence not established".
- ✅ Conclusion "robust across … the decontaminated real-firm arm" → "…and is further illustrated descriptively by the real-firm arm".
- ✅ Abstract + Highlights "no axis >5%" → qualified "Under a descriptive main-effects decomposition, no axis exceeds ~5%".
- ✅ Supplementary Table S1 created (variance-range R²=0.083/0.119/0.101) → NLP_submission/supplementary_variance_range.pdf.
- Recompiled: main 22 pages clean (0 undefined); residual flagged-terms grep = 0.
- NLP_submission now holds: cas-sc-revised.pdf, RESPONSE_TO_REVIEWERS.pdf, supplementary_variance_range.pdf.

---
## Round 3 — clustering terminology + §3.6 title
- ✅ Clustering split: synthetic-battery CIs relabelled profile-clustered (Table 1/var, tab:frag, tab:tier, SIS-battery validation, Limitations, Methods main bootstrap = 6 occurrences); issuer-clustered retained ONLY for the 3 real-issuer instances (tab:realarm, SIS real validation, Methods real comparison).
- ✅ §3.6 title "Robustness on decontaminated real issuers" → "Illustrative check on decontaminated real issuers"; "before using real issuers as a robustness sample" → "as a descriptive external check".
- Recompiled clean: 22 pages, 0 undefined refs; cas-sc-revised.pdf restaged.
- Supplementary Table S1 (R²=0.083/0.119/0.101) present as separate file: NLP_submission/supplementary_variance_range.pdf — MUST be uploaded to Elsevier as "Supplementary Material".
