# Manuscript change-list — NLP-D-26-00451 major revision

Planning document only (no manuscript edits made yet). Each row is a concrete edit to `paper/NLP/cas-sc.tex`, keyed to the reviewer point it answers, with the exact number/source to insert. Status: **PENDING** until the reasoning run finishes and we edit the doc. All offline numbers below were re-verified against the regenerated `results/*.json` on 2026-09-06 (zero drift).

Decision on venue: **stay at the NLP journal** (major revision, not reject). We do NOT retarget. R2's "retarget to quant-finance" is declined in the response letter, and the NLP relevance is strengthened editorially instead.

---

## R3-1 — Circularity: profiles built to Altman strata, then scored against those strata (Fig 1)

Chosen option: **(b) reframe as design-label recovery**, plus point to the independent real-firm arm as the external check.

- §3 / Fig 1 caption: replace "benchmark-referenced / majority-correct / accuracy" language with "design-label recovery" / "consistency with the constructed strata." The 56/44 split is a *diagnostic of label recovery*, not a neutral accuracy diagnostic.
- **Add the external-benchmark specification curve** (closes R3-1's explicit second ask): new figure/subsection showing per-specification band accuracy of the 31 real issuers vs their **disclosed agency ratings** (external, not used in profile construction). Numbers (from `analysis/realarm_speccurve.py`, wired into reproduce.sh): range **42.2%–61.1%** across the 12 specs, **18.9pp** spread, mean **53.7%**, issuer-clustered 95% CI **[0.41, 0.66]**. State that specification sensitivity persists against a truly external reference.
- Keep the real-issuer arm (31 decontaminated issuers) and present it descriptively (see R3-4).
- Add one sentence: the instability finding does not depend on the benchmark at all — the IG/HY flip (25.2%) is a *within-model agreement* measure computed without any external label. This is the benchmark-free panel already in Fig 1.
- Global find/replace audit for the words "correct," "accuracy," "benchmark-referenced" outside the explicitly-labelled recovery context.

## R3-2 — D-optimal design resolution-limited; variance components not identified

Chosen option: **(b) descriptive partitions — implemented aggressively.** The ANOVA is demoted to a descriptive summary; the model-free flip/agreement/permutation/score results carry the paper.

- §3.1 / Table 1: relabel the decomposition as "descriptive variance partitions under the assumed main-effects model," NOT causal attributions.
- **Remove the inferential confidence intervals from the individual per-axis variance shares** in Table 1. Report per-axis magnitudes (answer presentation ≈4.6%, etc.) without the precise-looking intervals the reviewer flagged.
- Insert aliasing diagnostics from the frozen design (`results_revision.json` → `R3_2.aliasing_diagnostics`): main-effect max off-diagonal corr **0.054**; main×2FI max abs corr **0.354**. State: main effects mutually near-orthogonal; only low-alias two-factor interactions estimable.
- Reframe the "~25% residual" claim: descriptive residual under the main-effects model, may contain aliased interaction variance; drop "most residual variation is structured sensitivity."
- Add an explicit sentence in §3.1 that none of the paper's conclusions depends on the decomposition — the headline flip (25.2%), cross-spec agreement, permutation test, and instability score are model-free and assume no orthogonality.
- Add a supplementary robustness table (the "range of variance explained by different model specifications" R3 asked for): main-effects R²=0.083; main+2-way in-sample R²=0.119; regularized 2-way issuer-out-of-sample R²=0.101 (`analysis/variance_model_range.py`). One line: the shifting decomposition illustrates why individual-axis attribution is not identified; all specs remain small.
- (Bayesian hierarchical re-fit NOT pursued; the aggressive descriptive demotion is the chosen route and the letter does not offer the hierarchical model conditionally.)

## R3-3 — Permutation test used the wrong null

**DONE (offline).** Re-ran with the rating-invariance null (permute specification assignments across profiles, not accuracy labels).

- §3.2: replace the old permutation description with the rating-invariance null (permute spec assignments; statistic = between-spec SD of item-centred rating) on the deterministic Google temp-0 subgrid: observed spread **1.59 notches**, null mean 0.18 / **SD 0.050**, **0/2000** exceed, **p = 0.0005**, specification η² (item-centred) = **0.46**. Add: this test runs on the temp-0-honoured subgrid (satisfies reviewer's closing condition); and note η² is a spec-level-aggregate quantity, not comparable to Table 1's individual-rating partition. (Numbers from `analysis/permtest_and_tau.py`; the earlier 0.96 figure was NOT reproducible and has been replaced.)
- §4.2 (SIS): report τ = **0.08** (Youden's J on held-out split), precision **1.00**, recall **0.88**; ROC CIs 0.94 [0.86–0.99] and 0.70 [0.51–0.87]. Source: `analysis/permtest_and_tau.py`, `results_extended.json`.
- Update the abstract's permutation mention accordingly (currently "p=0.001").

## R3-4 — Decontamination ad hoc; scaling not neutral; TOST misspecified/underpowered

Chosen option: **(b) drop TOST, present real-firm results descriptively**, and add the invariance proof + sensitivity the reviewer asks for.

- Remove the TOST equivalence test and any "qualitatively persist / equivalent" claim. Present the 31-issuer arm descriptively with sample-size caveats.
- Rebut the "scaling not neutral" concern with the proof: uniform per-issuer dollar scaling (LogUniform[0.6,1.7]) preserves every ratio, so Altman Z″ is invariant. Insert: Z″ correlation transformed-vs-original = **1.000000**, **100%** stratum retention (SAFE/WATCH/DISTRESS unchanged). Source: `sealed_crosswalk.json` real_figures + `build_battery_realarm.py` (uniform scaling).
- Distinguish two claims: (i) Z″ is invariant to the uniform scaling *by construction* (analytic); (ii) the LLM also sees absolute dollars, so scale-insensitivity of the *model output* must be shown empirically. Report the empirical check (`analysis/realarm_scale_sensitivity.py`, wired into reproduce.sh): the applied per-issuer scale factors span 0.60–1.66; instability vs scale Spearman **−0.035** (perm p **0.85**), rating level vs scale **−0.019** (mean rank) / **+0.019** (IG-rate) → no material sensitivity to absolute scale within the range. Do NOT claim invariance of LLM output "by construction."
- Acknowledge the fingerprint test is exact-figure only; soften the identification claim to "exact-figure lookup" rather than broad inference.

## R3-5 — SIS validated on same data; no out-of-sample framework; tau unspecified

**DONE (offline).** Proper held-out framework already computed.

- §4.2: report held-out-specification cross-validation — score fit on 16 calibration specs, evaluated on the disjoint 16 validation specs: ROC-AUC **0.94** (issuer-clustered bootstrap CI), repeated-split median AUC **0.88** over 300 balanced splits, avg precision **0.98**, base rate 0.76.
- Real-issuer external validation: ROC-AUC **0.70** on 31 decontaminated issuers (add the CI, base rate 0.61).
- Add tau-calibration: state the operating threshold and how performance varies with tau (already computed).
- Report out-of-model transfer **honestly**: weak (Spearman ~0.19, AUC ~0.50). Do NOT claim cross-model generalization; state the score is per-model/per-grid and must be recalibrated.
- Reframe SIS vs Gini-Simpson (also answers R2-E): SIS is the *operationalization + validated deployment control*, not a claim of a new dispersion index. Credit Gini-Simpson explicitly.

## R3-6 — Economic translations post-hoc/arbitrary; capital illustration misleading

Chosen option: **(a) remove entirely.** Low upside / high risk, not the paper's contribution, and the reviewer explicitly permits deletion.

- **Delete** the portfolio-turnover, spread-range, Cornaggia anchor, Pillar-1 Basel capital illustration, and the RCAP comparison from §3.5 and from the abstract/introduction. No supplementary version retained.
- The offline numbers we computed for these (turnover recast, capital IQR/median 0.217, etc.) are NOT used in the manuscript; they remain in `results_revision.json` only as internal record.
- Response-letter line: "We agree. All spread, turnover and regulatory-capital translations have been removed. The revised paper focuses on the empirically identified specification-instability quantities."
- Q4 becomes moot (no Basel mapping remains).

## R3-7 — Over-general framing; flagship "no attenuation" = absence of evidence; test when instability is most severe

Chosen option: **reframe as a case study** of specification sensitivity in the evaluated systems.

- Abstract/intro/conclusion: emphasize conditional nature — findings are for the evaluated models and grid; SIS characterizes that sensitivity. Soften "no evidence it attenuates on flagship models" to explicitly flag the wide CI (−1.1%, 95% CI −7.6 to +6.0) and the two-model/12-spec scope; state it as "does not detect attenuation" not "shows none."
- Add severity stratification (already computed):
  - By Z″ stratum (`results_extended.json` B6): SAFE flip **13.0%**, WATCH **35.5%**, DISTRESS **27.1%** — instability is worst mid-scale (WATCH).
  - By distance from IG/HY boundary (`results_revision.json` R3_7): Spearman(flip, |Z″−2.60|) = **−0.05** → instability is *pervasive*, not just a near-boundary artifact (honest null; report as such).
- Keep flagship tier table (§3.7) but under the case-study framing; all its numbers verified consistent.

## R2-F / R2-B — reasoning architectures + issuer expansion

- **Reasoning arm (DeepSeek-R1, native CoT)** — DONE, frozen (1620/1620, SHA-256 manifest MANIFEST_REASONING.sha256). Add a "reasoning-architecture robustness" subsection reporting: reasoning-tier IG/HY flip **25.5%** (95% CI 20.9–30.1%) vs nano/flash 24.7% and flagship 23.6%; paired reasoning−nano/flash diff **+0.9pp** (95% CI −7.0 to +8.8, indistinguishable from zero); reasoning band accuracy vs Altman **55.5%**; reasoning IG rate **31.4%** (far more conservative than flagship's 79.9%, yet no more stable). Conclusion: explicit chain-of-thought does NOT remove the elicitation sensitivity; it persists across model family/architecture. Answers R2's "evaluate modern reasoning architectures / CoT" and adds a third model family + reasoning architecture (open-weight). Source: `results_reasoning.json`.
- Issuer expansion (N=31 → more): optional Tier-3 (~$2, heavy build). Not committed. If not done, defend N in the letter via issuer-clustered bootstrap (already used) and the descriptive reframing.

## R2-A / R2-G — NLP-venue relevance

- Frame the core contribution as **LLM elicitation reliability**: whether an LLM's categorical judgment stays stable under defensible changes to the linguistic and procedural specification while the substantive input is held fixed. (Avoid "purely a language phenomenon" — the grid also varies model/temperature, so a hostile reviewer could attack that.) Position as an NLP evaluation-methodology contribution with the SIS as a reusable tool. Decline retargeting on the merits.

## R2-B — sample size / estimand (statistical safety)

- State plainly: independent underlying profiles = 45 (controlled) and 31 (real). The design estimates **within-profile specification sensitivity**, not population prevalence; repeated elicitation conditions give dense paired measurement of that estimand; uncertainty clustered at the profile/issuer level.
- Add an explicit sentence that the 8,640 elicitation cells are **not** treated as independent observations; all CIs are issuer-clustered. (Do NOT claim the cell is the unit of inference — that is attackable.)

---

## Additional manuscript tasks (reviewer-letter round 2)
- **Reasoning arm provenance + accurate description:** the arm runs ALL 12 specs on ONE model (provider axis held constant) — do NOT describe it as the two-provider grid; state provider is constant and cross-provider variation (largest gap, §3.3) is absent. Add a dedicated reasoning results table AND a new row in the model-snapshots table (`tab:models`) — do NOT call it "Table 7" (that number collides / shifts; use \ref). MANIFEST_REASONING entry, post-hoc label, DAS line (DeepSeek-R1 via OpenRouter API, queried 2026-09-06, SHA-256 frozen). Seed/temperature are OpenRouter request parameters, not self-hosted determinism — note this.
- **Algorithm 1 flag rate:** report the referral volume — SIS-only rule fires on ~67% of issuers; the near-boundary conjunction (Algorithm 1) cuts it to ~33%. State the post-conjunction rate in the deployment section.
- **Directional items / contribution (iii) / abstract counts:** turnover removal (R3-6) orphans the 45 directional items and introduction contribution (iii); the abstract's "8,640 elicitations, 4,320 on credit-health" now leaves the other 4,320 (directional) unexplained. Revise the introduction to drop/replace contribution (iii), and either repurpose or remove the directional-items material + fix the abstract counts so nothing dangles.
- **Real-arm external-benchmark curve:** present descriptively; the between-spec spread is NOT distinguishable from sampling noise at n=31 (within-arm permutation p=0.46). Do not claim it establishes external-benchmark sensitivity; lead with the benchmark-free within-model flip.
- **SIS threshold (Algorithm 1):** state the k=16 discreteness; τ=0.08 = "flag any disagreement" rule; note k-dependence (k≈9 deployment → smallest non-zero SIS 0.198); present threshold as descriptive.
- **§4.2 wording:** make explicit that "external" validation = external issuers (6/6 spec split), not external specifications.
- **Scale sensitivity:** state the one-draw-per-issuer confound (scale vs issuer identity) and flag within-issuer re-elicitation as the clean test; within-support only.
- **η² reconciliation:** in §3.2 present the permutation spread (1.59 notches) and η² (0.46) as two summaries of the same item-centred-rating object; note non-comparability to Table 1.

## Final manuscript–rebuttal synchronization audit (before submission)
Grep the revised manuscript to confirm every rebuttal promise is actually reflected, and that old terms/numbers are gone:
- No "TOST"/"equivalence"/"qualitatively persist"; no "turnover"/"Cornaggia"/"Basel"/"RCAP"/"Pillar-1"/"capital"; no "$0.57 billion".
- Altman described as a construction/stratification reference, not external ground truth; no "benchmark-referenced"/"majority-correct"/"accuracy" implying external validity.
- Variance decomposition descriptive-only; per-axis CIs removed from Table 1; aliasing 0.054/0.354 present.
- Permutation reported as rating-invariance null (η²=0.46, p=0.0005, 0/2000); no η²=0.96, no p=0.001/999.
- DeepSeek-R1 arm present (25.5%, three axes, provider held constant, post-hoc, manifest, DAS); real-arm external-benchmark curve with issuer-preserving permutation p=0.021.
- SIS τ reframed (any-disagreement rule, ~67%→~33% post-conjunction); "computed on" not "fit on".
- Softened flagship ("does not detect attenuation") and boundary ("no monotonic association") wording.

## Build/verify checklist after edits
1. Recompile `cas-sc.tex` → 0 undefined refs/cites.
2. Re-run `reproduce.sh` → all results regenerate incl. reasoning arm.
3. Re-verify every number in the manuscript against `results/*.json` (this pass found zero drift; repeat after edits).
4. Rebuild `.docx`, blinded manuscript, and refresh anonymized capsule.
5. Commit with paper title as message; user pushes on Mac.
