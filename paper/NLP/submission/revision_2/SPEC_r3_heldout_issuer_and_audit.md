# Pre-registered spec: held-out-issuer benchmark, and a full design-dependent re-audit

Committed and hashed BEFORE computation. Two items. Offline, deterministic, no new model calls.

## Item 1 — held-out-issuer benchmark (Reviewer 3, Concern 3)

The required action asks for the baseline benchmark "in both held-out-specification and
held-out-issuer settings." Our existing comparison (`r3_sis_baselines.py`) splits
SPECIFICATIONS 16/16 and evaluates every issuer. The held-out-ISSUER setting was not run, and the
response letter must not claim it was.

**Design.** Features and events are constructed exactly as in the specification split: the
instability score, discrete semantic entropy, dissent count, vote margin and boundary distance are
computed on the 16 calibration specifications; the event is "the issuer's modal IG/HY call changes
on at least one of the 16 held-out specifications." Issuers are then split at random into two
disjoint halves, and discrimination is computed ONLY on the held-out issuer half. 300 random splits,
seed 42, matching the 300-split protocol already used elsewhere in the paper.

**Estimand.** Mean held-out-issuer ROC-AUC per predictor, with the 2.5/97.5 percentiles across
splits; and the paired per-split AUC difference between the score and the dissent count, with its
percentile interval.

**Pre-stated prediction (algebraic).** Rank-equivalence of the score, the dissent count, the vote
margin and discrete semantic entropy at the binary gate is a property of the per-issuer statistic,
not of which issuers are evaluated. It therefore holds on ANY subset of issuers, so the AUC
difference must be exactly 0 on every split. A non-zero difference is a bug in this script, not a
finding. Asserted in code.

**Reporting.** Reported at its value either way, in a new column block of Table 7, so the
specification-split and issuer-split results are shown SEPARATELY and never merged into one AUC.

## Item 2 — re-audit of every design-dependent quantity

The aliasing diagnostic we previously reported (0.062 / 0.333) was computed on the 48-specification
three-provider grid rather than the 32-specification two-provider arm that the variance
decomposition is fitted on. Having found one such scope error, we must establish whether any other
reported number shares it, rather than assert that none does.

**Procedure.** Enumerate every analysis script that derives a quantity from the specification
design matrix or the specification set, and record for each: the spec set it reads, its cardinality,
and whether that set is the analysed 32-specification arm. Any script reading `grid_definition.json`
(48 specs, three providers) whose output is reported for the two-provider arm is a scope error of
the same kind.

**Decision rule.** If the audit finds further scope errors, they are corrected and reported, and
the quality-control sentence in the response letter is written to say what changed. If it finds
none, the letter may state that no other reported result or conclusion changed. The sentence is
written only after the audit, never before.

## Outputs
`results/results_r3_heldout_issuer.json`, `results/results_design_audit.json`.
