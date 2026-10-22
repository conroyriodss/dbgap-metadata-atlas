# Quickstart

## Existing project user

1. Open A, B, and C from the README. A GitHub-opened Colab notebook can be saved to your Drive
   for personal settings. Keep the same `DRIVE_ROOT` in all three; do not relocate caches into Git.
2. Set `PUBMED_EMAIL` in your working A copy. Where used, the NCBI key is read from Colab's
   `NCBI` secret. Do not put real credentials or personal configuration into committed source.
3. A: `reuse` loads successful cached responses and collects missing/due failed items;
   `check_stale` additionally checks old successful responses after three calendar months.
   `clean` deliberately archives selected registered files. Maintenance at the end stays off.
4. B: leave `ANALYSIS_MODE='reuse'`. Its recipe/input signatures decide whether outputs change.
   Set `DATA_CUTOFF` to an actual acquisition cutoff when known; never the day slides are rendered.
5. C: run after B. It requires the matching B recipe and verifies recorded file hashes.

Primary results: `preliminary14_analysis/`; presentations: timestamped folders under
`preliminary14_decks/`. The interactive explorer is an optional local companion, not a dynamic
PowerPoint slide.

## New user without source data

First run the synthetic smoke test. The full A workflow can initiate thousands of public-metadata
requests and download ontology files. It is not a demo run and does not use a GPU. Review A's
settings and source documentation before enabling all optional collectors. A's default
`FTP_RUN_MODE='full'` is a checkpointed full corpus collection; `audit` is a separate pilot.

B can operate on CSV files bearing the same stems for testing. Production defaults use pandas /
PyArrow Parquet. Ordinary repository CI does not recollect public sources.

## Failure handling

A preserves prior successful rows when a refresh fails; successful source-check timestamps and
attempt timestamps differ. A join or cached read is not a successful remote check. Unknown
platform status is not platform-negative. The Authorized Access block has bounded attempts,
1/7/30-day retry cooldowns and a per-run failure limit. A new version has its own eligibility.

If source files change, rerun B before C. If ontology validation is unavailable, source-recorded
labels can still appear but hierarchy refinements are not claimed. If prospective publication,
release-date, or administrative histories are missing, method-matched analyses are withheld or
marked as descriptive analogues; there is no automatic gap imputation.

## Local environment

Use Python 3.11+ and `requirements.txt`. The listed versions are an initial packaging/smoke-test
baseline, not a recovered lockfile for the original production run. Capture the actual runtime
for every empirical run. Colab images may differ from the baseline; review conflicts rather than
blindly downgrading an active notebook kernel.
