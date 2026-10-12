# Deviations from the pre-registration — real-issuer decontamination experiments

The pre-registration `SPEC_r3_realarm_experiments.md` is hashed
(`137367c9175070210afa5cdc1f9534e77d99b014e196dd32fec5d17f02284fba`) and is NOT edited. Deviations
forced during execution are recorded here instead, which is the point of hashing the spec first.

## Deviation 1 — Google/Gemini provider could not be collected

**What the spec said.** "Providers: openai and google, using the same models as the real-issuer
arm" (Experiment A); Experiment B over the frozen 12-specification grid, which assigns 6
specifications to each provider.

**What happened.** Every Gemini key returns HTTP 402 before any content is generated:

    "Your prepayment credits are depleted. Please go to AI Studio ... to manage your project
     and billing."  (status RESOURCE_EXHAUSTED)

All three `GEMINI_API_KEY_*` values resolve to the same exhausted billing project, so key rotation
does not help. This is an account-funding condition, not a rate limit and not a code defect; it
cannot be worked around from inside the analysis.

**Effect on coverage.**
- Experiment A: 124 of 248 planned calls (openai only).
- Experiment B: 558 of 1,116 planned calls — the 6 openai specifications of the 12-specification
  grid, at all 31 issuers and all 3 scales.
- The paired structure that the estimands depend on is UNAFFECTED: every retained
  (issuer, specification) cell still appears at all three scales, so the within-issuer scale
  contrast is still fully paired and still has 31 issuer clusters.

**What this costs.** The cross-provider half of both experiments is missing. Experiment A's
identification rate is then a statement about one model family, not two; Experiment B's scale null
is estimated on half the specification grid. Neither estimand is biased by the absence — the
missing cells are missing for a billing reason that is independent of issuer, scale and response —
but the evidence is weaker than pre-registered, and any claim must say "on the OpenAI arm".

**Resolution.** Top up the Gemini billing project and re-run; the runner is resume-safe and will
collect only the missing Google cells, leaving every existing immutable call file untouched. Until
then the manuscript must report the experiments as single-provider.

## Deviation 2 — HTTP 402 is not retried

The runner originally treated `RESOURCE_EXHAUSTED` as a rate limit and retried it five times with
backoff. Because the Gemini failure carries that status, half the queue spent roughly 32 seconds
sleeping per job before failing, which is why throughput was 8 calls/min rather than ~25. A 402 is
now a hard, unretried failure counted separately as `billing_blocked`, so an exhausted account is
visible in `run_meta.json` instead of looking like transient flakiness.
