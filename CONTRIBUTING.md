# Contributing

Use a branch and pull request. State the analytical question, source snapshot, changed estimand
or data contract, tests executed, and any remaining uncertainty. Keep notebook source clean;
submit no caches, execution outputs, credentials or unreviewed person-level records.

A owns acquisition; B owns local analysis; C owns rendering. Preserve established table/column
and checkpoint structures unless an explicit migration is proposed. Avoid another competing
notebook version in the default workflow. Add synthetic regression cases for every repaired bug.
Never present a fixture or LLM-generated label as empirical validation.

Run `python scripts/check_repo.py` and `python -m unittest discover -s tests -v`.
After reviewed edits, run `python scripts/refresh_package_manifest.py --clean-notebooks`; review its file list.
For substantive B/C changes also run the synthetic smoke test and inspect the real produced
figures locally. CI is not a source API, license, identity-resolution, or causal-inference audit.

Research questions are in docs/research_questions.md. Do not change a prespecified hypothesis
or frozen result after seeing its validation outcome without creating a clearly labeled new version.
