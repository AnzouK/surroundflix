# Privacy

Surroundflix collects nothing. There's no account, no analytics, no
tracking and no cookies.

## The extension and the userscript

- They run only on `www.netflix.com` and send nothing anywhere. They add
  audio formats to the request Netflix's own player sends to Netflix, trim
  the list of video streams if you picked a video quality or codec, and add the
  Atmos, 5.1 and 4K badges to Netflix's title pages.
- The extension stores your settings in your browser's extension storage:
  your audio choice, your video quality, your preferred codec and whether
  to keep a playback log. They never leave your computer.
- "Recently watched" in the popup keeps a log of the last 30 titles you
  played: the title's Netflix number, its name when the player shows it,
  the date and time, and the audio and video Netflix sent. It is stored in
  the same extension storage, never sent anywhere, and you can turn it off
  or clear it in the popup. Removing the extension deletes it. Nothing is
  logged in private windows. The log belongs to the browser, so everyone
  using it sees the same list, whatever their Netflix profile.
- "On this tab" in the popup reads the audio formats and the video quality
  Netflix sent for the current title, and the badges come from the title
  features Netflix already sends to the page. That information stays in
  the page and the popup.
- "Copy debug info" copies the audio and video details shown for the
  current tab, your three settings and your browser's user agent to your
  clipboard. Nothing is sent: you choose where to paste it.
- They read nothing else: not your Netflix account's viewing history, no
  account details, no other site.
- The Chrome Web Store asks extensions to declare the data they handle,
  even when it never leaves the device. For Surroundflix that is the
  playback log above (web history) and what it reads from Netflix's pages
  for the popup, the badges and the log (website content). Neither is sent
  anywhere, sold or shared.

## The macOS app

- It checks for updates only when you click "Check for updates". That
  sends one request to GitHub's API (`api.github.com`), which, like any
  website, sees your IP address. See
  [GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).
- It remembers the language you picked, on your Mac only.

## The userscript's automatic updates

Your userscript manager periodically downloads the latest
`surroundflix.user.js` from this repository's GitHub releases to check for
a new version. That request goes to GitHub, not to the maintainer.

## Contact

Questions: open an issue at
[github.com/AnzouK/surroundflix/issues](https://github.com/AnzouK/surroundflix/issues).
