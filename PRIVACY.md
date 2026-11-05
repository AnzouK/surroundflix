# Privacy

Surroundflix collects nothing. There's no account, no analytics, no
tracking and no cookies.

## The extension and the userscript

- They run only on `www.netflix.com` and send nothing anywhere. They add
  audio formats to the request Netflix's own player sends to Netflix, trim
  the list of video streams if you picked a video quality or codec, and add the
  Atmos, 5.1 and 4K badges to Netflix's title pages.
- The extension stores three settings in your browser's extension storage:
  your audio choice ("5.1 and Atmos" or "5.1 only"), your video quality
  and your preferred codec. They never leave your computer.
- "On this tab" in the popup reads the audio formats and the video quality
  Netflix sent for the current title, and the badges come from the title
  features Netflix already sends to the page. That information stays in
  the page and the popup.
- They read nothing else: no viewing history, no account details, no
  other site.

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
