/*
 * Surroundflix content script.
 *
 * Content scripts run in an isolated copy of the page's JavaScript, so the
 * JSON.stringify wrapper in page.js has to live in the page's own context.
 * This script passes the choices made in the popup to page.js through
 * attributes on <html>, and, in Safari, loads page.js into the page. Chrome
 * loads page.js itself (manifest "world": "MAIN"). It also tells the
 * background script which audio label to show on the toolbar button.
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

  // The status page.js mirrors on <html>. Page scripts can write this
  // attribute too; real statuses stay under 4 KB.
  var STATUS_ATTR = "data-surroundflix-status";
  function isPlainObject(value) {
    return !!value && typeof value === "object" && !Array.isArray(value);
  }

  function readStatus() {
    var raw = root.getAttribute(STATUS_ATTR);
    var status = null;
    if (raw && raw.length <= 16384) {
      try { status = JSON.parse(raw); } catch (err) {}
    }
    if (isPlainObject(status)) {
      // Trailers and the next episode come with manifests of their own, so
      // only the title in the player's URL is reported. The latest manifest
      // stands in for it only when Netflix sent that one without a title id.
      var has = Object.prototype.hasOwnProperty;
      var titles = status.titles;
      var m = /^\/watch\/(\d{1,12})(?:\/|$)/.exec(location.pathname);
      var entry = m && isPlainObject(titles) && has.call(titles, m[1]) ? titles[m[1]] : null;
      if (isPlainObject(entry)) {
        status.received = Array.isArray(entry.received) ? entry.received : null;
        status.video = isPlainObject(entry.video) ? entry.video : null;
      } else if (!m || typeof status.title === "string") {
        status.received = null;
        status.video = null;
      }
      delete status.title;
      delete status.titles;
    }
    return { active: !!raw, status: status };
  }

  // The popup asks for it.
  try {
    api.runtime.onMessage.addListener(function (message, sender, sendResponse) {
      if (!message || message.type !== "surroundflix-status") return false;
      sendResponse(readStatus());
      return false;
    });
  } catch (err) {}

  // The toolbar button shows "ATM" or "5.1" while the player is open on a
  // title Netflix sent with that audio.
  function badgeLabel() {
    if (location.pathname.indexOf("/watch") !== 0) return "";
    var status = readStatus().status;
    var received = status && Array.isArray(status.received) ? status.received : [];
    if (received.indexOf("ddplus-atmos-dash") !== -1) return "ATM";
    for (var i = 0; i < received.length; i++) {
      if (typeof received[i] === "string" && /-5\.1(hq)?-dash$/.test(received[i])) return "5.1";
    }
    return "";
  }

  var shownLabel = null;
  function updateBadge() {
    var label = badgeLabel();
    if (label === shownLabel) return;
    shownLabel = label;
    try {
      Promise.resolve(api.runtime.sendMessage({ type: "surroundflix-badge", label: label }))
        .then(null, function () {});
    } catch (err) {}
  }

  try {
    new MutationObserver(updateBadge).observe(root, { attributes: true, attributeFilter: [STATUS_ATTR] });
    // Netflix opens and leaves the player without loading a new page, and
    // content scripts get no event for that.
    setInterval(updateBadge, 2000);
    updateBadge();
    window.addEventListener("popstate", updateBadge);
  } catch (err) {}

  if (INJECT) {
    var script = document.createElement("script");
    script.src = api.runtime.getURL("page.js");
    script.onload = function () { script.remove(); };
    (document.head || root).appendChild(script);
  }
})();
