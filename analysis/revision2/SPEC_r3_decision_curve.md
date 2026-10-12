# Pre-registered spec: decision-curve / net-benefit analysis for the instability score

Committed and hashed BEFORE the computation is run. Reviewer 3, Concern #3 required action:
"report a decision-curve analysis or net-benefit analysis for triage, showing whether SIS improves
referral decisions over 'flag any disagreement', over distance to the IG/HY boundary, and over
self-consistency vote margins."

## Data
The frozen panel `data/panel/panel.parquet`, credit_health family, lenient parse, providers
openai+google. No new elicitations. Identical calibration/validation split to
`r3_sis_baselines.py`: calibration = even-indexed spec_ids, validation = odd-indexed. Event =
the item's validation elicitations are not unanimous at the stated resolution.

## Strategies compared
1. `sis` — specification-instability score (Gini--Simpson) on the calibration specs.
2. `dissent` — number of dissenting calibration elicitations.
3. `neg_margin` — negative self-consistency vote margin.
4. `neg_boundary_dist` — negative distance of the modal letter to the IG/HY boundary.
5. `any_disagreement` — the fixed rule "flag iff SIS > 0", no free threshold.
6. `flag_all`, `flag_none` — the two reference strategies of a decision curve.

## Estimand
Standard net benefit at threshold probability pt, n items:
  NB(pt) = TP/n - (FP/n) * (pt / (1 - pt))
For strategies 1-4, which are continuous scores rather than probabilities, the curve reported at
each pt is the upper envelope over that strategy's own attainable score thresholds. This is the
most favourable reading of each strategy, so it cannot understate SIS.
pt grid: 0.05 to 0.60 in steps of 0.05.

## Pre-stated prediction (the result is algebraic, not discovered)
At binary (IG/HY) resolution SIS = 2(m/k)(1-m/k) is a strictly increasing function of the
dissent count m for m < k/2. The two strategies' threshold families therefore generate
IDENTICAL flag sets, so their net-benefit curves must coincide at every pt. Any difference is a
bug in this script, not a finding. We predict:
  - max |NB_sis(pt) - NB_dissent(pt)| = 0 exactly, at every pt, at ighy resolution;
  - `any_disagreement` attains the SIS envelope wherever the envelope's optimum is SIS>0;
  - `neg_boundary_dist` is weakly dominated, consistent with its lower AUC.

## Decision rule
If the maximum absolute net-benefit gap between SIS and the dissent count is 0 across the pt
grid, we report that SIS yields no triage gain over counting dissents and retain the withdrawal
of the incremental-value claim. Reported at its value either way, including a null.

## Outputs
`results/results_r3_decision_curve.json`. Deterministic; no RNG is used.
