# Publish from Colab

## Initial bootstrap

The prepared download contains a code-only ZIP and a three-cell publishing notebook. The
external bootstrap notebook pins the SHA-256 of that ZIP. Open it in Colab, upload the ZIP,
review the file inventory, and run its publishing cell only after the release/licensing review.
It does not mount or scan Drive. The notebook never collects scientific data.

Suggested target: `conroyriodss/dbgap-metadata-atlas`. This is a proposed target until the live publisher
returns a repository URL and commit. Repository ownership can be an authorized personal
account or organization; creating an organizational repository requires that account's permission.

### Settings

```python
GITHUB_OWNER = "conroyriodss"
REPOSITORY = "dbgap-metadata-atlas"
VISIBILITY = "public"
PUBLISH = False
PUBLIC_RELEASE_REVIEWED = False
ENABLE_PAGES = False
SEED_QUESTIONS = False
```

Preview needs no credentials and makes no network requests. For publication, set `PUBLISH=True`
and `PUBLIC_RELEASE_REVIEWED=True` only after reviewing the exact payload and rights/licensing
position. The cell asks you to type `PUBLISH conroyriodss/dbgap-metadata-atlas PUBLIC`. The code does not
choose a license or authorize institutional release on your behalf.

### GitHub authentication

Use a short-lived fine-grained personal access token for the intended resource owner. Store it
as Colab secret `GITHUB`, grant notebook access, or use the hidden prompt. Never paste
it into notebook source, a URL, an issue, or a shared log.

Required permissions depend on the route:

| Operation | Permission |
|---|---|
| Push the selected code files | Contents: read/write |
| Include the CI workflow | Workflows: read/write |
| Create a new repository through the API | Repository creation: write OR Administration: write, under current GitHub docs |
| Open a review PR on later updates | Pull requests: read/write |
| Seed the optional ten question issues | Issues: read/write |
| Enable optional documentation Pages | Pages: write and the configuration permissions required by the endpoint |

For the narrowest routine token, first create an empty public repository through GitHub's UI,
then give a token access to **only that repository** with Contents and Workflows permissions
(and Pull requests for automated PRs). A token limited to selected existing repositories cannot
automatically include a repository that does not yet exist. For API creation, the token needs
access to the new repository as well as creation permission; account/organization policy may
prevent this. After bootstrap, replace broad access with a selected-repository token.

The publisher surfaces accepted-permission headers on failures without echoing credential values.
It cannot grant itself account privileges or bypass an organization's approval policy.

### What publication does

1. Reads only `public_files.json`, sanitizes notebook output/editor metadata, and performs code,
   path and credential-pattern checks. Scientific notebook code is not rewritten.
2. Creates a missing repository if enabled, or checks the identity marker of an existing one.
   An unmarked populated repository is refused (a README/LICENSE-only starter is allowed).
3. Compares file blobs, uploads only changed declared files and prepares one Git commit after
   a new repository's initial bootstrap. Unlisted remote files are preserved, never deleted.
4. A new or empty repository receives its first package on its default branch. A populated
   repository receives a review branch and optionally a PR. There is no force push.
5. Prints the actual repository, branch, commit and payload hash. A failure can leave an empty
   repository, unreferenced objects, or a review branch; inspect and rerun rather than resetting.

An unchanged repeat does not create another commit. A repeated run with an unmerged review
branch may propose another review branch; inspect/merge the existing PR first.

## Daily scientific work is not a publishing operation

Run A/B/C with data on Drive. Do not automatically push the Drive analysis directory after every
run. Save reviewed notebook-source changes to your Git checkout or specify exact notebook
updates in the publisher. API keys and private configuration belong in your working copy/secrets.

After reviewing edits, run:

```bash
python scripts/check_repo.py
python -m unittest discover -s tests -v
python scripts/refresh_package_manifest.py --clean-notebooks
python scripts/publish_github.py --owner conroyriodss --repo dbgap-metadata-atlas
# This is still a preview. Add --publish --reviewed only after review.
```

## Optional website and research issues

`ENABLE_PAGES=True` configures a public documentation landing page from the default branch's
`/docs` directory. It does not publish production figures or populated explorers. For manual setup,
choose Settings -> Pages -> Deploy from a branch -> default branch -> /docs. Pages may take
time to deploy; configuration success is not confirmation that the website is live.

`SEED_QUESTIONS=True` creates ten unprioritized question issues, using embedded stable markers
to avoid duplicates. Neither toggles labels as confirmed findings nor assigns priorities/owners.

## References (checked for this implementation, 2026-10-21)

- https://docs.github.com/en/rest/repos/repos#create-a-repository-for-the-authenticated-user
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
- https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens
- https://docs.github.com/en/rest/git/refs
- https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- https://research.google.com/colaboratory/faq.html

The bundled REST client explicitly sets API version `2026-03-10`; requirements can change, so
check the endpoint's current permissions and the actual response when troubleshooting.
