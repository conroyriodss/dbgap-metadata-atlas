# Units, denominators, and interpretation

| Unit or measure | Operational meaning | Not established |
|---|---|---|
| Root accession | Canonical `phs...` record in the assembled universe | Independent cohort, unique participant pool, complete deposited asset |
| `v` / `p` / consent label | Actual recorded data version, participant set, and study-specific consent identity | Complete release history; universal code-to-GRU mapping |
| DAR rows | Captured accession-requester records | Unique scientific projects, all applications, downloads, execution or reuse |
| Root-WLID pair | Distinct observed root/requester-identifier relationship | Adjudicated unique person or independent analysis |
| Exact requester-set family | Sensitivity grouping based on identical observed sets | Verified biological family; elimination of partial overlap |
| Publication link | Source-recorded accession-PMID association | Secondary reuse, use of the current version, or independence from generators |
| Distinct retrieved PMID | Unique linked identifier with successful PubMed retrieval under the declared rule | Complete bibliography for that study |
| Defined RCR | Nonmissing publication-level iCite RCR | Quality, benefit caused by sharing, patient impact |
| NCT link | Explicit identifier reference in saved metadata, potentially in linked publication text | Originating trial or downstream translation |
| NIH acknowledgement | Explicit study-section acknowledgement evidence | Every NIH-supported study |
| RePORTER association | Paper-project relationship reported by RePORTER | Cost of generating the dataset or attributable ROI |
| Platform listing | Explicit source-recorded cross-listing and consent/version context | Full physical replication or platform-mediated use |
| Native MeSH | Independently recorded source annotation | Human-adjudicated truth, official RCDC categorization |
| Hierarchical bridge | Explicit broader/narrower/common-ancestor relation | Exact equivalence or validation of the dataset-trial link |
| Assay family | Transparent crosswalk of reported labels, OBI mapping when supported | Harmonized participant data, pipelines, units or sample counts |
| FTP timing | Earliest surviving qualifying public artifact under the collector rule | Accession minting, registration, actual availability or first release |

Retain positive, supported-negative, unobserved, unresolved, failed, and stale states separately.
All-root observed-positive shares and known-source prevalences answer different questions.
RCR calculations count each PMID once for corpus summaries; accession-weighted/family views
must identify their weighting. Missing RCR is not zero.

Ranked contributor bars count root-PI attribution pairs; a co-attributed root contributes to
multiple labels. Current public PI attribution is not a historical submission log. Requester
names/organizations are proxies; preserve uncertainty and do not report them as verified identities.

The four DAR/publication categories are cross-sectional intersections, not a sequential funnel.
Pre-first-DAR publication frequency does not bound the fraction of all papers representing reuse.
The most-recent observed metadata can postdate the outcomes and cannot be treated automatically
as a baseline covariate.
