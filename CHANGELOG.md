# Changelog

All notable changes to Surroundflix are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
`python3 scripts/release.py prepare` dates a section on the day you release
it, and `python3 scripts/release.py tag` tags main once that is merged; the
release workflow publishes the section as the release notes. New entries go
under [Unreleased].

## [Unreleased]

### Fixed

- A change made in the popup now applies to the next title without reloading
  the page: Netflix's own request is no longer edited in place.
- Badges update as soon as the audio choice changes, and a title card no
  longer borrows the badges of the title open in the modal.
- "Always the best" picks the highest resolution first, then the highest
  bitrate at it (an 8 Mb/s 1080p stream no longer beats 2160p).
- Quality modes still apply when some of Netflix's streams have no size.
- A stored codec that can't be decoded any more is reset to Automatic.
- The app window no longer reloads on focus once the extension is on, so an
  update result stays on screen.

### Security

- The update link is checked after the browser resolves the path (`..`,
  `%2e%2e`), and `surroundflix check` validates every redirect.
- Oversized or implausible values in the status written on the page are
  ignored by the popup.
- Releases run the full CI first and are refused unless the tag is on
  `main`; GitHub Actions are pinned by commit.

## [1.0.0] - 2026-11-06

Initial release. Surroundflix asks Netflix for its Dolby 5.1 and Atmos
tracks in Safari, so macOS plays them with Spatial Audio on AirPods, and
gives you control over the video Netflix sends.

### Features

- **Dolby 5.1 and Atmos in Safari.** Netflix's Dolby Digital Plus 5.1,
  5.1 HQ and Atmos profiles are added to the player's request, without
  modifying Netflix's code. Safari plays Atmos as its 5.1 bed, shown as
  "Multichannel" with Spatial Audio and head tracking. A "5.1 only" choice
  leaves Atmos out if a title won't start.
- **AAC 5.1 in Chrome.** Chrome has no Dolby decoder, so its build asks for
  Netflix's AAC 5.1 track on titles that have one.
- **Video quality.** Automatic, At least 720p, 1080p or 4K, Always the
  best (highest video and audio bitrate), or Data saver (720p max).
- **Codec choice.** Automatic, H.264 (any profile, Main or High), HEVC
  with HDR10 and Dolby Vision (Safari), AV1, or VP9 (Chrome). H.264 Main
  also asks for Netflix's `-prk-qc` encodes, often the highest bitrate.
  Codecs the browser can't decode aren't offered.
- **Title badges.** The Dolby Atmos, 5.1 and Ultra HD 4K badges Netflix
  hides on its web pages are shown again, when the browser can play them.
- **Toolbar popup.** The audio, quality and codec menus, a line explaining
  each choice, and what Netflix sent for the current tab: audio, video
  resolution, codec, HDR format, bitrate and the resolutions offered.
- **macOS app.** A resizable window with the extension's status, setup
  steps, a shortcut to Safari's settings and an update check, in English,
  French and Portuguese (Portugal, Brazil and Angola).
- **Userscript.** For the free Userscripts app, with automatic updates and
  no unsigned-extension setting; quality and codec are set when building it.

### Security and maintenance

- One extension permission (`storage`), runs only on `www.netflix.com`,
  contacts no server; page data is treated as untrusted.
- Security tests, Bandit, pip-audit, gitleaks and CodeQL in CI.
- Releases built by GitHub Actions with `SHA256SUMS.txt` and build
  provenance attestations.
- A daily check of Netflix's player opens an issue if the profiles change.
