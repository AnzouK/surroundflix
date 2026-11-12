/* Surroundflix popup: the audio preset, the video quality and codec, saved in
 * extension storage, and what Netflix sent for the current tab. */
var DEFAULT_PRESET = /*__SURROUNDFLIX_DEFAULT_PRESET__*/ "atmos";
var CHECK_DOLBY = /*__SURROUNDFLIX_CHECK_DOLBY__*/ false;
var DEFAULT_VIDEO_QUALITY = /*__SURROUNDFLIX_DEFAULT_VIDEO_QUALITY__*/ "auto";
var DEFAULT_VIDEO_CODEC = /*__SURROUNDFLIX_DEFAULT_VIDEO_CODEC__*/ "auto";
var VERSION = /*__SURROUNDFLIX_VERSION__*/ "0.0.0";

(function () {
  "use strict";
  var api = globalThis.browser || globalThis.chrome;
  // Missing when popup.html is opened as a normal page (?demo= below).
  var storage = api && api.storage && api.storage.local;
  var radios = document.querySelectorAll('input[name="preset"]');
  var lang = pickLang(navigator.languages || [navigator.language]);

  applyI18n(document, lang);
  document.getElementById("version").textContent = VERSION;

  function select(value) {
    var known = false;
    for (var i = 0; i < radios.length; i++) known = known || radios[i].value === value;
    if (!known) value = DEFAULT_PRESET;
    for (var j = 0; j < radios.length; j++) radios[j].checked = radios[j].value === value;
  }

  var videoQuality = document.getElementById("video-quality");
  var videoCodec = document.getElementById("video-codec");

  // Codecs Netflix never sends to this browser are left out: HEVC is
  // Safari only, VP9 Chrome only.
  // So are codecs this Mac or browser can't decode (AV1 in Safari needs a
  // chip with an AV1 decoder).
  var browserName = CHECK_DOLBY ? "chrome" : "safari";
  var CODEC_TYPES = {
    h264: 'video/mp4; codecs="avc1.640028"',
    h264main: 'video/mp4; codecs="avc1.4d4028"',
    h264high: 'video/mp4; codecs="avc1.640028"',
    hevc: 'video/mp4; codecs="hvc1.2.4.L153.B0"',
    av1: 'video/mp4; codecs="av01.0.08M.08"',
    vp9: 'video/mp4; codecs="vp09.00.40.08"'
  };
  function decodes(codec) {
    try {
      return !window.MediaSource || !CODEC_TYPES[codec] || window.MediaSource.isTypeSupported(CODEC_TYPES[codec]);
    } catch (err) {
      return true;
    }
  }
  var codecOptions = videoCodec.querySelectorAll("option");
  for (var c = 0; c < codecOptions.length; c++) {
    var only = codecOptions[c].getAttribute("data-browser");
    if ((only && only !== browserName) || !decodes(codecOptions[c].value)) codecOptions[c].remove();
  }

  // After a change, "Apply now" reloads the Netflix tab, so the player asks
  // Netflix again with the new settings.
  var applyNow = document.getElementById("apply-now");
  var debugResult = document.getElementById("debug-result");
  var netflixTab = null, changed = false;

  function showApply() {
    applyNow.hidden = !changed || netflixTab === null;
  }

  function store(items) {
    try {
      if (storage) storage.set(items);
    } catch (err) {}
  }

  function save(items) {
    store(items);
    changed = true;
    debugResult.textContent = ""; // what was copied no longer matches
    showApply();
  }

  applyNow.addEventListener("click", function () {
    function close() { window.close(); }
    try {
      Promise.resolve(api.tabs.reload(netflixTab)).then(close, close);
    } catch (err) {}
  });

  select(DEFAULT_PRESET);
  videoQuality.value = DEFAULT_VIDEO_QUALITY;
  videoCodec.value = DEFAULT_VIDEO_CODEC;
  describeAll();
  if (storage) try {
    Promise.resolve(storage.get(["preset", "videoQuality", "videoCodec"])).then(function (stored) {
      if (stored && stored.preset) select(stored.preset);
      if (stored && typeof stored.videoQuality === "string") videoQuality.value = stored.videoQuality;
      if (!videoQuality.value) videoQuality.value = DEFAULT_VIDEO_QUALITY; // unknown stored value
      if (stored && typeof stored.videoCodec === "string") videoCodec.value = stored.videoCodec;
      if (!videoCodec.value) {
        // Codec no longer offered in this browser, so go back to Automatic.
        videoCodec.value = DEFAULT_VIDEO_CODEC;
        store({ videoCodec: DEFAULT_VIDEO_CODEC });
      }
      describeAll();
    }, function () {});
  } catch (err) {}

  for (var i = 0; i < radios.length; i++) {
    radios[i].addEventListener("change", function (event) {
      save({ preset: event.target.value });
      describeAll();
    });
  }
  videoQuality.addEventListener("change", function () {
    save({ videoQuality: videoQuality.value });
    describeAll();
  });
  videoCodec.addEventListener("change", function () {
    save({ videoCodec: videoCodec.value });
    describeAll();
  });

  // One line under each menu explains the option currently chosen.
  function describe(id, key, extra) {
    var node = document.getElementById(id);
    var text = t(lang, key);
    if (extra) text += " " + t(lang, extra);
    node.textContent = text;
  }

  function describeAll() {
    var preset = document.querySelector('input[name="preset"]:checked');
    describe("preset-desc", "pdesc_" + (preset ? preset.value : "atmos"));
    describe("video-quality-desc", "qdesc_" + (videoQuality.value || "auto"));
    var codec = videoCodec.value || "auto";
    describe("video-codec-desc", "cdesc_" + codec, codec === "auto" ? "" : "codec_hint");
  }

  var out = document.getElementById("tab-status");
  var videoOut = document.getElementById("tab-video");
  var rangeOut = document.getElementById("tab-range");
  var missOut = document.getElementById("tab-miss");

  // Fills `node` with a translated sentence whose {name} part is in bold.
  function sentence(node, key, name, value) {
    var vars = {};
    vars[name] = "\u0000";
    var parts = t(lang, key, vars).split("\u0000");
    var strong = document.createElement("strong");
    strong.textContent = value;
    node.textContent = "";
    node.appendChild(document.createTextNode(parts[0]));
    node.appendChild(strong);
    node.appendChild(document.createTextNode(parts[1] || ""));
  }

  function isNetflixUrl(url) {
    return typeof url === "string" && /^https:\/\/(www\.)?netflix\.com\//.test(url);
  }

  function showVideo(video) {
    var quality = formatVideo(video, lang);
    videoOut.hidden = !quality;
    if (quality) sentence(videoOut, "tab_video", "quality", quality);
    var hasRange = !!quality && plausible(video.minHeight, 10000) && plausible(video.maxHeight, 10000) &&
      video.minHeight <= video.maxHeight;
    rangeOut.hidden = !hasRange;
    if (hasRange) rangeOut.textContent = t(lang, "tab_video_range", { min: Math.round(video.minHeight) + "p", max: Math.round(video.maxHeight) + "p" });
    var misses = quality ? videoMisses(video) : [];
    missOut.hidden = !misses.length;
    missOut.textContent = misses.map(function (miss) { return t(lang, miss[0], miss[1]); }).join(" ");
  }

  // Everything a bug report needs, from this popup and from the page.
  var debug = document.getElementById("debug");
  var lastStatus = null;
  var STATUS_KEYS = ["version", "preset", "dolbySupported", "requested", "requestedVideo",
    "received", "video", "patchedRequests"];

  // The page wrote the status: copy only the fields page.js publishes.
  function knownStatus(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    var out = {}, found = false;
    STATUS_KEYS.forEach(function (key) {
      if (Object.prototype.hasOwnProperty.call(raw, key)) {
        out[key] = raw[key];
        found = true;
      }
    });
    return found ? out : null;
  }

  function debugInfo() {
    var preset = document.querySelector('input[name="preset"]:checked');
    return JSON.stringify({
      browser: navigator.userAgent,
      settings: {
        preset: preset ? preset.value : null,
        videoQuality: videoQuality.value,
        videoCodec: videoCodec.value
      },
      page: lastStatus
    }, null, 2);
  }

  function copyText(text) {
    var fallback = function () {
      var focused = document.activeElement;
      var area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try {
        ok = document.execCommand("copy");
      } catch (err) {}
      area.remove();
      if (focused && focused.focus) focused.focus();
      if (!ok) throw new Error("copy refused");
    };
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return Promise.resolve(navigator.clipboard.writeText(text)).then(null, fallback);
      }
      fallback();
      return Promise.resolve();
    } catch (err) {
      return Promise.reject(err);
    }
  }

  document.getElementById("copy-debug").addEventListener("click", function () {
    copyText(debugInfo()).then(function () {
      debugResult.textContent = t(lang, "debug_copied");
    }, function () {
      debugResult.textContent = t(lang, "debug_failed");
    });
  });

  function showStatus(reply) {
    lastStatus = reply && reply.active ? knownStatus(reply.status) : null;
    debug.hidden = !lastStatus;
    debugResult.textContent = "";
    showVideo(lastStatus ? lastStatus.video : null);
    out.textContent = "";
    if (reply && reply.noAnswer) {
      out.textContent = t(lang, "tab_no_access");
      return;
    }
    if (!reply || !reply.active) {
      out.textContent = t(lang, "tab_none");
      return;
    }
    var received = reply.status && reply.status.received;
    if (!received) {
      out.textContent = t(lang, "tab_waiting");
      return;
    }
    var best = bestAudio(received);
    if (!best) {
      out.textContent = t(lang, "tab_stereo");
      return;
    }
    sentence(out, "tab_best", "format", best);
  }

  // The tab this popup was opened on. A Safari web app (Netflix added to the
  // Dock) doesn't always report it as its window's active tab, so the next
  // lookup is tried when one finds no tab at all.
  var TAB_LOOKUPS = [{ active: true, currentWindow: true }, { active: true, lastFocusedWindow: true },
    { active: true }];

  function findTab(step) {
    if (step >= TAB_LOOKUPS.length) return Promise.resolve(null);
    return Promise.resolve(api.tabs.query(TAB_LOOKUPS[step])).then(function (tabs) {
      return tabs && tabs[0] ? tabs[0] : findTab(step + 1);
    }, function () {
      return findTab(step + 1);
    });
  }

  // Preview in a normal browser: popup.html?demo=atmos|stereo|waiting|noaccess|none
  var demo = new URLSearchParams(location.search).get("demo");
  if (demo) {
    showStatus({
      atmos: { active: true, status: { received: ["ddplus-atmos-dash", "ddplus-5.1-dash", "heaac-2-dash"],
        video: { mode: "auto", height: 2160, bitrate: 10400, codec: "hevc", dynamicRange: "dv",
          codecs: ["hevc", "av1", "h264"], minHeight: 342, maxHeight: 2160 } } },
      stereo: { active: true, status: { received: ["heaac-2-dash"] } },
      waiting: { active: true, status: { received: null } },
      noaccess: { noAnswer: true }
    }[demo] || null);
  } else {
    try {
      findTab(0).then(function (tab) {
        if (!tab) return null;
        return Promise.resolve(api.tabs.sendMessage(tab.id, { type: "surroundflix-status" }))
          .then(function (reply) {
            if (reply && reply.active) netflixTab = tab.id;
            showApply();
            return reply;
          }, function () {
            // No content script answered. The URL is only visible on sites
            // the extension may access, so an unknown URL can be Netflix
            // without permission (or a second copy of the extension).
            return isNetflixUrl(tab.url) || !tab.url ? { noAnswer: true } : null;
          });
      }).then(showStatus, function () { showStatus(null); });
    } catch (err) {
      showStatus(null);
    }
  }

  // Without Dolby support (Chrome), page.js asks for AAC 5.1 instead: there
  // is no Atmos, so "5.1 only" stands for what Surroundflix gets.
  var dolby = !CHECK_DOLBY;
  if (CHECK_DOLBY) try {
    dolby = MediaSource.isTypeSupported('audio/mp4; codecs="ec-3"');
  } catch (err) {}
  if (!dolby) {
    var showAsSurround = function () {
      var atmos = document.querySelector('input[name="preset"]:checked');
      if (atmos && atmos.value === "atmos") select("surround");
      describeAll();
    };
    for (var r = 0; r < radios.length; r++) {
      if (radios[r].value === "atmos") radios[r].disabled = true;
    }
    document.getElementById("no-dolby").hidden = false;
    showAsSurround();
    if (storage) try {
      Promise.resolve(storage.get(["preset"])).then(showAsSurround, function () {});
    } catch (err) {}
  }
})();
