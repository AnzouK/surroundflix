/*
 * Surroundflix content script.
 *
 * Content scripts run in an isolated copy of the page's JavaScript, so the
 * JSON.stringify wrapper in page.js has to live in the page's own context.
 * This script passes the choices made in the popup to page.js through
 * attributes on <html>, and, in Safari, loads page.js into the page. Chrome
 * loads page.js itself (manifest "world": "MAIN").
 */
(function () {
  "use strict";
  var api = globalThis.browser || globalThis.chrome;
  var root = document.documentElement;
  var INJECT = /*__SURROUNDFLIX_INJECT__*/ true;

  function setPreset(value) {
    if (value) root.setAttribute("data-surroundflix-preset", value);
  }

  function setVideo(value) {
    if (typeof value === "string") root.setAttribute("data-surroundflix-video", value);
  }

  function setCodec(value) {
    if (typeof value === "string") root.setAttribute("data-surroundflix-codec", value);
  }

  try {
    Promise.resolve(api.storage.local.get(["preset", "videoQuality", "videoCodec"])).then(function (stored) {
      setPreset(stored && stored.preset);
      setVideo(stored && stored.videoQuality);
      setCodec(stored && stored.videoCodec);
    }, function () {});
    api.storage.onChanged.addListener(function (changes, area) {
      if (area !== "local") return;
      if (changes.preset) setPreset(changes.preset.newValue);
      if (changes.videoQuality) setVideo(changes.videoQuality.newValue);
      if (changes.videoCodec) setCodec(changes.videoCodec.newValue);
    });
  } catch (err) {}

  // The popup asks for the status page.js mirrors on <html>.
  try {
    api.runtime.onMessage.addListener(function (message, sender, sendResponse) {
      if (!message || message.type !== "surroundflix-status") return false;
      var raw = root.getAttribute("data-surroundflix-status");
      var status = null;
      // Any page script can write this attribute; a real status is under 2 KB.
      if (raw && raw.length <= 16384) {
        try { status = JSON.parse(raw); } catch (err) {}
      }
      sendResponse({ active: !!raw, status: status });
      return false;
    });
  } catch (err) {}

  if (INJECT) {
    var script = document.createElement("script");
    script.src = api.runtime.getURL("page.js");
    script.onload = function () { script.remove(); };
    (document.head || root).appendChild(script);
  }
})();
