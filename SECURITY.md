# Security and sensitive content

Never open a public issue containing a real token, controlled data, participant information,
unreviewed requester records, or a complete sensitive log. Revoke exposed credentials first.
Contact the maintainer using an independently verified appropriate channel; the package does
not invent a private contact address. If repository private vulnerability reporting is enabled,
use that facility. Do not assume ordinary issues are private.

Keep tokens in Colab Secrets or a hidden prompt, scoped to the intended owner/repository.
The publisher sends them only to GitHub's API, does not store them in git URLs/config, and does
not follow redirects with authentication. It never requires a dbGaP controlled-data credential.
Disconnect/delete token access after an initial bootstrap and issue a narrowly scoped token for
routine maintenance. Organization policies may require approvals.

Credential-pattern checks do not find all secrets. Review notebook source/markdown as well as
outputs. Dependency pins are a reproducibility baseline, not an assurance that vulnerabilities
are absent. Update dependencies through reviewed pull requests and rerun tests.
