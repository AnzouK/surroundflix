<div align="center">

<img src="assets/icon.svg" width="112" alt="Surroundflix icon: five speakers around a listener">

<h1>Surroundflix</h1>

<p><strong>Netflix's Dolby 5.1 and Atmos tracks in Safari on macOS, with Spatial Audio on AirPods, plus your choice of video quality and codec.</strong></p>

<a href="https://github.com/AnzouK/surroundflix/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/AnzouK/surroundflix/ci.yml?branch=main&label=CI&logo=github" alt="CI status"></a>
<a href="https://github.com/AnzouK/surroundflix/releases"><img src="https://img.shields.io/github/v/release/AnzouK/surroundflix?include_prereleases&label=release&color=8250df" alt="Latest release"></a>
<a href="https://github.com/AnzouK/surroundflix#AGPL-3.0-1-ov-file"><img src="https://img.shields.io/badge/License-AGPL--3.0-6c8f2d" alt="License: AGPL-3.0"></a>
<img src="https://img.shields.io/badge/macOS-Safari%2016.4%2B-2f6f9f?logo=safari&logoColor=white" alt="macOS, Safari 16.4 or later">
<img src="https://img.shields.io/badge/Chrome-AAC%205.1-2f6f9f?logo=googlechrome&logoColor=white" alt="Chrome: AAC 5.1">
<img src="https://img.shields.io/badge/audio-5.1%20%C2%B7%20Atmos-de9a40" alt="Audio: 5.1 and Atmos">
<img src="https://img.shields.io/badge/interface-3%20languages-c9a227" alt="Interface in 3 languages">

<p>
<a href="#features">Features</a> &nbsp;·&nbsp;
<a href="#install">Install</a> &nbsp;·&nbsp;
<a href="#check-that-it-works">Check it works</a> &nbsp;·&nbsp;
<a href="#how-it-works">How it works</a> &nbsp;·&nbsp;
<a href="#building-from-source">Build</a> &nbsp;·&nbsp;
<a href="#credits">Credits</a>
</p>

</div>

Netflix in Safari on macOS only sends stereo, even on the Premium plan with
AirPods Pro, AirPods Max or a surround setup. Surroundflix asks Netflix for
its Dolby Digital Plus 5.1 and Atmos tracks instead, so macOS can play them
with Spatial Audio. It also lets you choose the video quality and codec,
and shows the Atmos, 5.1 and 4K badges Netflix hides on its web pages.

> [!NOTE]
> Netflix can change its player at any time; a daily check watches for
> that (see [Automatic watch](#automatic-watch)).

## What you get

| Title on Netflix | Safari | Safari + Surroundflix | Chrome | Chrome + Surroundflix |
| --- | --- | --- | --- | --- |
| Stereo only | Stereo | Stereo | Stereo | Stereo |
| 5.1 | Stereo | Dolby 5.1, "Multichannel" | Stereo | AAC 5.1 when offered |
| Dolby Atmos | Stereo | 5.1 bed of the Atmos mix, "Multichannel" | Stereo | AAC 5.1 when offered |
| Multichannel Spatial Audio on AirPods | No | Yes, with head tracking | No | No |

Safari decodes Netflix's Atmos stream (E-AC-3 JOC) down to its 5.1 bed and
hands at most six channels to macOS. That limit is in WebKit and no
extension can lift it. On AirPods, 5.1 with Spatial Audio and head tracking
is still a clear step up from stereo.

## Features

<p align="center">
  <img src="design/showcase.svg" width="720" alt="Surroundflix app window (extension on in Safari, audio and video notes, language menu, update check) next to the toolbar popup (5.1 and Atmos or 5.1 only, video quality and codec menus, and what Netflix sent: Dolby Atmos, 2160p HEVC Dolby Vision)">
</p>

### Audio

The Surroundflix button in Safari's toolbar has two choices:

| Audio | What it does |
| --- | --- |
| 5.1 and Atmos (default) | Asks Netflix for its Dolby Digital Plus 5.1, 5.1 HQ and Atmos tracks. Safari plays Atmos as its 5.1 bed |
| 5.1 only | Leaves Atmos out of the request. Use it if an Atmos title doesn't start or stays silent |

Chrome has no Dolby decoder, so its build asks for AAC 5.1 instead and
the audio choice is greyed out.

### Video quality

| Video quality | What it does |
| --- | --- |
| Automatic (default) | Netflix picks, as without Surroundflix |
| At least 720p / 1080p / 4K | Netflix still adapts to your connection, but never below that resolution |
| Always the best | Only the highest bitrate, for video and for each audio format |
| Data saver (720p max) | Never above 720p, for hotspots and capped plans |

These modes remove streams from the list Netflix's player picks from; the
player itself is untouched. If a title doesn't reach a minimum, its best
streams are kept, so playback never breaks. Anything above Automatic needs
a fast, stable connection, or playback pauses to buffer instead of lowering
the quality. Netflix caps Chrome at 1080p (software DRM); Safari can reach
4K HDR on a Premium plan with a compatible Mac and screen.

### Codec

| Codec | Notes |
| --- | --- |
| Automatic (default) | Netflix picks: usually AV1 in Chrome, HEVC in Safari |
| H.264 | Highest bitrates at a given resolution, up to 1080p, no HDR. Netflix picks the profile |
| H.264 Main / High | H.264 with that profile only. Main also asks for Netflix's second family of Main encodes (`-prk-qc`, the names the Kodi Netflix add-on uses), which on some titles has a much higher bitrate |
| HEVC (H.265) | Safari only. Netflix's 4K, HDR10 and Dolby Vision streams |
| AV1 | Smallest files for the same quality score; can look softer at low bitrates |
| VP9 | Chrome only |

Netflix picks the codec on its servers from the formats the player lists,
and sends only that one. With a codec chosen, Surroundflix lists only that
codec's formats, so Netflix sends it. Codecs your browser can't decode
aren't offered in the menu (AV1 in Safari needs an Apple chip with an AV1
decoder, M3 or later). If a title doesn't exist in the chosen codec, it
may not start: switch back to Automatic. Quality and codec combine:
HEVC with At least 4K gives 4K HEVC.

Under each menu, a line explains the option currently chosen. Changes
apply to the next title you start.

### On this tab

The bottom of the popup shows what Netflix sent for the title playing in
the current tab: the best audio (Dolby Atmos, Dolby Digital Plus 5.1, AAC
5.1 or stereo), the video (resolution, codec, HDR or Dolby Vision,
bitrate) and the range of resolutions Netflix offers for it. If a Netflix
tab doesn't answer, the popup says to allow Surroundflix on netflix.com.

### Title badges

Netflix sends the features of every title (Atmos, 5.1, 4K...) to its web
pages but only draws some of them. Surroundflix adds `Dolby Atmos`, `5.1`
and `Ultra HD 4K` next to Netflix's own badges, on title pages and in
their episode and collection lists, when the browser can play them: Atmos
and 4K in Safari, 5.1 in both. With "5.1 only" chosen, Atmos titles show
`5.1`.

### App window

The macOS app shows whether the extension is on in Safari, with the setup
steps until it is, opens Safari's settings, checks GitHub for a newer
release, and comes in English, French and Portuguese (Portugal, Brazil and
Angola, picked from the system language). The toolbar popup follows the
browser's language.

## Install

Download the latest release from the
[Releases page](https://github.com/AnzouK/surroundflix/releases).
Requires macOS with Safari 16.4 or later.

### Option A: the app (Surroundflix.dmg)

1. Open the .dmg and drag Surroundflix into Applications, then open it once.
   The app isn't notarized by Apple, so macOS may block it the first time:
   go to System Settings > Privacy & Security and click **Open Anyway**.
2. Safari > Settings > Advanced: tick **Show features for web developers**.
3. Safari > Settings > Developer: tick **Allow unsigned extensions**.
   Safari turns this off every time it quits, so you'll redo this step after
   a restart. Option B doesn't have this problem.
4. Safari > Settings > Extensions: enable Surroundflix and allow it on netflix.com.

The toolbar button and the app window are described in [Features](#features).

### Option B: userscript

1. Install the free [Userscripts](https://apps.apple.com/app/userscripts/id1463298887)
   app and enable it in Safari > Settings > Extensions.
2. Open `surroundflix.user.js` (in the release, or inside the .dmg) with Userscripts.
3. Allow it on netflix.com and reload Netflix.

Userscripts updates it automatically when a new release is out. To set a video
mode for the userscript, build it with, for example,
`surroundflix build --video-quality min1080 --video-codec h264`. The userscript is for Safari only and always asks for 5.1 and Atmos; it
has no toolbar button. In Chrome, use the Chrome extension below.

### Chrome

Chrome has no Dolby decoder, on any system, so no Atmos or Dolby 5.1 there.
The Chrome build asks Netflix for its AAC 5.1 track instead, on titles that
still offer one. On macOS, Chrome doesn't hand multichannel audio to
AirPods, so Spatial Audio shows as unavailable and you hear a stereo
downmix. It's mostly useful with real 5.1 speakers.

1. Download `surroundflix-chrome.zip` from the release and unzip it.
2. Open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked** and pick the unzipped folder.

## Check that it works

1. Open a title that has 5.1 or Atmos audio. Its page should show a
   `Dolby Atmos` or `5.1` badge (and `Ultra HD 4K` in Safari): Netflix
   sends those features but its web pages hide them, so Surroundflix adds
   them back. Then play it.
2. The player's audio menu should list `English (5.1)` or `English (Atmos)`.
3. With AirPods connected, Control Center > Sound should say Multichannel / Spatial Audio, not Stereo.

If Atmos titles ever fail to play, choose **5.1 only** in the toolbar
button (userscript: build it with `--preset surround`).

## How it works

Netflix's web player (Cadmium) sends a list of the audio and video
"profiles" the browser supports when it requests a title. On Safari that
list only contains stereo audio, so the server only returns stereo.

Surroundflix wraps `JSON.stringify` in the page and appends
`ddplus-5.1-dash`, `ddplus-5.1hq-dash` and `ddplus-atmos-dash` to that list
just before the request goes out.

Earlier attempts (see [Credits](#credits)) shipped a hand-edited copy of
Netflix's player, which broke each time Netflix released a new version.
Surroundflix never modifies or redistributes Netflix code, so it only
breaks if Netflix changes the request format itself.

The video quality and codec choices work the same way: video formats are
removed from that list, or streams from Netflix's answer, before the
player sees them. It doesn't touch DRM or accounts. The extension only
runs on `www.netflix.com` and asks for a single permission, `storage`, to
remember the choices made in its toolbar button.

## Privacy and security

Surroundflix collects nothing and the extension contacts no server; the app
only asks GitHub for updates when you click the button. Details in
[PRIVACY.md](PRIVACY.md).

Every push runs security tests (permissions, untrusted page data, network
destinations, workflow hardening) plus Bandit, pip-audit, gitleaks and
CodeQL. Releases are built by GitHub Actions from a tagged commit that
passed CI, and ship with `SHA256SUMS.txt` and build provenance
attestations. Check a download with:

```bash
shasum -a 256 -c SHA256SUMS.txt
gh attestation verify Surroundflix.dmg --repo AnzouK/surroundflix
```

To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Building from source

Python 3.9+. The app and .dmg also need macOS with the full Xcode (the
Command Line Tools alone don't include Apple's extension converter). After
installing Xcode, open it once, then run
`sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`.

```bash
git clone https://github.com/AnzouK/surroundflix.git
cd surroundflix
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                          # run the tests, security tests included
surroundflix build              # userscript, Safari and Chrome extensions, app window in dist/
surroundflix build --debug      # same, with logs in the Safari console
surroundflix build --preset surround   # 5.1 only, no Atmos request
surroundflix dmg                # Surroundflix.app + .dmg in release/
```

Type `__surroundflix` in the Web Inspector console on Netflix:
`lastManifestAudio` and `lastManifestVideo` show what Netflix actually sent
back, and `requestedVideo` the video formats asked for when a codec is chosen.
A `--debug` build also logs each step to the console. The
[bug report form](https://github.com/AnzouK/surroundflix/issues/new?template=bug_report.yml)
asks for that output.

Open `dist/app/Main.html` in a browser to preview the app window; add
`?state=on&lang=pt-AO&theme=dark` to try other states, languages and themes.
After changing the app window, the popup or their English text, run
`python scripts/make_showcase.py` to redraw `design/showcase.svg` (a test
fails until you do).

Branches, commit messages, translations and releases are described in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Automatic watch

`.github/workflows/watch-playercore.yml` runs once a day. It downloads
Netflix's current player, checks that the Dolby and AAC 5.1 profile names and the
`profiles` request field are still there, records the player version in
`.github/playercore-state.json`, and opens an issue if something is missing.

Netflix may only expose the player URL to signed-in pages. If the job can't
find it, copy the `cadmium-playercore-*.js` URL from Safari's Network tab
and save it as a repository variable named `PLAYERCORE_URL`. The same check
runs locally:

```bash
surroundflix check --url "https://assets.nflxext.com/.../cadmium-playercore-X.js"
```

## Project layout

```
src/surroundflix/
  profiles.py           Netflix audio profiles, presets, video modes and codecs
  templates/page.js     the in-page hook: Netflix's request and answer, title badges
  templates/content.js  passes the popup choices to page.js (and loads it in Safari)
  templates/popup.*     the toolbar button
  templates/app/        the app window (replaces Apple's default one)
  templates/i18n.json   every interface string, per language
  build.py              builds the userscript and both extensions
  xcode.py              customises the Xcode project made by Apple's converter
  package.py            builds the macOS app and the .dmg
  playercore.py         downloads and checks Netflix's player
  cli.py                the `surroundflix` command
scripts/
  make_showcase.py      redraws design/showcase.svg from the templates
  release.py            dates the CHANGELOG, tags and pushes a release
tests/                  pytest, including the hook run under Node
```

## Credits

- **zooole**, **igermanprod**, **katzecz** and the rest of the MacRumors thread
  [Netflix on Safari with Dolby Atmos](https://forums.macrumors.com/threads/netflix-on-safari-with-dolby-atmos.2329766/),
  who showed Safari could play Netflix's 5.1 and Atmos streams and found the HQ profiles.
- **[dortanes / OpenSpatial](https://github.com/dortanes/openspatial)**, whose Safari
  extension confirmed the approach and the six-channel limit.
- **[truedread / netflix-1080p](https://github.com/truedread/netflix-1080p)**, the original Cadmium research.
- **[David Buchanan / turbo-recadmiumator](https://github.com/davidbuchanan314/turbo-recadmiumator)**,
  for patching at runtime instead of shipping a modified player.
- **[lkmvip / netflix-4K-DDplus](https://github.com/lkmvip/netflix-4K-DDplus)** and
  **TGSAN / [Netflix Plus](https://greasyfork.org/scripts/478739)**, for keeping DD+ alive in browsers.
- **[CastagnaIT / Netflix add-on for Kodi](https://github.com/CastagnaIT/plugin.video.netflix)**,
  whose list of Netflix's video profiles gave the `-prk-qc` H.264 Main encodes.

## Disclaimer

Unofficial project, not affiliated with Netflix, Apple or Dolby. Using it
may go against Netflix's Terms of Use; use it at your own risk. It doesn't
bypass DRM or unlock anything your plan doesn't already include.

## License

[AGPL-3.0 license](https://github.com/AnzouK/surroundflix#AGPL-3.0-1-ov-file). Copyright (c) 2026 AnzouK.

You can use, study and modify Surroundflix. If you distribute it, or a
modified version, or run a modified version as a service, you must publish
the full source under the same license.
