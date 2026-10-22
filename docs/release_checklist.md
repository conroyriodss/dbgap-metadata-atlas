# Initial public-release checklist

## Human review before pressing Publish

- Confirm the intended GitHub owner, repository name and public visibility.
- Confirm authority to release the source and documentation and determine the licensing position.
  Add an approved LICENSE/NOTICE before advertising the project as open source; do not assume
  federal affiliation resolves ownership in all components.
- Review the explicit public file list. It should contain code/docs, not your Drive analysis folder.
- Review notebook source and markdown for embedded private values. Output stripping and regex
  checks are not a complete secrets/privacy review.
- Confirm authorship/attribution in CITATION.cff. No DOI or official NIH endorsement is assumed.
- Read the limitations: passing code tests is not proof of verified reuse, trial direction, causal
  platform effects or financial attribution.

## After initial publication

- Inspect the actual repository commit and Actions results; do not infer CI passed from upload success.
- Narrow/revoke the bootstrap token. Future edits should use only the intended repository's permissions.
- Review optional Pages content before enabling it. The supplied landing page contains no real results.
- Use the ten issue seeds as proposals; set priorities deliberately rather than treating the suggested
  ordering as agreed research governance.
- Configure branch protection/rules and required reviews under the account's applicable policy.
  The publisher does not change these administrative settings.
- Create a tagged code release only after reviewing code, license, attribution and actual validation.
  Keep its code tag/commit separate from any later approved data snapshot.
