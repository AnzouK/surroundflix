/*
 * Surroundflix content script.
 *
 * Content scripts run in an isolated copy of the page's JavaScript, so the
 * JSON.stringify wrapper in page.js has to live in the page's own context.
 * This script passes the preset chosen in the popup to page.js through an
 * attribute on <html>, and, in Safari, loads page.js into the page. Chrome
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

  try {
    Promise.resolve(api.storage.local.get("preset")).then(function (stored) {
      setPreset(stored && stored.preset);
    }, function () {});
    api.storage.onChanged.addListener(function (changes, area) {
      if (area === "local" && changes.preset) setPreset(changes.preset.newValue);
    });
  } catch (err) {
    // Storage unavailable: page.js falls back to the default preset.
  }

  // The popup asks for the status page.js mirrors on <html>.
  try {
    api.runtime.onMessage.addListener(function (message, sender, sendResponse) {
      if (!message || message.type !== "surroundflix-status") return false;
      var raw = root.getAttribute("data-surroundflix-status");
      var status = null;
      try { status = raw ? JSON.parse(raw) : null; } catch (err) {}
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
