# Changelog

All notable changes to Surroundflix are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.0] - 2026-11-12

### Added

- The toolbar button shows "ATM" or "5.1" while the player is open on a
  title Netflix sent with Atmos or 5.1.
- "On this tab" in the popup says when Netflix didn't send the quality or
  codec you chose.
- The popup shows the version of Surroundflix.

### Fixed

- The popup scrolls when it is taller than Safari allows, instead of being
  cut off.
- The popup finds its tab in a Safari web app (Netflix added to the Dock),
  so "On this tab" and "Reload Netflix to apply now" work there.
- "On this tab" only describes the title open in the player. Trailers,
  previews and the next episode Netflix loads in advance no longer show up
  there, and nothing is shown outside the player.
- `surroundflix check` resumes a download that is cut off instead of
  starting over.

## [1.2.0] - 2026-11-09

### Added

- "Netflix default" in the popup's audio choices adds no audio profile, to
  check whether Surroundflix is why a title won't play. Quality and codec
  still apply.

### Fixed

- `surroundflix check` handles escaped slashes in the playercore URL on
  Netflix's homepage.
- `surroundflix check` also watches the H.264 Main profiles the extension
  adds.

## [1.1.0] - 2026-11-07

### Added

- "Copy debug info" in the popup copies your settings, browser version and
  what Netflix sent, ready to paste into a bug report.
- After a change in the popup, "Reload Netflix to apply now" reloads the
  Netflix tab so the new settings apply without waiting for the next title.

### Fixed

- Codec and quality changes in the popup apply to the next title in every
  case, without reloading the page.
- "On this tab" in the popup picks the highest resolution before comparing
  bitrates.
- Badges show on a title's own page (`/title/...`), and the "More Like This"
  cards in the details window no longer get the badges of the open title.
- A card that React reuses for a title without badge data no longer keeps
  the previous title's badges.
- `surroundflix xcode` passes `--video-quality` and `--video-codec` to the
  userscript it builds.
- `surroundflix check` retries a download that is cut off before giving up.
- The app's update check ignores release tags that aren't plain versions.

## [1.0.1] - 2026-11-06

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
