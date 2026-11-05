## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## Checklist

- [ ] `ruff check src tests scripts`, `ruff format --check src tests scripts` and `pytest` pass locally
- [ ] JavaScript changes: `surroundflix build` then `npx eslint dist` reports no errors
- [ ] New or changed behaviour has a test (offline, no Netflix account needed)
- [ ] New interface text is added to every language in `templates/i18n.json`
- [ ] App window or popup changed: `python scripts/make_showcase.py` run
- [ ] No new extension permission, host or network destination (or it's explained here and in PRIVACY.md)
- [ ] Entry added to `CHANGELOG.md` under "Unreleased"
- [ ] No secrets or personal data in the diff or screenshots
