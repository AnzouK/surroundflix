/*
 * Surroundflix content script.
 *
 * Content scripts run in an isolated copy of the page's JavaScript, so the
 * JSON.stringify wrapper in page.js has to live in the page's own context.
 * This script passes the choices made in the popup to page.js through
 * attributes on <html>, and, in Safari, loads page.js into the page. Chrome
 * loads page.js itself (manifest "world": "MAIN"). It also tells the
 * background script which audio label to show on the toolbar button, and
 * keeps the local playback log the popup shows under "Recently watched".
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

  // Playback log, in storage.local only. Null until loaded, so a write
  // never replaces entries it hasn't read.
  var recent = null;
  var historyEnabled = true;
  var clearedId = null; // title playing when the log was cleared

  try {
    Promise.resolve(api.storage.local.get(["preset", "videoQuality", "videoCodec", "historyEnabled", "history"]))
      .then(function (stored) {
        setPreset(stored && stored.preset);
        setVideo(stored && stored.videoQuality);
        setCodec(stored && stored.videoCodec);
        historyEnabled = !stored || stored.historyEnabled !== false;
        recent = cleanHistory(stored && stored.history);
        recordHistory();
      }, function () {});
    api.storage.onChanged.addListener(function (changes, area) {
      if (area !== "local") return;
      if (changes.preset) setPreset(changes.preset.newValue);
      if (changes.videoQuality) setVideo(changes.videoQuality.newValue);
      if (changes.videoCodec) setCodec(changes.videoCodec.newValue);
      if (changes.historyEnabled) historyEnabled = changes.historyEnabled.newValue !== false;
      if (changes.history && recent !== null) {
        recent = cleanHistory(changes.history.newValue);
        if (!recent.length) clearedId = watchId();
      }
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

  var HISTORY_MAX = 30;
  var HISTORY_WAIT = 10000; // ms between two writes for the same title
  var HISTORY_SAME_VIEWING = 6 * 3600000;
  var AUDIO_KEYS = ["ddplus-atmos-dash", "ddplus-5.1hq-dash", "ddplus-5.1-dash", "heaac-5.1-dash", "stereo"];
  var CODEC_KEYS = ["h264", "h264main", "h264high", "hevc", "av1", "vp9"];
  var HDR_KEYS = ["dv", "hdr"];
  var FIELDS = ["audio", "height", "codec", "hdr", "bitrate", "name"];
  var lastWrite = {};

  function known(list, value) {
    return typeof value === "string" && list.indexOf(value) !== -1 ? value : null;
  }

  function number(value, max) {
    return typeof value === "number" && isFinite(value) && value >= 1 && value <= max ? Math.round(value) : null;
  }

  function cleanName(value) {
    if (typeof value !== "string") return null;
    var text = value.replace(/[\u0000-\u001f\u007f-\u009f]+/g, " ").replace(/\s+/g, " ").trim();
    return text ? Array.from(text).slice(0, 80).join("") : null;
  }

  function cleanEntry(raw) {
    if (!isPlainObject(raw) || typeof raw.id !== "string" || !/^\d{1,12}$/.test(raw.id)) return null;
    var entry = {
      id: raw.id,
      at: number(raw.at, 1e14),
      audio: known(AUDIO_KEYS, raw.audio),
      height: number(raw.height, 10000),
      codec: known(CODEC_KEYS, raw.codec),
      hdr: known(HDR_KEYS, raw.hdr),
      bitrate: number(raw.bitrate, 1000000)
    };
    var name = cleanName(raw.name);
    if (name) entry.name = name;
    return entry.at && (entry.audio || entry.height || entry.codec || entry.bitrate) ? entry : null;
  }

  function cleanHistory(list) {
    var out = [], seen = {};
    if (!Array.isArray(list)) return out;
    for (var i = 0; i < list.length && out.length < HISTORY_MAX; i++) {
      var entry = cleanEntry(list[i]);
      if (entry && !seen[entry.id]) {
        seen[entry.id] = true;
        out.push(entry);
      }
    }
    return out;
  }

  // The best audio profile, as the popup shows it, or "stereo".
  function bestProfile(received) {
    if (!Array.isArray(received)) return null;
    for (var i = 0; i < AUDIO_KEYS.length - 1; i++) {
      if (received.indexOf(AUDIO_KEYS[i]) !== -1) return AUDIO_KEYS[i];
    }
    for (var j = 0; j < received.length; j++) {
      if (typeof received[j] === "string" && /^[a-z0-9.-]{1,40}-dash$/.test(received[j])) return "stereo";
    }
    return null;
  }

  // Only shown while the player's controls are. Series put the name,
  // episode and episode title in separate nodes.
  function playerTitle() {
    try {
      var node = document.querySelector && document.querySelector('[data-uia="video-title"]');
      if (!node) return null;
      var parts = [];
      for (var i = 0; i < node.childNodes.length; i++) {
        if (node.childNodes[i].nodeType === 8) continue; // comment
        var text = node.childNodes[i].textContent;
        if (text && text.trim()) parts.push(text);
      }
      return cleanName(parts.join(" "));
    } catch (err) {
      return null;
    }
  }

  function watchId() {
    var m = /^\/watch\/(\d{1,12})(?:\/|$)/.exec(location.pathname);
    return m ? m[1] : null;
  }

  function recordHistory() {
    if (recent === null || !historyEnabled) return;
    // Private windows share storage.local with normal ones: log nothing.
    if (api.extension && api.extension.inIncognitoContext) return;
    var id = watchId();
    if (id !== clearedId) clearedId = null;
    if (!id || clearedId) return;
    var status = readStatus().status;
    if (!status || (status.received == null && status.video == null)) return;
    var video = isPlainObject(status.video) ? status.video : {};
    var now = Date.now();
    var fresh = cleanEntry({
      id: id, at: now, audio: bestProfile(status.received), height: video.height,
      codec: video.codec, hdr: video.dynamicRange, bitrate: video.bitrate, name: playerTitle()
    });
    if (!fresh) return;
    var index = -1;
    for (var i = 0; i < recent.length; i++) {
      if (recent[i].id === id) index = i;
    }
    var old = index === -1 ? null : recent[index];
    var changed = index !== 0;
    if (old) {
      // Same viewing (still first, within 6 hours): keep its date.
      // Watched again later: today's date.
      if (index === 0 && now - old.at < HISTORY_SAME_VIEWING) fresh.at = old.at;
      for (var f = 0; f < FIELDS.length; f++) {
        var key = FIELDS[f];
        if (fresh[key] == null && old[key] != null) fresh[key] = old[key];
        if (fresh[key] !== old[key]) changed = true;
      }
    }
    if (!changed || (lastWrite[id] && now - lastWrite[id] < HISTORY_WAIT)) return;
    lastWrite[id] = now;
    var next = [fresh];
    for (var j = 0; j < recent.length && next.length < HISTORY_MAX; j++) {
      if (j !== index) next.push(recent[j]);
    }
    recent = next;
    try {
      Promise.resolve(api.storage.local.set({ history: next })).then(null, function () {});
    } catch (err) {}
  }

  var shownLabel = null;
  function updateBadge() {
    recordHistory();
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
