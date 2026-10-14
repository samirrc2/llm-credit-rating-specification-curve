# Evaluating LLM-Based Credit Rating Systems: A Pre-Registered Specification-Curve Analysis

Reproducibility artifact for the manuscript of the same title.

**Authors:** Samir Chincholikar (Independent researcher, New York, USA) · Robin Chawla (Independent researcher, New York, USA, corresponding author)
**ORCID:** [0009-0007-2779-3492](https://orcid.org/0009-0007-2779-3492) · [0009-0007-2807-3948](https://orcid.org/0009-0007-2807-3948)
**Contact:** robin.chawla.cse14@iitbhu.ac.in · samir.chincholikar@gmail.com
**Repository:** https://github.com/samirrc2/llm-credit-rating-specification-curve
**Zenodo DOI:** [10.5281/zenodo.21953934](https://doi.org/10.5281/zenodo.21953934)

## Reproducibility documentation

[`REPRODUCIBILITY_DOCUMENTATION.pdf`](REPRODUCIBILITY_DOCUMENTATION.pdf) is a single, self-contained
companion describing the entire archive: data inputs and provenance, every analysis script and its
outputs, the one-command offline reproduction, the verification and determinism procedure, the pinned
environment, and licensing. It is also included in the Zenodo deposit.

Every number, table, and figure regenerates from **frozen response corpora** — **offline, with no API
calls and at zero cost.** The study comprises:

- **Confirmatory experiment (two providers, OpenAI + Google):** a fixed 90-item firm-profile battery ×
  32-specification factorial grid × 3 seeds = **8,640 elicitations** across four model snapshots, with an
  objective Altman Z″ benchmark. (The released raw corpus additionally retains an excluded third-provider
  pilot for transparency; the confirmatory analysis uses only the two providers with complete coverage.)
- **Perturbed, fingerprint-screened real-firm arm (illustrative):** 31 anonymized, perturbed issuers
  benchmarked to disclosed agency ratings, under a pre-registered fingerprint-identification gate. Two
  pre-registered decontamination experiments (**1,364 new elicitations, 1,361 substantive**) show that a
  closed-set probe still recovers issuer identity from scale-invariant ratios alone at **19.4% against a
  3.2% chance rate**, so this arm is reported as a descriptive limitation and carries no
  external-validity claim.
- **Flagship model-tier robustness arm (post-hoc):** `gpt-5.4` + `gemini-3.1-pro-preview` on the frozen
  12-specification grid × 45 credit-health items × 3 seeds = **1,620 elicitations**, fixed by
  `MANIFEST_FLAGSHIP.sha256`.
- **Reasoning-architecture arm (post-hoc):** `deepseek-r1` (native chain-of-thought) on the same frozen
  12-specification grid × 45 items × 3 seeds = **1,620 elicitations**, fixed by `MANIFEST_REASONING.sha256`.
- **A descriptive dispersion index, benchmarked against simpler baselines:** a *specification-instability
  score* (SIS) predicts held-out instability (ROC-AUC 0.94 on held-out specifications, 0.70 on the
  real-issuer calibration set), but at the IG/HY gate it is **ordinally equivalent to counting dissenting
  elicitations** and adds no incremental discrimination. A decision-curve analysis finds no triage gain
  over the dissent count. SIS is therefore reported as a descriptive dispersion summary and a governance
  trigger, **not** as a validated operational control. The deployable rule is stated directly on the
  integer dissent count.

## Repository layout
```
REPRODUCIBILITY_DOCUMENTATION.pdf  # single-file companion documenting the whole archive
config/            # grid, paraphrase templates, rating scale, run config
capture/           # collection code (NOT needed to reproduce): main collector, real-firm collector,
                   #   run_flagship.py (flagship arm), freeze_flagship.py, list_models.py
analysis/          # offline analysis:
                   #   run_analysis, addenda, benchmark_validation,
                   #   analyze_realarm, realarm_speccurve, realarm_scale_sensitivity,
                   #   tier_analysis (flagship vs nano/flash), extended_analysis (SIS validation,
                   #   self-consistency, weighted agreement, cost), revision_analysis,
                   #   permtest_and_tau, variance_model_range, crossmodel_aliasing,
                   #   reasoning_analysis, make_figures, make_extended_figures
data/
  frozen/main/     # battery_90, grid, capital_map, rating_scale, manifests (pre-registered inputs)
  frozen/realarm/  # real-firm arm frozen artifacts (battery, sealed crosswalk, provenance, spec grid)
  frozen/market_data/  # FRED spread series (cached)
  raw/main/        # frozen response corpus (per-call JSON)
  raw/realarm/     # real-firm arm model-output panels (arm/comparator/fingerprint)
  panel/           # panel.parquet (built once from raw; the analysis input)
results/           # regenerated results_*.json (incl. results_tier, results_extended) + exhibits
paper/NLP/        # manuscript (Elsevier CAS single-column), figures, highlights, cover letter, .docx
docs/              # reports, appendix D, changelog
manifest/          # SHA-256 manifests for every frozen stage (incl. MANIFEST_FLAGSHIP)
PREREGISTRATION.md, PREREGISTRATION_AMENDMENTS.md
README.md, LICENSE, CITATION.cff, DATA_AVAILABILITY.md, reproduce.sh
```

## Reproduce (offline, no keys)
```bash
pip install -r requirements.txt   # numpy, pandas, pyarrow, statsmodels (pinned, Python 3.10)
bash reproduce.sh                 # or: PY=/path/to/python bash reproduce.sh
```

`reproduce.sh` runs `python3` unless `PY` names an interpreter. Point `PY` at the environment
built from `requirements.txt` if the `python3` on your `PATH` is something else. An Anaconda base
environment, for example, aborts in `analysis/run_analysis.py` with
`ImportError: cannot import name '_lazywhere' from scipy._lib._util`, because its scipy and
statsmodels versions disagree.
All `results/results_*.json` regenerate byte-for-byte from the frozen data (verified in a clean
virtualenv from the pinned `requirements.txt`); no network access is required. Headline results:
per-comparison IG/HY flip **25.2%** (95% CI 19.7–31.2). Chance-corrected agreement reaches only
**Fleiss' κ = 0.49** at that binary resolution. Pure within-cell seed variance is **8.1%**, and the
elicitation axes jointly explain **R² = 0.083–0.119**, a share the fractional design cannot attribute to
individual axes. The rating-invariance permutation on the temperature-0-honored subgrid gives
**p = 0.0005** (η² = 0.46). The flagship tier **does not detect attenuation** (paired Δ −1.1 pp, 95% CI
−7.6 to +6.0) and the reasoning arm shows comparable instability (25.5%, paired Δ +0.9 pp).

SIS predicts held-out instability at **ROC-AUC 0.94**, and a profile-split subsampling analysis over 300
draws gives mean AUC 0.936 at the gate and 0.950 at three bands, with an index-minus-dissent-count
difference of exactly zero on every split. Cross-model transfer is moderate but inconsistent
(Spearman 0.14–0.73). Distance to the IG/HY boundary is a weaker and different signal
(AUC 0.763 and 0.655). Design aliasing on the analysed **32-specification two-provider** design is
bounded by a maximum main-effect off-diagonal correlation of **0.125** and a maximum
main-effect × two-factor-interaction correlation of **0.504**.

## Notes
- Reproduction never calls a model API. Provider API keys are required solely to *collect* a corpus
  and are never committed (`.gitignore` blocks `keys.env.txt` and any `API Keys/` folder).
- Most of `capture/` is the collection harness and is not run during reproduction, but three paths
  under it are inputs the analysis does read: `capture/flagship_runs/` and `capture/reasoning_runs/`
  hold the two frozen post-hoc corpora, and `capture/freeze_decontam.py` is imported by the
  decontamination analysis. A copy of this repository that omits them will not reproduce.
- `results/` holds generated outputs with one exception. The four `SPEC_*.sha256` files are
  pre-registration hashes, committed before computation and never written by any script. Each
  revision-2 analysis reads the relevant one to stamp its specification hash into its output.
- The disposable SEC 10-K / company-facts cache used to *build* the real-firm battery is not shipped and
  is **not needed to reproduce any result**. It is re-fetchable for free from the public SEC EDGAR system
  (keyless; a descriptive `User-Agent` header is the only requirement,
  <https://www.sec.gov/os/webmaster-faq#developers>):
  - **10-K filings** — permanent document URLs are in the `url` column of
    `data/frozen/realarm/ratings_provenance.csv`; the `efts_verify` column gives the matching EDGAR
    full-text-search link.
  - **Company facts (XBRL)** — `https://data.sec.gov/api/xbrl/companyfacts/CIK<10-digit-CIK>.json`
  - **Filing index / submissions** — `https://data.sec.gov/submissions/CIK<10-digit-CIK>.json`
  The collector that rebuilds the cache is `capture/realarm_collect.py`.
- Manifest hashes in `manifest/` fix every frozen stage.
