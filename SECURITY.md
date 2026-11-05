# Security policy

Surroundflix runs inside netflix.com and ships an unsigned macOS app, so
its own security matters. Please report anything that looks off.

## Reporting a vulnerability

Open a private advisory at
[github.com/AnzouK/surroundflix/security/advisories/new](https://github.com/AnzouK/surroundflix/security/advisories/new).
Only the maintainer sees it, and with your approval it becomes a public
advisory crediting you once the fix ships.

Please don't open a public issue for an unpatched problem.

## In scope

- The page hook, content script and popup (`src/surroundflix/templates/`):
  anything that lets a web page, another extension or Netflix's responses
  run code, inject HTML, or reach the extension's storage or messages.
- The app window and its update check: anything that makes it open or
  display content that doesn't come from this repository's releases.
- The Python tool and the workflows: fetching from unexpected hosts,
  reading local files, command injection, leaked tokens.
- Release files: a way to get a modified .dmg, userscript or zip past the
  published checksums or build attestations.

## Out of scope

- Netflix detecting or blocking Surroundflix. That's a compatibility issue.
- The app being unsigned: it is, and the README says so. Gatekeeper
  warnings are expected until the app is signed with an Apple Developer ID.
- Safari decoding Atmos to 5.1, or Chrome lacking Dolby: platform limits.

## What protects users today

- The extension asks for one permission, `storage`, and runs only on
  `www.netflix.com`. It contacts no server.
- Data read from the page (the popup's choices passed through `<html>`
  attributes, Netflix's audio and video lists, title features) is treated
  as untrusted: only known values are used, and text is always inserted
  with `textContent`, never as HTML.
- The app only contacts `api.github.com` for updates, and only links to
  this repository's releases.
- `tests/test_security.py` checks all of the above on every push, and
  `security.yml` runs Bandit, pip-audit, gitleaks and (on the public repo)
  CodeQL.
- Releases come with `SHA256SUMS.txt` and, on the public repo, build
  provenance attestations:

  ```bash
  shasum -a 256 -c SHA256SUMS.txt
  gh attestation verify Surroundflix.dmg --repo AnzouK/surroundflix
  ```

## Supported versions

Only the latest release gets fixes.
