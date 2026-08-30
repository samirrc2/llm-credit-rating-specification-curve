# Data availability

All data required to reproduce every result are included in this repository and are released under
MIT. No proprietary data and no live model access are needed to reproduce the paper. The archived,
citable reproducibility artifact is deposited on Zenodo:
**DOI [10.5281/zenodo.21953935](https://doi.org/10.5281/zenodo.21953935)**.

## Frozen inputs (pre-registered)
- `data/frozen/main/battery_90.json` — the 90-item firm-quarter battery (Altman Z″ benchmark bands).
- `config/grid_definition.json`, `config/paraphrase_templates.json`, `config/rating_scale.json` —
  the specification grid and prompt templates.
- `data/frozen/main/capital_map.json` — Basel CRE20 ECRA risk-weight map (quote-verified; **post-hoc**).
- `data/frozen/market_data/*.csv` — FRED ICE-BofA option-adjusted spread series (cached).
- `PREREGISTRATION.md`, `PREREGISTRATION_AMENDMENTS.md`.

## Frozen response corpus (the elicitations)
- `data/raw/main/run_20260707_185649/` — per-call model responses from the full data collection. The
  confirmatory analysis in the manuscript uses the two providers with complete current-and-prior snapshot
  coverage (OpenAI and Google; 8,640 cells); a third provider (xAI) was piloted with incomplete coverage
  and is excluded from the analysis but retained here in raw form for transparency.
- `data/panel/panel.parquet` — the analysis panel built once from the raw corpus (the analysis scripts
  filter to the two confirmatory providers).

## Real-firm arm
- `data/frozen/realarm/` — anonymized perturbed battery, sealed crosswalk, rating provenance
  (verbatim 10-K quote + SEC URL + document SHA-256), spec grid, selection artifacts.
- `data/raw/realarm/{arm_runs,battery_comp_runs,fp_runs}/` — model-output panels (the arm's frozen
  elicitations and the fingerprinting-gate probes).

## Integrity
- `manifest/MANIFEST_*.sha256` fix every frozen stage (inputs, raw, panel, analysis, capital, market,
  validation, real-firm arm).
- Verified: `bash reproduce.sh` regenerates every `results/results_*.json`, `results/H1_results.json`,
  and `results/exhibits/*` **byte-for-byte**, offline.

## Re-fetchable (not required)
- The disposable SEC 10-K HTML and company-facts cache used to *build* the real-firm battery is not
  shipped (removed to keep the artifact lean) and is **not needed** to reproduce any result — the
  anonymized battery and the model-output run panels are frozen in `data/frozen/realarm/` and
  `data/raw/realarm/`.
- It is re-fetchable for free from the public **SEC EDGAR** system (no API key; SEC requires only a
  descriptive `User-Agent` header — https://www.sec.gov/os/webmaster-faq#developers):
  - **10-K filings:** permanent document URLs are in the `url` column of
    `data/frozen/realarm/ratings_provenance.csv`, e.g.
    `https://www.sec.gov/Archives/edgar/data/<CIK>/<ACCESSION>/<doc>.htm`
    (the `efts_verify` column holds the matching EDGAR full-text-search URL,
    `https://efts.sec.gov/LATEST/search-index`).
  - **Company facts (XBRL):** `https://data.sec.gov/api/xbrl/companyfacts/CIK<10-digit-CIK>.json`
  - **Filing submissions index:** `https://data.sec.gov/submissions/CIK<10-digit-CIK>.json`
- The collector `capture/realarm_collect.py` rebuilds the cache from these endpoints.

## Reproducibility — the two chains (journal-facing)
**1. Frozen corpus → results (the reproduction of record).**
`bash reproduce.sh` regenerates every `results/results_*.json`, `H1_results.json`, and exhibit
**byte-for-byte** from `data/panel/panel.parquet` + `data/frozen/*` — offline, no API calls, no keys.
Verified: `results.json = 580f1f47…`, real-arm `diff = −0.0914 (95% CI −0.21, 0.03; not distinguishable from zero, TOST inconclusive)`.

**2. Raw responses → panel → results (the full chain, provided for auditors).**
The complete raw corpus — **12,960 per-call model responses** — is released at
`data/raw/main/run_20260707_185649/raw/` and integrity-fixed by `MANIFEST_RAW` (`fd8122fa…`,
recomputation verified). `analysis/build_panel.py` rebuilds the panel from these raw responses; the
rebuilt panel is **row-for-row identical** to the released `panel.parquet` (`df.equals == True`,
32,379 rows). Note: Parquet serialization is not byte-deterministic, so a rebuilt `panel.parquet`
may hash differently while containing identical data; the confirmatory analysis reads the released
frozen panel, so **all reported numbers reproduce exactly**. The released `panel.parquet`
(`MANIFEST_PANEL` `64507c1e…`) is the artifact of record.

**On "re-collecting" the LLM responses.** LLM outputs are non-deterministic — that is the paper's
central finding — so re-querying the models would *not* reproduce the same corpus and is neither
expected nor meaningful for reproducibility. The frozen response corpus is the primary data;
`capture/` is included only to document how it was collected (requires provider API keys; not needed
to reproduce any result).
