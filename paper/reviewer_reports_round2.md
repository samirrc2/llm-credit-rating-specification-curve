# Reviewer reports, revision 2 (NLP-D-26-00451)

Verbatim referee text, extracted from RESPONSE_TO_REVIEWERS_R2.tex so the reports survive
independently of the reply. Reviewer 2 dated 21 September; Reviewer 3 dated 19 September.
Do not edit a reviewer's words.

## Reviewer \#2, Concern \#1

1. Please formalize the "near-boundary" component of the operational review rule in
Section 4 and Algorithm 1. The function $g$ maps a letter rating to a decision class, such as
IG/HY, and $\hat r$ is subsequently defined as the modal decision class. It is therefore unclear how
the condition $\hat r \in B$ identifies a rating "near" the IG/HY boundary.

## Reviewer \#2, Concern \#2

2. Please clarify the sampling convention underlying the reported matched-pair flip
probabilities. The Methods and the captions of Figures 2--4 should state whether two draws may
select the same elicitation cell and whether the pair may differ in specification, seed, or both.
This clarification would make the 25.2% result and the self-consistency analysis fully
reproducible.

## Reviewer \#2, Concern \#3

3. Please harmonize the description of the analytical sample near the beginning of the
paper. The abstract reports 45 credit-health profiles, 32 specifications, and three seeds, giving
4,320 credit-rating elicitations, whereas the Introduction describes a 90-item battery and 8,640
elicitations. Although Section 6.1 explains that the additional 45 directional items are not
analyzed in this paper, this distinction should be stated at the first mention of the 8,640-cell
experiment to avoid the impression of inconsistent sample sizes.

## Reviewer \#2, Concern \#4

4. In Table 4 and Section 3.6, the statement that approximately 33% agreement is
"expected by chance" requires qualification. If this is a uniform three-class reference value,
please label it as such. If it is intended as a chance-corrected baseline based on the observed
class marginals, the corresponding calculation should be provided.

## Reviewer \#3 --- opening assessment

the authors have made efforts to address the previous review comments, including
reframing the contribution as an evaluation-methodology case study, removing the economic
translations, correcting the permutation test, adding a reasoning-architecture arm, and providing
held-out-specification validation for the SIS...\ however, the revised manuscript still requires
careful evaluation, and the following points must be considered before it can be further considered
for publication. this manuscript is a research article, and it is evaluated as such.

## Reviewer \#3, Concern \#1 --- per-axis variance decomposition

the per-axis variance decomposition remains non-identified under the
resolution-limited d-optimal fractional grid, yet the abstract, highlights, and conclusions still
state that no controllable axis exceeds about 5% of rating variance. the authors now report
aliasing diagnostics, including a maximum absolute correlation of 0.333 between a main effect and a
two-factor interaction of other factors, and they correctly label the decomposition as descriptive.
however, the headline claim of "no axis exceeds ~5%" is still presented as a
substantive finding rather than as a model-dependent descriptive partition. because main effects can
be partially aliased with omitted interactions, the per-axis point estimates cannot support even a
descriptive ranking of axes without explicit bounds or a design that separates them. the added
R^2 range of 0.083 to 0.119 across model specifications does not identify individual
axes; it only shows that the elicitation axes jointly explain little variance under the assumed
models. this remains important because the paper's central interpretation---that instability is
spread across elicitation choices rather than concentrated in a tunable knob---depends in part on
this decomposition.

required action: either remove all per-axis numeric claims from the abstract, highlights,
and conclusions, or conduct a fully crossed or resolution-v sub-experiment on a reduced set of
factors and items that can cleanly estimate main effects and relevant two-way interactions. if a new
experiment is not feasible, provide formal bounds on each per-axis variance share under all aliasing
structures consistent with the observed design matrix, or fit a bayesian hierarchical model with
explicit shrinkage priors on interaction terms and report posterior intervals for the main effects.
the abstract and highlights should then state only what is identified: that the elicitation axes
jointly explain a small and model-dependent share of variance, not that any specific axis is bounded
by ~5%.

## Reviewer \#3, Concern \#2 --- external validity of the real-issuer arm

the real-issuer arm still does not provide strong external validity, and the
decontamination procedure remains insufficiently validated for the claims made...\ the perturbation
applies a single per-issuer uniform scaling factor to all dollar quantities. this preserves financial
ratios and Altman Z" by construction, but it does not prevent an LLM from inferring issuer identity
from the pattern of ratios, nor does it rule out memorized issuer knowledge that is not based on
exact figures. the fingerprinting test only measures exact-figure lookup. the authors acknowledge
this limitation, but the abstract still states that specification variation is observed in "31
perturbed and fingerprint-screened real issuers," which can be read as external validation. in
addition, the scale factor is confounded with issuer identity because each issuer receives only one
draw. the sample of 31 issuers and 12 specifications is also small for any quantitative external
claim.

required action: add a ratio-pattern identification test. for example, train a classifier
on financial ratios to predict issuer identity from the perturbed profiles, or prompt the LLM to
infer the issuer from the ratio profile after perturbation, and report the identification rate.
conduct a within-issuer scale sensitivity design by re-eliciting a subset of issuers at multiple
scale factors, such as 0.6, 1.0, and 1.7, so that scale is not fully confounded with issuer
identity. if these checks show residual identification or if the sample remains too small, remove
the real-issuer claim from the abstract and conclusion and present the arm only as an illustrative
descriptive limitation. the paper should not imply external validity beyond what the design can
support.

## Reviewer \#3, Concern \#3 --- incremental value of the instability score

the SIS validation is improved, but its incremental value over simple
disagreement-based baselines and its status as a deployable model-risk control remain unproven...\
at the binary IG/HY gate with a low threshold, the SIS flag reduces to "any disagreement" across
the k elicitations. the reported Youden-optimal threshold of 0.08 is below the smallest non-zero SIS
value at k=16, so the operating rule is essentially "flag any issuer with at least one disagreeing
calibration elicitation." this rule is already directly observable from the k elicitations and does
not require the continuous SIS. the manuscript does not compare SIS against simple baselines such as
the number of dissenting elicitations, the modal rating's distance to the IG/HY boundary,
self-consistency vote margins, semantic entropy, or token-level confidence. the threshold is also
chosen and evaluated on the same held-out split, and cross-model transfer is moderate and
inconsistent. this matters because the abstract and highlights present the SIS as a "validated" and
"deployable model-risk control."

required action: benchmark SIS against these simple baselines in both
held-out-specification and held-out-issuer settings. report a decision-curve analysis or net-benefit
analysis for triage, showing whether SIS improves referral decisions over "flag any disagreement,"
over distance to the IG/HY boundary, and over self-consistency vote margins. if SIS does not provide
incremental value beyond these baselines, reframe it as a descriptive dispersion index rather than a
deployable control, and remove or substantially qualify the "validated" and "deployable" language
in the abstract and highlights. if it does provide incremental value, report the threshold selection
in a fully nested cross-validation or on an independent calibration set and show how performance
varies with k and tau.

## Reviewer \#3, Concern \#4 --- closing question on identifiable bounds

under the resolution-limited d-optimal fractional grid, can you provide formal
identifiable bounds on the maximum possible main effect of answer presentation and the
provider-by-item interaction under all aliasing structures consistent with the observed design
matrix, and how would those bounds change the abstract's claim that no controllable axis exceeds
about 5% of rating variance?
