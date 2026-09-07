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
- **Decontaminated real-firm arm:** 31 anonymized, perturbed issuers benchmarked to disclosed agency
  ratings, under a pre-registered fingerprinting gate.
- **Flagship model-tier robustness arm (post-hoc):** `gpt-5.4` + `gemini-3.1-pro-preview` on the frozen
  12-specification grid × 45 credit-health items × 3 seeds = **1,620 elicitations**, fixed by
  `MANIFEST_FLAGSHIP.sha256`.
- **A deployable control:** a *specification-instability score* (SIS), validated on held-out
  specifications (ROC-AUC 0.94; ROC-AUC 0.70 on the real-issuer arm), with a self-consistency curve and a
  per-issuer cost model.

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
paper/ISWA/        # manuscript (Elsevier CAS single-column), figures, highlights, cover letter, .docx
docs/              # reports, appendix D, changelog
manifest/          # SHA-256 manifests for every frozen stage (incl. MANIFEST_FLAGSHIP)
PREREGISTRATION.md, PREREGISTRATION_AMENDMENTS.md
README.md, LICENSE, CITATION.cff, DATA_AVAILABILITY.md, reproduce.sh
```

## Reproduce (offline, no keys)
```bash
pip install -r requirements.txt   # numpy, pandas, pyarrow, statsmodels (pinned; Python 3.10)
bash reproduce.sh
```
All `results/results_*.json` regenerate byte-for-byte from the frozen data (verified in a clean
virtualenv from the pinned `requirements.txt`); no network access is required. Headline results:
per-comparison IG/HY flip **25.2%** (95% CI 19.7–31.2); pure within-cell seed variance **8.1%**;
determinism-subgrid permutation **p = 0.001**; flagship tier shows **no evidence of attenuation**
(paired Δ −1.1 pp, 95% CI −7.6 to +6.0); SIS validation **ROC-AUC 0.94** (held-out specifications).

## Notes
- `capture/` is provided for transparency only; reproduction never calls a model API. Provider API keys
  are required solely to *collect* a corpus and are never committed (`.gitignore` blocks `keys.env.txt`
  and any `API Keys/` folder).
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
