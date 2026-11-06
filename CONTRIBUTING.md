# Contributing

Bug reports, fixes and translations are welcome. For a larger change, open
an issue first so we can agree on the approach.

## Setup

```bash
git clone https://github.com/AnzouK/surroundflix.git
cd surroundflix
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Node.js is needed for the tests that run the page hook, and the full Xcode
for `surroundflix dmg` (see [Building from source](README.md#building-from-source)).

## Workflow

1. Branch from an up-to-date `main`: `feat/…`, `fix/…`, `docs/…`, `ci/…`.
2. Commit with [Conventional Commits](https://www.conventionalcommits.org/):
   `feat(video): add a codec menu`, `fix(popup): …`, `docs(readme): …`,
   `test: …`, `ci: …`, `chore(release): v1.1.0`. Lowercase, imperative, no
   final period.
3. Add an entry under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) for
   anything a user would notice.
4. Open a pull request and fill in its checklist. `main` only accepts
   pull requests with green CI; merge with **Rebase and merge**.

Before pushing:

```bash
ruff check src tests scripts && ruff format --check src tests scripts && pytest
surroundflix build && npx eslint dist
```

After changing the app window, the popup or their English text, run
`python scripts/make_showcase.py` to redraw `design/showcase.svg` (a test
fails until you do).

## Translations

All interface text lives in `src/surroundflix/templates/i18n.json`. To add
a language, copy the `en` block, translate it, add its name under
`languages`, and run `pytest`: a test checks that no string is missing.

## Releases

Versions follow [Semantic Versioning](https://semver.org/): `fix` commits
make a patch release, `feat` commits a minor one, breaking changes a major
one. A release takes two steps, so the tag lands on `main` after CI:

```bash
python3 scripts/release.py prepare 1.1.0   # on an up-to-date main
# open the release/v1.1.0 pull request, merge it once CI is green, then:
git checkout main && git pull && python3 scripts/release.py tag
```

`prepare` turns `[Unreleased]` into the new version's section, dated with
your computer's date, sets the version in `pyproject.toml` and
`src/surroundflix/__init__.py`, commits on a `release/v…` branch and pushes
it. `tag` checks that the section of the code's version is dated, then tags
`main` and pushes the tag. Both accept `--dry-run`.

The tag starts `.github/workflows/release.yml`: it runs the whole CI on the
tagged commit, builds the .dmg on a macOS runner, the userscript and the
Chrome zip, writes `SHA256SUMS.txt`, and publishes the release with the
CHANGELOG section and the install guide (`.github/release-install.md`) as
notes.

## Security

Please report vulnerabilities privately, as described in
[SECURITY.md](SECURITY.md), not in a public issue.
