# Pre-registration: real-issuer decontamination experiments (Reviewer 3, Concern 2)

Committed and hashed BEFORE any model call. Two experiments, each closing one half of the
reviewer's required action. Frozen inputs: `data/frozen/realarm/battery_real45.json` (31 issuers),
`data/frozen/realarm/spec_grid_12.json` (12 specifications), `sealed_crosswalk.json` (issuer
identities, sealed until scoring).

## Experiment A — ratio-pattern issuer identification

**Motivation.** The existing fingerprinting gate asks the model to identify the issuer from the
perturbed profile, which still contains absolute dollar magnitudes; it therefore measures
exact-figure lookup, as the reviewer says. The open question is whether the *pattern of ratios*,
which the per-issuer uniform scaling preserves by construction, is itself identifying.

**Why prompted rather than a trained classifier.** Each issuer contributes exactly one ratio
profile, so a supervised 31-way classifier has one example per class and its accuracy would be a
statement about the classifier, not about leakage. We therefore probe the model directly.

**Inputs.** For each of the 31 issuers, a ratios-only profile: every absolute monetary quantity is
removed and only scale-invariant quantities are retained (margins, leverage and coverage ratios,
returns, growth rates, and the Altman Z'' component ratios). Scale-invariance of the retained
fields is asserted in code: multiplying every dollar quantity by any factor must leave the
ratios-only profile byte-identical. A failure is a bug, not a finding.

**Conditions.**
- Task A1, open-ended: "Name the company this profile describes, or reply UNKNOWN."
- Task A2, closed-set 31-way: the 31 true issuer names are supplied as candidates in randomised
  order; the model picks one or replies UNKNOWN. Three independent orderings per issuer, to
  remove position effects.
- Providers: openai and google, using the same models as the real-issuer arm. Temperature 0.

**Calls.** A1: 31 x 2 providers = 62. A2: 31 x 2 providers x 3 orderings = 186. Total 248.

**Estimand.** Top-1 identification rate, scored against `sealed_crosswalk.json`, which is opened
only at scoring. Open-ended answers are scored by normalised-name match, with the match rule fixed
in advance.

**Reference benchmarks.** (i) Chance for the closed set is 1/31 = 3.23%. (ii) The pre-registered
exact-figure fingerprint rate after perturbation, 2.9%. (iii) The pre-registration's 5% screening
threshold.

**Test and interval.** Exact binomial test of the closed-set rate against 1/31. Issuer-clustered
bootstrap (2,000 draws, seed 42) for all reported rates; the bootstrap unit is the issuer.

**Decision rule, fixed now.** If the closed-set top-1 rate is not significantly above 1/31 at
alpha = 0.05 AND its bootstrap upper bound is below the pre-registered 5% threshold, we report that
residual ratio-pattern identification is not detected. If it exceeds either, we report that the
perturbation does NOT prevent ratio-based identification and demote the real-issuer arm to an
illustrative descriptive limitation, which is the reviewer's permitted fallback.

## Experiment B — within-issuer scale sensitivity

**Motivation.** In the previous revision each issuer received one draw from LogUniform[0.6, 1.7],
so the scale factor is confounded with issuer identity, exactly as the reviewer states. The fix is
to vary scale *within* issuer.

**Design.** All 31 issuers x 3 scale factors {0.6, 1.0, 1.7} x the frozen 12-specification grid,
one seed per cell. Scale multiplies every absolute monetary quantity; all ratios, and therefore
Altman Z'', are invariant by construction, asserted in code. Fully paired: the same issuer and the
same specification appear at all three scales.

**Calls.** 31 x 3 x 12 = 1,116.

**Rationale for one seed.** The grid is dominated by temperature-0 specifications, where seed
variation is near-zero, and the design question is between-scale, not within-cell. Seeds are not
the estimand here and spending three times the calls on them would not change the contrast.

**Primary estimand.** The within-issuer rate at which the modal IG/HY class differs between scale
0.6 and scale 1.7, holding the specification set fixed. Secondary: the same at band resolution; and
the paired within-issuer difference in the instability score across scales.

**Test and interval.** Within-issuer permutation test: under the null that absolute scale is
irrelevant, the three scale labels are exchangeable within an issuer-by-specification cell. 10,000
permutations, seed 42. Issuer-clustered bootstrap (2,000 draws, seed 42) for the rate; the
bootstrap unit is the issuer. Paired analysis throughout, so each issuer is its own control.

**Decision rule, fixed now.** If the permutation test does not reject, we report that absolute
scale does not materially move the rating and that the earlier between-issuer correlation is
replaced by a properly paired null. If it rejects, scale itself moves ratings, the perturbation is
not innocuous, and we demote the real-issuer arm accordingly.

## Reporting, fixed now
A new table: identification rates for both tasks against all three reference benchmarks, and the
within-issuer scale-change rates with permutation p and bootstrap interval. Both results reported
at their value, including nulls.

## Claims these experiments would permit, and the limit that REMAINS either way
Permitted if both are null: "the perturbation leaves no detectable ratio-pattern identification,
and absolute scale does not move the rating within issuer." That addresses decontamination.

STILL QUALIFIED regardless of outcome: n = 31 issuers and 12 specifications remains small, and the
arm is an *illustrative real-issuer robustness check*, not external validation. A null
identification result bounds leakage; it does not establish that findings generalise to the
population of rated issuers. The abstract and conclusion must not use "external validation".
