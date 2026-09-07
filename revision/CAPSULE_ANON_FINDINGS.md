# Anonymized-capsule re-verification — findings (2026-09-06)

Scanned `paper/ISWA/submission/reproducibility_capsule_ANONYMIZED.zip` (17,929 files). The manuscript-identifier scrub (family-names → "Anonymous", ORCIDs → XXXX, DOIs/repo → withheld) held, BUT three metadata files still leak author identity. These MUST be fixed before the capsule is refreshed for resubmission.

## Real leaks to fix (author de-anonymization risk)

1. **CITATION.cff** — given-names not scrubbed and location present:
   - line 27: `given-names: "Samir"` → change to `"Author"` (or `"Anon"`)
   - line 31: `given-names: "Robin"` → change to `"Author"`
   - lines 28, 33: `affiliation: "Independent researcher, New York, USA"` → drop the location, e.g. `"Affiliation withheld for double-blind review"`

2. **README.md** — line 5 author line:
   - `**Authors:** Anonymous Author (Independent researcher, New York, USA) · Anonymous Author (Independent researcher, New York, USA, corresponding author)` → remove "New York, USA"; keep it generic, e.g. `Anonymous Author (affiliation withheld) · Anonymous Author (affiliation withheld, corresponding author)`

3. **.zenodo.json** — lines 11, 16:
   - `"affiliation": "Independent researcher, New York, USA"` (×2) → `"Withheld for double-blind review"`

The family-names ("Anonymous"), ORCIDs (XXXX), emails (anonymous@example.com), repository ("withheld"), and DOIs ("[DOI withheld]") were correctly scrubbed. The `"New York, USA"` location string is the specific remaining identifier — it narrows authorship and should go.

## Confirmed NOT leaks (leave as-is)
- `data/raw/realarm/fp_runs/**` raw responses contain real company names (NYT, Curtiss-Wright, Robinhood, etc.). These are the *fingerprinting-test* outputs (the model guessing which real issuer a perturbed profile is) — legitimate study data and evidence for the 2.9% identification result, not author identity. Keep them.
- "Robin"/"chawla" substring hits in fp_runs = "Robinson"/"Robinhood" company guesses. Not the co-author name.

## Action
Fix the three files in the SOURCE tree's anonymization step (the public-repo copies correctly keep the real names Chincholikar/Chawla; only the ANONYMIZED capsule copies need these fields blanked). Re-zip during the capsule refresh after the manuscript revision, then re-run this scan to confirm clean.
