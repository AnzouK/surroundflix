# Changelog

All notable changes to Surroundflix. The release workflow publishes the
section matching the tag as the release notes.

## [Unreleased]

### Added

- Video quality menu in the toolbar popup: Automatic (default), At least
  720p, At least 1080p, At least 4K, Always the best, Data saver (720p max). Streams
  outside the choice are removed from the list Netflix's player picks from.
  "Always the best" also keeps the highest bitrate of each audio format.
  The popup shows the video Netflix sent and the range it offers.
  Userscript: `surroundflix build --video-quality <mode>`.
- Dolby Atmos, 5.1 and Ultra HD 4K badges on title pages. Netflix sends
  these features for every title but its web pages hide them; they are
  shown when the browser can play them (4K and Atmos in Safari, 5.1 in
  Chrome).

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
