/* Surroundflix popup: the audio preset and the video quality mode, saved in
 * extension storage, and what Netflix sent for the current tab. */
var DEFAULT_PRESET = /*__SURROUNDFLIX_DEFAULT_PRESET__*/ "atmos";
var CHECK_DOLBY = /*__SURROUNDFLIX_CHECK_DOLBY__*/ false;
var DEFAULT_VIDEO_QUALITY = /*__SURROUNDFLIX_DEFAULT_VIDEO_QUALITY__*/ "auto";

(function () {
  "use strict";
  var api = globalThis.browser || globalThis.chrome;
  var radios = document.querySelectorAll('input[name="preset"]');

  applyI18n(document, pickLang(navigator.languages || [navigator.language]));

  function select(value) {
    for (var i = 0; i < radios.length; i++) radios[i].checked = radios[i].value === value;
  }

  var videoQuality = document.getElementById("video-quality");

  select(DEFAULT_PRESET);
  videoQuality.value = DEFAULT_VIDEO_QUALITY;
  Promise.resolve(api.storage.local.get(["preset", "videoQuality"])).then(function (stored) {
    if (stored && stored.preset) select(stored.preset);
    if (stored && typeof stored.videoQuality === "string") videoQuality.value = stored.videoQuality;
    if (!videoQuality.value) videoQuality.value = DEFAULT_VIDEO_QUALITY; // unknown stored value
  }, function () { /* storage unavailable: keep the defaults shown above */ });

  for (var i = 0; i < radios.length; i++) {
    radios[i].addEventListener("change", function (event) {
      api.storage.local.set({ preset: event.target.value });
    });
  }
  videoQuality.addEventListener("change", function () {
    api.storage.local.set({ videoQuality: videoQuality.value });
  });

  var lang = pickLang(navigator.languages || [navigator.language]);
  var out = document.getElementById("tab-status");
  var videoOut = document.getElementById("tab-video");
  var rangeOut = document.getElementById("tab-range");

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

  function showVideo(video) {
    var quality = formatVideo(video, lang);
    videoOut.hidden = !quality;
    if (quality) sentence(videoOut, "tab_video", "quality", quality);
    var hasRange = !!quality && typeof video.minHeight === "number" && typeof video.maxHeight === "number";
    rangeOut.hidden = !hasRange;
    if (hasRange) rangeOut.textContent = t(lang, "tab_video_range", { min: video.minHeight + "p", max: video.maxHeight + "p" });
  }

  function showStatus(reply) {
    showVideo(reply && reply.active && reply.status ? reply.status.video : null);
    out.textContent = "";
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

  // Preview in a normal browser: popup.html?demo=atmos|stereo|waiting|none
  var demo = new URLSearchParams(location.search).get("demo");
  if (demo) {
    showStatus({
      atmos: { active: true, status: { received: ["ddplus-atmos-dash", "ddplus-5.1-dash", "heaac-2-dash"],
        video: { mode: "auto", height: 1080, bitrate: 5800, minHeight: 270, maxHeight: 1080 } } },
      stereo: { active: true, status: { received: ["heaac-2-dash"] } },
      waiting: { active: true, status: { received: null } }
    }[demo] || null);
  } else {
    try {
      Promise.resolve(api.tabs.query({ active: true, currentWindow: true })).then(function (tabs) {
        if (!tabs || !tabs[0]) return null;
        return api.tabs.sendMessage(tabs[0].id, { type: "surroundflix-status" });
      }).then(showStatus, function () { showStatus(null); });
    } catch (err) {
      showStatus(null);
    }
  }

  // Without Dolby support (Chrome), the preset has no effect: page.js asks
  // for AAC 5.1 instead.
  var dolby = !CHECK_DOLBY;
  if (CHECK_DOLBY) try {
    dolby = MediaSource.isTypeSupported('audio/mp4; codecs="ec-3"');
  } catch (err) {
    // MediaSource missing: treat as no Dolby support.
  }
  if (!dolby) {
    document.getElementById("presets").disabled = true;
    document.getElementById("no-dolby").hidden = false;
  }
})();
