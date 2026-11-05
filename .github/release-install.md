## Install

Requires macOS with Safari 16.4 or later, or Chrome.

### Safari: the app (`Surroundflix.dmg`)

1. Open the .dmg, drag Surroundflix into Applications and open it once.
   The app isn't notarized by Apple: if macOS blocks it, go to System
   Settings > Privacy & Security and click **Open Anyway**.
2. Safari > Settings > Advanced: tick **Show features for web developers**.
3. Safari > Settings > Developer: tick **Allow unsigned extensions**.
   Safari turns this off each time it quits, so redo this step after a restart.
4. Safari > Settings > Extensions: enable Surroundflix and allow it on netflix.com.

The Surroundflix button in Safari's toolbar sets the audio, the video
quality and the codec.

### Safari: the userscript (`surroundflix.user.js`)

No unsigned-extension setting, but no toolbar button either.

1. Install the free [Userscripts](https://apps.apple.com/app/userscripts/id1463298887)
   app and enable it in Safari > Settings > Extensions.
2. Open `surroundflix.user.js` with Userscripts and allow it on netflix.com.

It updates itself when a new release is out.

### Chrome (`surroundflix-chrome.zip`)

Chrome has no Dolby decoder, so it gets Netflix's AAC 5.1 when a title has it.

1. Unzip `surroundflix-chrome.zip`.
2. Open `chrome://extensions`, turn on **Developer mode**, click
   **Load unpacked** and pick the unzipped folder.

### Check that it works

Open a title with 5.1 or Atmos: its page shows a `Dolby Atmos` or `5.1`
badge. Play it, open the toolbar button: "On this tab" shows the audio and
video Netflix sent. Full guide: [README](https://github.com/AnzouK/surroundflix#readme).
