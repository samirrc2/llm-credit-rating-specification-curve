# Response to Reviewer 2 — NLP-D-26-00451

**Manuscript:** Evaluating LLM-Based Credit Rating Systems: A Pre-Registered Specification-Curve Analysis

We thank the reviewer for the careful reading and for recognizing the "commendably rigorous experimental execution and an exemplary reproducible pipeline." Each concern is addressed below; every number cited is reproducible offline via `reproduce.sh` (seed 42).

---

**Reviewer comment.**

> The paper applies a pre-registered specification-curve analysis to evaluate the sensitivity of LLM-generated corporate credit ratings across variations in prompt configurations, formatting choices, and sampling parameters, offering commendably rigorous experimental execution and an exemplary reproducible pipeline. However, the submission suffers from a fundamental domain misalignment for an NLP venue, as its core task—mapping structured financial data to credit ratings—treats the model as a financial classification engine without delivering insights into language representations, semantic mechanisms, or generation dynamics. Furthermore, its empirical claims are constrained by a small underlying item sample ($N=45$ synthetic profiles and $N=31$ real-world issuers), severe statistical underpowering in its equivalence testing, and aliasing artifacts in its fractional factorial design. The proposed Specification-Instability Score (SIS) largely rebrands the standard Gini-Simpson dispersion index, offering limited methodological innovation, while comparing basic elicitations against a rigid mathematical model like Altman $Z''$ without evaluating advanced pipelines like RAG or Chain-of-Thought artificially amplifies variance. Overall, the authors are strongly advised to expand their issuer dataset, evaluate modern reasoning architectures, and re-target the manuscript to a quantitative finance or financial technology venue.

**Response.** The comment raises seven distinct points; we take each in turn.

**1. Fit for an NLP venue / "financial classification engine."**

*(Addressed in manuscript Section 1, Section 2.4, and Section 5.)*

- The object of study is LLM elicitation reliability: whether an LLM's categorical judgment remains stable under defensible changes to the linguistic and procedural specification while the substantive input is held fixed.
- We do not claim to identify internal representation mechanisms; our contribution is behavioral evaluation of NLP systems under controlled linguistic and procedural perturbations, analogous to robustness and reliability evaluation in other NLP settings.
- This category of contribution is well within the Journal's stated scope — the "development and application of trustworthy AI to analyze, process, or model human language across various contexts, domains, and intelligent systems" — and it is consistent with work the Journal already publishes. Recent examples of behavioral LLM evaluation in the Journal that likewise do not analyze internal representations include Singh & Siami Namin (2025), *A survey on chatbots and large language models: Testing and evaluation techniques*; Espejel et al. (2023), *GPT-3.5, GPT-4, or BARD? Evaluating LLMs' reasoning ability in a zero-shot setting and performance boosting through prompts*; and de Wynter et al. (2023), *An evaluation on large language model outputs: Discourse and memorization*. Prompt- and paraphrase-sensitivity is also established subject matter here, e.g. Lau & Zubiaga (2025), *Understanding the effects of human-written paraphrases in LLM-generated text detection*, and Al Nazi et al. (2025), *Evaluation of open and closed-source LLMs … with zero-shot, few-shot, and chain-of-thought prompting*.
- We have revised the introduction and discussion to foreground this as an evaluation-methodology contribution on the specification-sensitivity of LLM outputs, with the instability score offered as a reusable evaluation tool. The credit-rating setting is the testbed, not the contribution.

**2. Small item sample (N=45 synthetic, N=31 real).**

*(Addressed in manuscript Section 5.2; clustering in the Table 1–5 captions and Methods Section 6.3.)*

- We agree that the number of independent underlying credit profiles is 45 in the controlled arm and 31 in the real-issuer arm. The design is intended to estimate within-profile specification sensitivity, not population prevalence. The repeated elicitation conditions provide dense paired measurement of that within-profile estimand, while uncertainty is clustered at the profile/issuer level.
- We have revised the manuscript to make this distinction explicit and to avoid treating the 8,640 elicitation cells as independent observations; confidence intervals are profile-clustered on the constructed battery (issuer-clustered on the real-issuer arm).
- We have also added a severity analysis that uses the profile structure informatively (stratum-level and boundary-distance breakdowns).

**3. Underpowering in the equivalence testing.**

*(Addressed in manuscript Section 3.6, Table 4, and Methods Section 6.3.)*

- We agree. The equivalence (TOST) analysis has been **removed**. The real-firm arm is now presented purely descriptively, with explicit sample-size caveats and no equivalence claim.

**4. Aliasing in the fractional factorial design.**

*(Addressed in manuscript Section 3.1, Table 1, Table 2, and Section 5.2.)*

- We now report the aliasing diagnostics from the frozen design directly (computed offline in `analysis/crossmodel_aliasing.py`): main-effect columns are near-orthogonal (maximum off-diagonal correlation **0.062**), while the maximum absolute correlation between a main effect and a two-factor-interaction of other factors is **0.333**, confirming that non-negligible aliasing remains. For this reason the decomposition is retained only descriptively.
- The variance components are re-presented as descriptive partitions under the assumed model, not causal attributions, and per-axis figures are qualified accordingly.

**5. The instability score "rebrands the Gini–Simpson index."**

*(Addressed in manuscript Section 4, Section 4.2, and Table 7.)*

- We agree the underlying quantity is the Gini–Simpson concentration (1 − Σ p_c²), and we now credit this explicitly.
- The contribution is not a new index but its operationalization and validation as a candidate operational, ground-truth-free control: a held-out-specification validation framework (ROC-AUC **0.94** on the constructed battery; median **0.88** across 300 splits; **0.70** on real issuers), a practical descriptive operating point (a k-dependent operating rule), and an honest account of cross-model transfer, which is moderate but inconsistent across model pairs (per-item Spearman 0.14–0.73, median ≈ 0.45; AUC ≈ 0.72), too variable to rely on, for which we state the concrete recalibration requirement — a new model should be re-scored on the specification grid (about **\$7.43 per 1,000 issuers at k = 9 on a nano/flash tier**, from the deployment cost table) rather than reusing another model's scores. Section 4 has been rewritten to make this scope precise.

**6. No advanced pipelines (RAG / Chain-of-Thought); comparison to a rigid Altman Z″ amplifies variance.**

*(Addressed in manuscript Section 3.8, Table 6, Table 9, and Section 5.3.)*

- We have added a reasoning-architecture arm using an open-weight model with native chain-of-thought (DeepSeek-R1), on the 45-item × 3-seed grid across the frozen 12 specifications. We are precise about what this arm varies. The frozen 12-specification grid spans four axes — provider, prompt paraphrase, output format, and answer presentation (version, few-shot, and temperature are fixed). A single model instantiates the grid, so the reasoning arm exercises the three non-provider axes — paraphrase (3 levels), output format (2), and presentation (2), fully crossed into all 12 distinct configurations — while holding the fourth axis, provider, constant. It is therefore not literally the two-provider grid, and we describe it accurately: the +0.9-percentage-point paired difference below compares three axes of variation (reasoning) against four (nano/flash). The arm is labelled post-hoc (not pre-registered); it was collected via the OpenRouter API (model `deepseek/deepseek-r1`) and frozen with a SHA-256 manifest, and reported with a dedicated results table, a new row in the model-snapshots table, a manifest entry, and a line in the data-availability statement.
- Result: the reasoning-model arm shows a **25.5%** IG/HY flip rate (95% CI 20.9–30.1%). The paired difference against the nano/flash tier is **+0.9 percentage points** (95% CI **−7.0 to +8.8**), i.e. statistically indistinguishable, and comparable to the flagship tier (23.6%). We therefore do not observe evidence of attenuation under explicit reasoning in this arm.
- Two design differences qualify the comparison. First, the reasoning arm contains no cross-provider variation, which §3.3 shows is the largest agreement gap (band-level agreement 64.4% across providers versus 82.5% within); the nano/flash 24.7% and flagship 23.6% figures include that component, whereas DeepSeek's 25.5% does not. Second, DeepSeek-R1 has a substantially more skewed marginal IG/HY distribution (31.4% investment-grade versus 79.9% for the flagship tier). Both features change the attainable disagreement structure. We therefore interpret the 25.5% flip rate as evidence of specification sensitivity within the evaluated reasoning model, rather than as a strictly like-for-like comparison across tiers.
- On amplification: Altman Z″ is used only as a pre-specified construction and stratification reference. The core instability measures (IG/HY flip, cross-specification agreement) are computed from within-model disagreement and use no benchmark, so they cannot be inflated by the choice of benchmark.
- On RAG specifically: retrieval augmentation changes the information set available to the model rather than the elicitation of a fixed input, so it would break the controlled design that holds the substantive facts constant across specifications. We therefore treat retrieval-augmented pipelines as out of scope for this controlled study and note them as future work; the chain-of-thought arm is the pipeline variation compatible with the design.

**7. Suggested re-targeting to a finance venue.**

*(Addressed in manuscript Section 1 and Section 2.4.)*

- With the strengthened elicitation-reliability framing (point 1), the reasoning-architecture arm (point 6), and the reusable evaluation score (point 5), the contribution sits as an LLM evaluation-methodology paper, and we have kept it here.
- We would also note, respectfully, that a finance *application domain* does not place the work outside the Journal's scope. The Journal publishes finance-domain NLP — e.g. Sun et al. (2025), *Financial sentiment analysis for pre-trained language models incorporating dictionary knowledge and neutral features*, and Chen et al. (2025), *Sentiment analysis for stock market research: A bibliometric study* — and, separately, LLM reliability and evaluation studies, including domain-situated LLM evaluations in e-commerce, radiology, and clinical records. To our knowledge, this is the first study in the Journal to evaluate elicitation-specification sensitivity in direct LLM-generated credit-rating judgments, which we see as complementing these established strands rather than falling outside the Journal's scope.
- Moreover, the underlying evaluation framework is not intrinsically finance-specific and can in principle be applied to other categorical LLM judgment tasks, so the contribution is not narrowly domain-bound. We are of course glad to defer to the editor on venue fit.
