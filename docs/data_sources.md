# Data sources and acquisition contracts

These are the source families used by the adopted notebooks. Endpoints below document current
code, not an assertion that every endpoint was live-tested during repository packaging.

| Source | Saved artifacts (principal stems) | Source/use limit |
|---|---|---|
| dbGaP FHIR ResearchStudy | `dbgap_studies_raw`, `dbgap_root_accessions` | Roots, recorded versions, titles and conditions; not historical snapshots of every version |
| dbGaP public requester records | `dar_records`, `dar_fetch_checkpoint.json` | Observed authorization/requester metadata; incomplete administrative lifecycle |
| dbGaP study counts/pages | `study_counts_analysis_ready`, `study_page_metadata_analysis_ready` | Variables, documents, datasets, descriptions and explicit publication references |
| SSTR | `sstr_study_summary`, compatible analysis-ready files | Subject/sample counts, consent context and reported assay evidence; retained report != every past report |
| Authorized Access API | `dbgap_authorized_access_api_metadata` | Literal external-source labels, consent-level SRA availability, current version context |
| PubMed | `pubmed_metadata_full`, `dbgap_study_pubmed_links_full` | Identity/metadata resolution; bibliography completeness and actual reuse need validation |
| NIH iCite | `icite_rcr_metrics`, study rollups | Publication influence/translation fields; missing/provisional states retained |
| ClinicalTrials.gov v2 | `dbgap_ctgov_direct_links`, semantic trial records | Registry metadata and algorithmic condition/intervention annotations; relation role not inferred |
| NIH RePORTER | `reporter_pub_links_full`, `reporter_projects_full`, base rollups | Many-to-many project-publication links; full award cost is not dataset cost |
| Public study attribution | `dbgap_public_attribution` | Source-displayed PI/group, institution and funding sections; parser/entity-resolution review needed |
| Public FTP listings | `accession_timing_ftp_root_results` and timing outputs | Surviving-object chronology only, with exact object/path and timestamp lineage |
| NLM MeSH XML | fixed-year snapshot and parsed index under `semantic_sources/` | Vocabulary release, tree paths and independent-source resolution preserved |
| OBI | snapshot and parsed index under `semantic_sources/` | Assay class mapping only where uniquely supported by the saved ontology |
| Optional administrative records | `replication_inputs/` | Verified submission, availability, request, publication and institutional histories supplied independently |

Selected endpoint families in the code:

- `https://dbgap-api.ncbi.nlm.nih.gov/fhir/x1/ResearchStudy`
- `https://dbgap.ncbi.nlm.nih.gov/beta/api/study/{accession}/...`
- `https://clinicaltrials.gov/api/v2/studies/{NCT}`
- `https://icite.od.nih.gov/api/pubs`
- `https://api.reporter.nih.gov/v1/publications/search`
- `https://api.reporter.nih.gov/v1/projects/search`
- `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
- Public `ftp.ncbi.nlm.nih.gov/dbgap/studies` listings

For service definitions, use the [dbGaP submission guide](https://www.ncbi.nlm.nih.gov/gap/docs/submissionguide/),
[ClinicalTrials.gov API documentation](https://clinicaltrials.gov/data-api/api),
[RePORTER API documentation](https://api.reporter.nih.gov/),
[NLM MeSH downloads](https://www.nlm.nih.gov/databases/download/mesh.html), and
[OBI documentation](https://obi-ontology.org/). Do not interpret these references as blanket licenses
for redistribution of every retrieved field. Respect service limits and applicable data/source terms.

The operational flags and exact path registry are in A. Do not rebuild missing histories by
substituting current-state fields. Snapshot timestamps, record versions and source hashes must
accompany each empirical analysis.
