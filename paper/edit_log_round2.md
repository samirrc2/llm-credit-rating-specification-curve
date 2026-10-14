# Revision 2 edit log — cas-sc.tex

Backup of the revision-1 manuscript: `paper/NLP/cas-sc.REV1.bak`.
Manuscript after these edits: **24 pages, 0 undefined references, 1 overfull box**
(pre-existing at line 65; the revision-1 manuscript had 3, so two were removed).
Response letter: **6 pages, 0 undefined, 0 overfull**, IEEE format per Paper 1, editor
cover page omitted as instructed.

## New computations (all offline, deterministic, no new model calls)

| script | output | purpose |
|---|---|---|
| `analysis/revision2/r2_chance_baseline.py` | `results/results_r2_chance_baseline.json` | R2.4 — marginal-matching chance baseline |
| `analysis/revision2/r3_sis_baselines.py` | `results/results_r3_sis_baselines.json` | R3.3 — SIS against simple baselines |
| `analysis/revision2/r3_alias_bounds.py` | `results/results_r3_alias_bounds.json` | R3.1 + direct question — alias algebra |

## Reviewer 2

- **R2.1 — Algorithm 1 near-boundary.** Real defect, not an ambiguity: `r̂` was the modal
  decision *class*, so `r̂ ∈ B` could not express proximity to a boundary between two classes.
  Algorithm 1 now carries letters alongside classes, takes the modal letter `ℓ̂` (line 7), and
  tests `|rank(ℓ̂) − b| ≤ w` (line 8). Inputs list `L`, `b`, `w` in place of `B`. Caption gives
  the reason and notes `w=1` reproduces the WATCH stratum.
- **R2.2 — pair sampling convention.** New Methods paragraph "Matched-pair disagreement: sampling
  convention": the statistic is `1 − Σp²`, the with-replacement pair-disagreement probability;
  draws may select the same cell; pairs may differ in specification, seed or both; the item is
  always fixed; `n = 96` per item; without-replacement variant is ×96/95, so 25.2% → 25.5%.
- **R2.3 — 4,320 vs 8,640.** Reconciled at the first mention of 8,640 in the Introduction, with a
  forward reference to Limitations (§5.2).
- **R2.4 — chance baseline. Changed a conclusion.** The ~33% was the uniform three-class value.
  The marginal-matching baseline is **48.9%** (machine SAFE 54.7% / WATCH 43.7%; agency 46.7% /
  53.3%). Observed 53.7% is an excess of **+4.9pp, 95% CI (−7.9, +17.1), κ = 0.095** — not
  distinguishable from chance. §3.6 and Table 4 now report this and withdraw the accuracy
  implication. The within-issuer specification spread (42.2–61.1%, perm p = 0.021) is unaffected.

## Reviewer 3

- **R3.1 — per-axis variance. Claims removed.** Abstract, both highlight lists and §3.1 no longer
  state "no axis exceeds ~5%". They now state what is identified: the axes jointly explain
  R² 0.083–0.119. §3.1 says the per-axis entries of Table 1 are not a ranking and gives the reason.
  New Methods §6.2 "What the design identifies": `E[β̂] = β + Aγ`, `A = (X'X)⁻¹X'Z`,
  `|a_j'γ| ≤ ‖a_j‖‖γ‖`; 27 interaction contrasts; `‖a_j‖₂` from 0.68 to 1.04; presentation 0.878
  with worst partner version×few-shot at 0.484. **No finite bound follows from the design alone.**
  The provider×item interaction **is** identified (items fully crossed with specifications, all
  90×32 cells populated) and is reported as the one identified component (~1.4%).
- **R3.3 — SIS incremental value. Reframed.** New §4.3 "Benchmark against simple baselines" with
  Table 7. At the binary gate SIS = 2(m/k)(1−m/k) is strictly increasing in the dissent count, so
  the two are order-isomorphic and must have identical rank-based discrimination. Confirmed:
  AUC 0.936 for SIS, dissent count and vote margin alike; AUC difference 0.000, CI (0.000, 0.000);
  Spearman 1.000000. At 3 bands all three give 0.951. At letter resolution the exercise is vacuous
  (base rate 1.00). Boundary distance is a distinct, weaker signal (0.763 / 0.655). τ = 0.08 sits
  below the smallest non-zero score at k=16 (0.117), so the rule is exactly "flag any disagreement".
  "Validated" and "deployable" removed from the abstract and highlights; §4.1 and §4.2 rewritten.
  Semantic entropy and token-level confidence are **stated as not computable** — the frozen corpus
  holds no logprobs.
- **R3.2 — real-issuer external validity. NOT CLOSED; editor's direction requested.** The existing
  scale analysis is confirmed to be *between*-issuer (one draw per issuer; Spearman −0.035,
  p = 0.85), exactly the confound the reviewer names. The within-issuer multi-scale design and the
  ratios-only identification probe both require new model calls and cannot be run on the frozen
  corpus. A ratio-based identity classifier is degenerate here (31 issuers, one profile each). The
  response letter states the two routes — collect the new arm, or take the reviewer's permitted
  fallback and demote the arm — and asks the editor which is preferred.

## Carried over, not yet done

- The anonymized capsule still leaks `"New York, USA"` in `CITATION.cff`, `README.md` and
  `.zenodo.json` (given-names and ORCIDs were correctly scrubbed). Flagged in
  `revision/CAPSULE_ANON_FINDINGS.md` before revision 1 and still open.

---

## Second pass: response-letter rewrite and the three required actions it exposed

Triggered by a re-read of the referee text against the draft reply. Rewriting the letter to the
house style of Paper 2 (one fact per bullet) made three unaddressed required actions visible.

### R3 Concern #3 — the decision-curve analysis had not been run
The required action asks for "a decision-curve analysis or net-benefit analysis for triage,
showing whether SIS improves referral decisions over 'flag any disagreement', over distance to the
IG/HY boundary, and over self-consistency vote margins." The previous draft answered only the
discrimination half of the comment.

- Spec written and hashed BEFORE the computation, per the paper's standing rule:
  `analysis/revision2/SPEC_r3_decision_curve.md`,
  sha256 `9b4bb4f780a22d77f8d808c8b9b2792ac10c818291fc7c82664b73bfeebfd26f`
  (recorded in `results/SPEC_r3_decision_curve.sha256`).
- The spec states the expected result in advance, because it is algebraic: SIS is order-isomorphic
  to the dissent count at binary resolution, so the net-benefit curves MUST coincide exactly, and
  any gap is a bug in the script rather than a finding.
- `analysis/revision2/r3_decision_curve.py` -> `results/results_r3_decision_curve.json`.
  Deterministic, no RNG, no new elicitations.
- Result, as predicted: max |NB(SIS) - NB(dissent count)| = 0.000 exactly across the whole
  p_t grid 0.05-0.60, at both non-degenerate resolutions. Vote margin coincides exactly too.
  Boundary distance is dominated by up to 0.156. Letter resolution is degenerate (base rate 1.00).
- One non-null result, reported at its value: dispersion-based referral beats refer-all once
  referral is costly enough. Gain is 0.000 for p_t <= 0.20 (base rate 0.76 makes refer-all
  near-optimal), then rises to +0.278 at p_t = 0.60.
- Refinement worth stating: the fixed "refer on any disagreement" rule falls short of the
  attainable envelope by up to 0.167, because for p_t > 0.30 a threshold of more than one dissent
  is better. The working knob is the integer dissent count, not the continuous score.
- Threshold selection: the reviewer is right that tau was chosen and evaluated on the same split.
  That required action is conditional on incremental value, which does not hold, so nested CV
  would calibrate a parameter the paper no longer asks to do any work. Stated, not skipped.
- Wired into the manuscript as the subsection "Net benefit for triage" plus Table 8 (`tab:sisdca`).

**Fault injection (the assertion is non-vacuous).** The equality assertion in
`r3_decision_curve.py` was tested before being reported as passing:

| fault | assertion fires? |
|---|---|
| SIS + 0.03*(k%3) | NO — and this was MY error, not a passing gate: k is constant within a resolution, so this is a constant offset that preserves the ordering. Not a valid fault. |
| SIS + 0.5*(modal_n % 2) (modal_n varies across items, so the order genuinely breaks) | YES — gap 0.066667 |
| SIS sign inverted | YES — gap 0.277778 |
| net-benefit FP penalty sign flipped | NO — correctly out of scope: it perturbs both strategies equally, so equality is preserved. A value-binding gate catches it instead (0.6667 -> 0.8603). |

Result restored and confirmed byte-identical to the pre-fault JSON after each injection.

### R3 Concern #1 — two points in the comment had no answer, and the paper contradicted the reply
- The 0.333 diagnostic: answered. It is a pairwise correlation and understates the problem, since
  a main effect is aliased with a linear combination of all 27 omitted contrasts, not with its
  worst single partner. This is why the alias norm replaced it.
- "the paper's central interpretation ... depends in part on this decomposition": answered. The
  interpretation survives because it never needed the per-axis partition; it now rests on the joint
  R^2 of 0.083-0.119, which bounds what all axes together explain.
- **Contradictions found and fixed.** The draft reply claimed the per-axis claims were gone from
  the conclusions. They were not:
  - Discussion (build-time risk paragraph) still read "no individual design axis accounts for more
    than about 5% of variance". Rewritten to the joint R^2 statement plus the one identified
    interaction.
  - Table 1 still labelled a row "Answer presentation (A7, **largest design axis**)" — the label is
    itself the ranking the reply withdraws. Label dropped.
  - Table 1's caption now states plainly that the per-axis rows are not a ranking and must not be
    read against one another, and that the item, provider x item and residual rows do not depend on
    that assumption.

### R3 Concern #2 — three sub-points were actionable now, not pending
Previously the whole concern was deferred to the editor. Three parts needed no new data and are
closed in this revision:
- The abstract no longer says variation is "observed in 31 perturbed and fingerprint-screened real
  issuers" — the reviewer's specific objection that it reads as external validation. It now reads
  "a small illustrative arm of 31 perturbed real issuers", and adds that we do not treat it as
  external validation, that the per-issuer perturbation preserves financial ratios by construction,
  and that the fingerprinting gate screens exact-figure recall only.
- The two new data collections (within-issuer multi-scale arm; ratios-only identification probe)
  remain the only genuinely pending items, and need new model calls.

### Verification performed
- 22 numbers in the response letter bound back to the four result JSONs: all 22 match.
- Table 8 was first hand-typed, and the binding check caught **3 wrong cells** (boundary distance
  at p_t=0.45: 0.556 vs true 0.572; "any disagreement" at 0.45: 0.633 vs 0.606; at 0.60: 0.600 vs
  0.500). The table is now GENERATED from the JSON rather than typed, so the duplicate cannot drift.
- `analysis/revision2/check_dca_binding.py` binds all 39 cells of Table 8 to the JSON. Exit 0 pass,
  1 mismatch, 2 not-checkable. Fault-injected: a single changed cell -> exit 1; a changed gap value
  -> exit 1; a deleted row -> exit 2 ("only 34 cells matched, expected 39"). Restored -> exit 0.
- Letter and manuscript both said the envelope diverges from "any disagreement" "above p_t ~ 0.4".
  The curve shows divergence from p_t = 0.35, i.e. for p_t > 0.30. Both corrected.
- Reviewer-coverage check: all 9 comment blocks present (R2 x4, R3 opening + 3 concerns + the
  closing question as its own Concern #4), and 31 load-bearing phrases from the referee text
  verified present in the RENDERED PDF, not only the source.
  Note: an initial coverage run reported 5 phrases missing; `pdftotext` is not installed on this
  machine and was returning empty output. Re-run with pymupdf: all present. The tool was broken,
  not the letter.
- Round-2 referee text extracted to `REVIEWER_REPORTS_R2.md` so the reports survive independently
  of the reply (previously they existed nowhere else).

### Build state
- `cas-sc.pdf` 25 pages, 0 undefined references, 0 undefined citations, 1 overfull hbox
  (pre-existing, line 72, the highlights block).
- `RESPONSE_TO_REVIEWERS_R2.pdf` 9 pages, 0 undefined, 0 overfull.
- Build artefacts (.aux/.log/.out/missfont.log) removed from `revision_2/`.

---

## Third pass: Reviewer 3 Concern 2 closed with two pre-registered experiments

Specification hashed BEFORE any model call:
`analysis/revision2/SPEC_r3_realarm_experiments.md`,
sha256 `137367c9175070210afa5cdc1f9534e77d99b014e196dd32fec5d17f02284fba`.
Both decision-rule branches, including the demotion branch, were fixed in that file in advance.

Collection: `capture/realarm_decontam.py`, 1,364 calls, two providers, 31 issuers, 0 errors,
3 empty completions, $1.00. Frozen at `data/frozen/realarm_decontam/` (read-only) with a sha256
per call file and a root hash over the sorted (path, hash) list:
`e0fcecc9394268fadfc133e2985766f9befcacf4dd5918a6fc24ad3f69a2d9b0`.

### Experiment A — ratio-pattern identification: NOT a null
- Open-ended ("name the company" from scale-invariant ratios): 0 of 60 calls. Zero.
- Closed-set 31-way, true names supplied in 3 randomised orderings: 19.4% top-1
  (issuer-clustered bootstrap CI 12.4-27.4%) against chance 1/31 = 3.2%; exact binomial
  p = 5.2e-18. 19 of 31 issuers identified at least once; 0 of 31 identified in all three
  orderings.
- Scoring audit: all 36 hits were full-entity-name matches. ZERO hits came from the short-ticker
  rule, so the five <=2-character tickers (AA, CC, HE, R, ST) did not generate false positives.
- Pre-registered rule required the closed-set rate to be indistinguishable from 1/31 AND a
  bootstrap upper bound below the 5% screening threshold. Neither holds. **Fallback applied: the
  real-issuer arm is demoted to an illustrative descriptive limitation.**

### Experiment B — within-issuer scale sensitivity: a clean null
- All 31 issuers x {0.6, 1.0, 1.7} x the frozen 12-spec grid, fully paired, 372 cells.
- IG/HY class differs between extreme scales in 15.9% of cells (CI 11.3-20.7%).
- Within-issuer permutation null (scale labels exchangeable) = 15.2%; p = 0.644, 10,000 perms.
- So changes of that size are re-elicitation variability, not scale. The confounded
  between-issuer correlation of revision 1 is replaced by a properly paired null.

### Manuscript changes
- New Section 3.7 "Decontamination of the real-issuer arm" + Table 9 (generated from
  `results_r3_decontam.json` by `build/make_decontam_table.py`).
- Abstract: arm reported as an illustrative descriptive limitation, both outcomes stated, no
  external-validity claim.
- Section 3.6 and the Conclusions sentence restricted to "descriptive only", pointing at 3.7.

### Deviations (recorded, not patched into the hashed spec)
`analysis/revision2/DEVIATIONS_r3_realarm_experiments.md`: the Gemini billing project was
exhausted mid-collection (HTTP 402 / RESOURCE_EXHAUSTED on all three keys); Google cells were
collected after it was funded, so final coverage is complete and no estimand changed. Also
records that HTTP 402 is no longer retried (it was being treated as a rate limit, costing ~32s
of sleep per Google job) and that the socket timeout went 120s -> 45s after one hung request
stalled the whole 12-worker pool at 786 calls.

### Verification
- Freeze gate fault-injected three ways: edit one byte of a call file -> exit 1; delete a call
  file -> exit 1; add an extra file -> detected. Restored -> exit 0.
- `analysis/revision2/r3_decontam_analysis.py` refuses to score unless the manifest root hash
  recomputes, so a half-collected or edited arm cannot become a result.
- Scale-invariance of the ratios-only profiles asserted at factors 0.6/1.0/1.7/3.3/11.0 and
  fault-injected (injecting an absolute revenue field fires the assertion).
- `build/mark_changes.py` HEADING pattern had a doubled backslash and matched nothing, so every
  heading fell through to the generic wrapper; harmless for \paragraph, it emitted
  \HLcode{\subsection{..}\label{..}} and broke the highlighted build. Fixed, and structural
  tokens are now never marked.

### Build state
- `cas-sc.pdf` 27 pages, 0 TeX errors, 0 undefined references, 0 undefined citations,
  1 overfull hbox (pre-existing).
- `RESPONSE_TO_REVIEWERS_R2.pdf` 11 pages, 0 errors, 0 undefined, 0 overfull.
- `highlighted_pdf.pdf` 27 pages, exact round-trip verified, marks non-vacuous.
