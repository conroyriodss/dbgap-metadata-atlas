# Semantic profiles and assay harmonization

## MeSH evidence lanes

A collects complete native study-page MeSH sections when available, retains original/FHIR
annotations, and collects trial condition terms independently. Intervention terms and registry
ancestors remain separate. Source identity, version, text, fetch time and response hash are retained.

B resolves against a fixed-year MeSH snapshot. Display the most-specific supported descriptors:
a native child descriptor can supersede a redundant parent in the display, but evidence is never
deleted. Neoplasms alone does not justify a narrower cancer subtype. A title-derived candidate
belongs in a separate review lane and is excluded by default (`SEMANTIC_INCLUDE_REVIEWED=False`).

Dataset-trial comparisons distinguish exact descriptor identity, directional broader/narrower
relationships, common-ancestor context, broad fallback, no supported match, and unavailable
annotations/vocabulary. Preserve polyhierarchy and actual tree paths. Independent source terms
are never copied across a relation to manufacture agreement. Broad common ancestry cannot
validate an NCT reference.

Profile weights and ancestor decay are exploratory. This is conceptually related to semantic
fingerprinting, **not the official NIH RCDC process, category definitions, weights or adjudication**.
A controlled mapping study and blind reference labels are required before classification claims.

## Assay evidence

Preserve WGS, WXS/WES, RNA-seq, explicitly single-cell/nucleus assays, miRNA-seq, chromatin assays,
methylation strategies, arrays, amplification and derived products. Do not translate generic
DNA-seq to WGS, RNA expression tables to raw RNA-seq, or WGA to sequencing.

Map OBI classes only when a supported class/label/synonym resolves in the saved ontology. Keep
broad local display families explicit. Unmapped values retain their original spelling and source.
The reporting parent and owning child remain distinct; repeated SSTR reports do not create new
samples. Current modality by discovery cohort does not date when that modality was submitted.

## Explorer

B's optional explorer supports pan/zoom, node movement, selected-route highlighting, source
links, facets and reset. The focal-study neighborhood is not a directional reuse relationship.
Project -> study -> NCT routes often compress publication-mediated links; they do not establish
grant-funded data generation followed by a trial. Exported HTML is not automatically safe for
public distribution merely because it renders aggregate graphics on its initial screen.
