# Public publication boundary

## Initial release: code and documentation only

Allowed by the bundled publisher: explicitly listed notebooks with outputs stripped, Python source,
methodological documentation, text-only synthetic tests, input contracts, and code provenance.

Excluded: source/derived Parquet and real CSV/JSONL, raw public pages/API caches, requester-level
records, personal contact fields, research-use text, project dossiers, executed notebook outputs,
collected ontology payloads, production manifests/logs containing identifiers, the populated graph,
and complete HTML/PPTX decks. Even publicly accessible upstream metadata are not automatically
approved for bulk redistribution or repackaging.

No controlled participant-level genomic or phenotype data should be uploaded to this repository
or entered into this Colab workflow. It is a public-metadata analysis workflow, not a controlled-data
access client. Existing authorization and data-use restrictions remain applicable.

## Why reports are excluded by default

The supplied presentation stores detailed data and provenance in HTML notes/embedded JSON.
A slide screenshot can look aggregate while its HTML includes investigator labels, institution
strings, paths and record-level mappings. Graph downloads can expose everything bundled, not
only the currently filtered view. Notebook output clearing does not remove hardcoded source
literals or markdown; inspect those separately.

The publisher's allowlist, path checks and credential regexes are safeguards, not a guarantee of
privacy, copyright clearance, confidentiality or scientific correctness. `.gitignore` does not remove
files already committed; deletion of a working-tree file does not erase Git history.

## Later approved analytical releases

Prepare a separate artifact package from an explicit column/file allowlist. Review hidden content,
small groups and identity fields; specify rights, provenance, cutoff, known limitations and
reproducibility access. Prefer reviewed aggregate outputs and a separate approved archival store
for large source snapshots. Do not silently enable Pages for an unreviewed deck.

Select an institutional/public release path and licensing position with the appropriate authority.
The presence of NIH affiliation or public government sources does not determine rights in every
contribution, third-party text, software dependency, figure or data field.
