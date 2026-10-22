# Reproducibility and release identity

Three different identities must be kept separate:

1. **Code release:** exact Git commit; code package manifest and notebook-cell hashes.
2. **Data snapshot:** actual source bytes, acquisition/check times, coverage, response hashes,
   record/version relationships and authorized storage location.
3. **Analysis/render run:** source snapshot + recipe/settings + environment + output hashes.

A new fetch may create new data even with unchanged code. Re-rendering a slide is not a new
source check. Cached prior-success data after a failed refresh retain their true older check date.
Do not call every date in a snapshot its release date.

## Every empirical release should record

- Git commit and a dirty-working-tree flag; full SHA-256 for exact code/input/output bytes.
- Actual cutoff and source check/attempt dates; stable paths or approved snapshot accessions.
- Cohort universe and identifier crosswalks; source-specific missingness; version/consent scope.
- Runtime Python and dependency versions. Preserve `pip freeze` privately; review for local paths
  or credentials before publication. The repository requirements are not the historical run lock.
- Tests actually executed, separately from inherited reports and user-reported production checks.
- Which analyses were exploratory, prespecified, conditional, withheld or independently validated.
- Analysis assumptions and human-review provenance. Do not expose blind expert labels to an LLM
  or outcome-aware process before independent adjudication is complete.

The publisher creates a single prepared-file commit (after GitHub's initial README bootstrap for
a new repository), checks concurrent updates with non-force behavior, and reports the commit ID.
Later updates normally go to a review branch/PR. Public-file manifests exclude themselves from
self-hashing. Git object hashes and SHA-256 content hashes serve different roles.

Historical deck summaries and reported checks remain evidence about earlier runs, not an
empirical result reproduced in CI. The source notebooks' calculation cells are preserved exactly
in the initial repository; initial synthetic smoke tests demonstrate execution, not scientific validity.
