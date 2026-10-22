# Drive workspace and reversible cleanup

The separately supplied **Manage_dbGaP_Drive_GitHub_Colab.ipynb** mounts Drive and uses
Drive API v3 folder IDs. Its code-only documentation seed is embedded and SHA-256 pinned,
so there is no ZIP-upload step. Private folder IDs belong in the local manager settings,
not in this repository. Scientific A/B/C code is not executed or rewritten by the manager.
The reusable implementation is `scripts/drive_workspace.py`.

## One preview, separate write operations

The five cells are: settings; mount/authenticate/inventory; prepare publication preview;
optional GitHub publication; optional archive or restore. Default **Run all** is read-only
with respect to Drive cloud files and GitHub. It writes only ephemeral Colab preview files.
Mounting/authentication still require Google consent. The preview does not read the GitHub
secret. Publication reads exactly the Colab secret configured as `GITHUB`.

The Drive token and GitHub token are different credentials. A GitHub personal access token
is required for the REST publisher; an SSH private key is not a substitute. No credential
is printed, written into a source notebook, put in a URL, or committed to GitHub.

## Source selection

Data folder inventory lists immediate children only. Notebook folder traversal is bounded
and excludes archive/cache/output directories. Shortcuts inside the folders are inventoried
but not followed. A shortcut explicitly supplied as the workspace folder ID is resolved.

A/B/C selection prefers recognized current filenames. Identical ordered code cells can
identify renamed copies of the adopted notebooks. When preferred files contain different
code, the manager requires explicit `NOTEBOOK_FILE_IDS`. It never equates most recently
modified with most scientifically current. Unknown newer versions remain review candidates.

Notebook outputs and execution/editor metadata are stripped only in publication copies.
The original Drive notebooks, their outputs, and all data structures are untouched. Private
selection reports retain Drive IDs, raw-byte hashes and code hashes. Public provenance retains
prepared/code hashes but not Drive folder IDs, file IDs, paths or inventory contents.

## Publication

The seed retains the public-file allowlist, project marker, checks, documentation and tests.
Only selected sanitized A/B/C plus code/documentation are sent to GitHub. Tables, source
responses, caches, checkpoints, decks, graph HTML, and this private workspace inventory do
not enter the payload. The same source-code/markdown payload is stable across repeated
previews; saving execution outputs alone does not make a new public code version.

Set `PUBLISH=True` and `PUBLIC_RELEASE_REVIEWED=True` and type the target-specific confirmation
only after reviewing the public inventory and licensing/release position. Existing project
repositories receive a review branch/PR; unrelated populated repositories are refused.
No force push, visibility change or deletion occurs. See [publishing](publishing.md) for
permission requirements. Successful API publication is not proof that hosted CI passed.

## Cleanup

Cleanup reorganizes selected code/report files; **it does not free storage**. No delete,
trash, reset, data deduplication, or cache cleanup endpoint exists in this manager.

The plan protects all scientific table and structured-data extensions, provenance/control
files, current A/B/C notebooks, all directories/shortcuts, and literal dependencies found
in selected source code. Dynamic references may be missed: review before archiving exports.
Unrecognized files are kept. Different notebook versions are not presumed obsolete.

`SUGGEST_ARCHIVE` is limited to same-code notebook copies and numbered project-file copies
matching an unnumbered original. The latter are verified by SHA-256 before any move;
Drive MD5 is only a cheap candidate screen. Code-identical notebooks can still differ in
markdown or outputs; their full original files remain in the archive. `REVIEW_VERSION`
and `REVIEW_EXPORT` require explicit file IDs. Moving old distinct revisions is reversible,
but their code is not automatically asserted to be superseded by the current notebook.

`CLEANUP_MODE='archive'` plus either `ARCHIVE_SUGGESTED_COPIES=True` or an explicit
`ARCHIVE_FILE_IDS` list builds the final plan. It then requires a count-and-hash-specific
confirmation. Stop editing/collecting while applying cleanup. Changed files are refused.

Each archive folder is newly created **inside that file's original parent**, within the
same Drive. A private journal folder is newly created under the user's My Drive root;
this avoids putting cross-folder private inventory details into a shared source folder.
A move intention is durably recorded before each move, followed by a parent/content check.
Google re-evaluates inherited ACLs on a move; the manager never changes permissions itself.
Do not apply cleanup in a folder whose sharing you do not understand.

For recovery, set `CLEANUP_MODE='restore'`, enter `RESTORE_JOURNAL_ID`, and type the journal-
specific confirmation. Restores refuse changed content, unexpected parents, out-of-scope
folders or filename conflicts. No existing file is overwritten. If interrupted, inspect
both the journal and current parents before reapplying. A partial operation is not rolled
back silently; pending/move-intent entries are recoverable by checking actual parent IDs.
The journal is preserved after restore. Historic sharing permissions are not recreated.

## Mounted paths

The manager resolves My Drive ancestry through IDs and checks ambiguous sibling names.
A display name is not a folder ID and not an assured filesystem path. It prints a mounted
path only when the path can be established and exists. Shared-with-me folders and some
shared-drive layouts can be API-accessible without a resolvable mounted path. In that case,
publishing/inventory/cleanup still work by ID; use a verified mounted shortcut/path for
running A/B/C. The manager does not create a lookalike folder or copy the corpus.

## Validation boundary

Tests use an in-memory Drive substitute and temporary local notebooks, not production Drive
or live permissions. They cover selection, scope, no-write preview, changed-file checks,
archiving, restore and privacy of the public payload. They do not validate Drive OAuth,
real folder ACL inheritance, source-data science, or GitHub hosted Actions/Pages.

## Official implementation references

- https://research.google.com/colaboratory/faq.html
- https://github.com/googlecolab/colabtools/blob/main/google/colab/userdata.py
- https://developers.google.com/workspace/drive/api/guides/search-files
- https://developers.google.com/workspace/drive/api/guides/folder
- https://developers.google.com/workspace/drive/api/guides/manage-sharing
- https://developers.google.com/workspace/drive/api/reference/rest/v3/files

Documentation checked October 21, 2026. Runtime permissions and service behavior still need
verification in the authorized Colab session.


## Large-folder and interrupted-run repair

The original manager applied its 150-notebook limit before filtering by project name.
The repaired manager counts only relevant A/B/C project notebooks and explicit in-scope
file selections. Unrelated notebook contents are never downloaded. Metadata inventory
limits (12,000 entries / 100 folders) remain in force; an incomplete inventory is not
authority to publish or reorganize files.

Explicit file IDs have priority, then the complete preferred-name pools, then older project
copies for optional cleanup. When a complete competing pool cannot fit the inspection
budget, that role remains unselected rather than choosing from a truncated list. Deferred
project notebooks remain KEEP. Use notebook_candidates.csv for file IDs and inspection status.

Every cell-2 rerun clears older publication/cleanup readiness. Cell 3 skips when inventory
failed, and cannot raise the earlier cascading SELECTION_ERRORS NameError. Cleanup prints
that no actionable plan exists when selection is incomplete; it does not claim a ZIP was
created. All publication/move defaults remain off. Folder/selection changes after preview
require reinspection; toggling publication on does not itself invalidate a valid preview.

The httplib2 per-request-timeout warning is not the notebook-count error. The existing
Drive transport already uses httplib2.Http(timeout=45); Google authentication helpers may
still emit the advisory. It is not suppressed, and no force-remount is required.
