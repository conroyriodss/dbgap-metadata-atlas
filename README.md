# dbGaP Metadata Atlas

**A reproducible, notebook-based study of the public signals around shared biomedical data.**

This project maps dbGaP study metadata, recorded data-access-request activity, linked literature,
ClinicalTrials.gov references, NIH funding associations, semantic annotations, and relationships
with SRA, BioData Catalyst (BDC), AnVIL, and other services.

**Status: exploratory research software.** Recorded access is not executed analysis; linked
publications are not adjudicated secondary reuse; NCT mentions are not necessarily originating
trials or downstream clinical uptake. This is not an official NIH, NLM, NCBI, or NHLBI product,
a compliance assessment, a repository ranking, or an ROI evaluation.

## Start here

| Notebook | Role | Colab |
|---|---|---|
| [01_collect.ipynb](notebooks/01_collect.ipynb) | A: checkpointed public metadata collection and canonical joins | [Open](https://colab.research.google.com/github/conroyriodss/dbgap-metadata-atlas/blob/main/notebooks/01_collect.ipynb) |
| [02_analyze.ipynb](notebooks/02_analyze.ipynb) | B: descriptive analysis, semantics, literature-method companions, interactive explorer | [Open](https://colab.research.google.com/github/conroyriodss/dbgap-metadata-atlas/blob/main/notebooks/02_analyze.ipynb) |
| [03_slides.ipynb](notebooks/03_slides.ipynb) | C: current fourteen-slide HTML and PowerPoint presentation | [Open](https://colab.research.google.com/github/conroyriodss/dbgap-metadata-atlas/blob/main/notebooks/03_slides.ipynb) |

Run **A -> B -> C** with the same external folder:

```python
DRIVE_ROOT = "/content/drive/MyDrive/dbgap_analysis"
```

Keep this data folder **outside the Git checkout**. A defaults to `RUN_MODE = "reuse"`;
`check_stale` checks sources due after three calendar months, and `clean` is an intentional
archive-and-rebuild operation. Reuse can still collect missing records and due retries.
B reads saved inputs; C verifies B's manifest and renders results. No production data are
included in this repository. A first full collection can be substantial; start with your
existing cache or disable optional collections you do not need. See [Quickstart](docs/quickstart.md).

## What is included

One canonical A/B/C implementation, the integrated graph explorer, methodological documentation,
source and metric dictionaries, ten proposed research workstreams, synthetic local tests,
publication safeguards, and a preview-first GitHub publisher. The scientific code cells of the
three adopted notebooks were not changed during repository packaging; their origins and hashes
are in [source_notebooks.json](provenance/source_notebooks.json).

The latest supplied code includes the Authorized Access retry cooldown and semantic clock fix,
source-recorded versus ontology-validated MeSH, contributors versus accessors, and data-type
profiles. It retains legacy output field names for compatibility; see the glossary rather than
inferring evidentiary strength from a field named `direct` or `grant`.

## Documentation

[Workflow](docs/architecture.md) | [Data sources](docs/data_sources.md) |
[Metric definitions](docs/metrics.md) | [Semantics and assay labels](docs/semantics.md) |
[Slide guide](docs/slide_guide.md) | [Published-study comparisons](docs/published_comparisons.md) |
[Research roadmap](docs/research_questions.md) | [Validation](docs/validation.md) |
[Reproducibility](docs/reproducibility.md) | [Publication policy](docs/publication_policy.md) |
[GitHub/Colab publishing](docs/publishing.md) | [Drive workspace and reversible cleanup](docs/drive_workspace.md)

## Local checks (no source API calls)

```bash
python -m pip install -r requirements-dev.txt
python scripts/check_repo.py
python -m unittest discover -s tests -v
```

For an actual synthetic B/C pipeline run, install the analysis dependencies and run:

```bash
python -m pip install -r requirements.txt
python scripts/smoke_test.py --output /tmp/dbgap-atlas-smoke
```

The test uses made-up records labeled **SYNTHETIC**. It is a software check, not an empirical result.
It does not run A or contact any scientific source. Optional model/semantic inputs remain absent
unless a particular test supplies them.

## Publishing and reuse

The initial repository contains **code and documentation only**. Do not upload raw caches,
requester-level records, executed notebooks, the full generated HTML deck, or a populated graph
by copying the analysis folder into Git. Hidden HTML notes/JSON may contain record-level details.
See [publication policy](docs/publication_policy.md).

No project-wide license was assigned during packaging. The maintainer must determine the
applicable rights and institutional release conditions before choosing a license. Publicly
visible is not the same as open-source licensed. See [LICENSE_STATUS.md](LICENSE_STATUS.md).

For citation, use [CITATION.cff](CITATION.cff) after confirming authorship and release metadata;
report the exact commit plus the separate data snapshot identifier. No DOI has been minted.

## Scientific standards

Keep missing values separate from supported negatives. Freeze source bytes and code separately.
Use unique PMIDs for publication-level RCR; distinguish roots from study families. Preserve
actual accession/version/participant-set/consent relationships. Never substitute FTP artifact
dates for release dates, copy trial terms onto datasets, or treat an LLM's label as validation.
Already inspected patterns are exploratory; new confirmatory work needs prespecified analysis
and independent human reference labels.
