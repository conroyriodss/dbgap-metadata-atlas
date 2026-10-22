# Workflow and boundaries

```text
Public metadata endpoints / explicit administrative inputs
               |
               v
01_collect (A): cache, coverage, source bytes/hashes, joins and base rollups
               |
               v
02_analyze (B): descriptive tables, semantics, figures, manifest, HTML explorer
               |
               v
03_slides (C): verify B inputs/outputs; render fourteen slides
               |
               v
Local review -> separately approved release assets (not automatic)
```

A owns FHIR, approved-requester records, counts, study pages, SSTR, PubMed, iCite,
ClinicalTrials.gov, RePORTER, Authorized Access fields, public attribution, FTP chronology,
and semantic-source retrieval. Some canonical joins and existing base funding/iCite rollups
remain in A to preserve the established data contract.

B owns local descriptive analyses, figure generation, independent-source semantic profiles,
assay-label crosswalks, and literature-method companions. Its optional graph block is the current
interactive implementation. Do not run an older standalone explorer in addition unless that is
an intentional comparison. C does not recollect sources or silently fit a different model.

## Canonicalization of this repository

Only the latest repaired A/B/C attachments were adopted. Older `_Refined`, `_Semantic`, and
`_Fixed` files are not alternative executable entry points here. Stable names replace filename
versioning; Git commits provide future history. Packaging adds a short introductory markdown
cell and removes execution/editor metadata. No code cell, field name, checkpoint layout, or
scientific transformation was changed. Exact original filenames and hashes remain in provenance.

Historical standalone catalog/gap-audit notebooks are not bundled as competing collectors.
Their evidence lessons and the current integrated semantic workflow are documented instead.
Full pre-repository chat history is not reconstructed as fake Git commits.

## Repository versus workspace

`notebooks/`, `scripts/`, `docs/`, `tests/`, and `provenance/` are public source artifacts.
`DRIVE_ROOT` is a separate, private-by-default working directory. `.gitignore` and the publisher's
explicit file list reinforce that boundary; neither establishes source-data redistribution rights.
