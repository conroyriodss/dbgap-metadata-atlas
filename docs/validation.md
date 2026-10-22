# Validation status

## What was preserved
The canonical A/B/C scientific code cells are identical to the latest repaired attachments.
Repository metadata/output cleaning is separately documented and testable by per-cell hashes.

## Reported production run
The maintainer supplied 32 passing structural checks, no failed structural checks, and 37 failed
source checks with prior successful rows preserved where present. Counts and their origin are in
`provenance/reported_run_context.json`. These reports were not rerun for repository packaging.
A successful join or numeric-range check does not validate the meaning or completeness of a link.

## Tests for this repository package
`provenance/packaging_test_report.json` records only the checks actually executed during this
packaging session. The repository has a standard-library test suite for publishing and notebook
hygiene, plus an explicit CSV synthetic B/C smoke test. CI does not contact scientific APIs.
The test report distinguishes executed packaging checks from historical test claims in the thread.

## Remaining gaps
Production Drive execution, live collection, original administrative-data replication, scientific
publication provenance, investigator identities, true release histories, patient impact, source-data
redistribution clearance and real GitHub publication are not validated by these packaging tests.
PyArrow coverage, complete semantic fixtures and PowerPoint rendering are reported according to
what this session actually exercised; do not infer them from older reports.

Potential parser/ascertainment issues are research work, not reasons to label a dataset unused.
Generated diagrams and LLM text are candidates for inspection, never independent evidence.
