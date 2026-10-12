# Pre-registered spec: revision-2 follow-ups (aliasing scope, coding invariance, semantic entropy)

Committed and hashed BEFORE the computation is run. Three items, each closing a specific
reviewer objection. Offline, deterministic, no new model calls.

## Item 1 — aliasing diagnostics on the design that is actually analysed
Reviewer 3, Concern 1 quotes our reported "maximum absolute correlation of 0.333 between a main
effect and a two-factor interaction of other factors". That figure is computed by
`analysis/crossmodel_aliasing.py` over all 48 specs in `grid_definition.json`, which spans THREE
providers. The variance decomposition in Section 3.1 is fitted on the two-provider arm
(openai + google), which is 32 specs. The diagnostic therefore describes a different design from
the one decomposed.

Recompute, on the 32-spec analysed design, with the same effect coding (k-1 columns per factor,
last level as -1) and centred Pearson correlation:
  - max |corr| between main-effect columns of distinct axes;
  - max |corr| between a main-effect column and a 2FI column of other ("non-parent") axes.

Reported at its value whatever it is. We expect it to be LARGER than 0.333, because dropping a
provider level removes design points. If so the manuscript figure is corrected upward and the
non-identification argument is strengthened, not weakened.

## Item 2 — a coding-invariant aliasing diagnostic
A pairwise correlation between effect-coded columns depends on which level is taken as the
reference, so a reviewer can object that 0.333 (or its replacement) is a coding artifact.
Compute the canonical correlations between the centred main-effect subspace span(X) and the
centred two-factor-interaction subspace span(Z), via the singular values of Q_X' Q_Z with Q from
thin QR. These are invariant to any non-singular re-parameterisation within either subspace.

Estimand: the largest canonical correlation. 1.0 means a main-effect contrast lies exactly in the
2FI span (exact confounding); 0.0 means orthogonality. Report the full spectrum and the count
above 0.9.

## Item 3 — discrete semantic entropy as a benchmark predictor
Reviewer 3, Concern 3 lists semantic entropy among the baselines SIS must beat. Our current
response says it "would need re-elicitation with log-probabilities enabled". That is wrong for
the discrete estimator: Farquhar et al. (Nature 2024) state that "discrete semantic entropy
approximates P(C_i|x) directly from the number of generations in each cluster, disregarding the
token probabilities", and recommend it precisely for models that do not expose probabilities.

Our outputs are categorical ratings on a fixed ordinal scale, so the semantic-equivalence
clustering step is given by construction: two elicitations share a cluster iff they share a
rating at the resolution analysed. Discrete semantic entropy then reduces exactly to the Shannon
entropy of the rating distribution, H = -sum_c p_c log p_c, which IS computable on the frozen
corpus.

Add H as a fourth benchmark predictor to the baseline comparison and to the decision curve, at
ighy / band / letter resolutions, using the identical 16/16 calibration-validation split,
mid-rank tie-corrected AUC, and issuer-clustered bootstrap (2000 draws, seed 42) already used.

### Pre-stated prediction (algebraic, not discovered)
At a binary resolution with k elicitations and minority count m, H = H_b(m/k) with H_b the binary
entropy function, which is strictly increasing on m < k/2. H is therefore an order-isomorphic
transform of the dissent count on the binary gate, exactly as SIS = 2(m/k)(1-m/k) is. We predict
AUC(H) = AUC(SIS) = AUC(dissent count) exactly, Spearman(H, dissent) = 1, and identical
net-benefit curves. A departure is a bug in the script, not a finding. Asserted in code.

### Scope limit to state in the manuscript, not to be overclaimed
Farquhar et al. sample repeated generations under a FIXED prompt and cluster free-text answers by
bidirectional entailment. Our design deliberately varies the elicitation specification and
records a categorical label. What we compute is therefore the discrete (Shannon) semantic-entropy
estimator applied to our categorical outcome over a specification ensemble -- a specification-level
analogue, not a replication of their hallucination-detection estimand. The manuscript must say so.
Token-level confidence remains genuinely not computable: the corpus retains no log-probabilities.

## Outputs
`results/results_r2r3_followups.json`. Deterministic; RNG only for the bootstrap, seed 42.
