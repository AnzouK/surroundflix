# Changelog

All notable changes to Surroundflix. The release workflow publishes the
section matching the tag as the release notes.

## [Unreleased]

## [0.1.0]

First version, not released publicly.

### Added

- Page hook that adds Netflix's Dolby Digital Plus 5.1, 5.1 HQ and Atmos
  profiles to the player's request, without modifying Netflix's code.
- Safari extension wrapped in a macOS app (.dmg), and a Safari userscript
  with automatic updates.
- Experimental Chrome extension asking for AAC 5.1, since Chrome has no
  Dolby decoder.
- Toolbar popup: choice between "5.1 and Atmos" and "5.1 only", and the
  best audio Netflix sent for the current tab.
- App window with extension status, setup steps, update check and a
  language menu (English, French, Portuguese with Portugal, Brazil and
  Angola variants from the system language).
- Daily check of Netflix's player in GitHub Actions.
- Security tests, Bandit, pip-audit, gitleaks and CodeQL in CI; release
  checksums and build provenance.
