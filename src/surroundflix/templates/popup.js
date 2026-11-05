/* Surroundflix popup: the audio preset choice, saved in extension storage. */
var DEFAULT_PRESET = /*__SURROUNDFLIX_DEFAULT_PRESET__*/ "atmos";
var CHECK_DOLBY = /*__SURROUNDFLIX_CHECK_DOLBY__*/ false;

(function () {
  "use strict";
  var api = globalThis.browser || globalThis.chrome;
  var radios = document.querySelectorAll('input[name="preset"]');

  applyI18n(document, pickLang(navigator.languages || [navigator.language]));

  function select(value) {
    for (var i = 0; i < radios.length; i++) radios[i].checked = radios[i].value === value;
  }

  select(DEFAULT_PRESET);
  Promise.resolve(api.storage.local.get("preset")).then(function (stored) {
    if (stored && stored.preset) select(stored.preset);
  }, function () {});

  for (var i = 0; i < radios.length; i++) {
    radios[i].addEventListener("change", function (event) {
      api.storage.local.set({ preset: event.target.value });
    });
  }

  var lang = pickLang(navigator.languages || [navigator.language]);
  var out = document.getElementById("tab-status");

  function showStatus(reply) {
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
    var parts = t(lang, "tab_best", { format: "\u0000" }).split("\u0000");
    var strong = document.createElement("strong");
    strong.textContent = best;
    out.appendChild(document.createTextNode(parts[0]));
    out.appendChild(strong);
    out.appendChild(document.createTextNode(parts[1] || ""));
  }

  // Preview in a normal browser: popup.html?demo=atmos|stereo|waiting|none
  var demo = new URLSearchParams(location.search).get("demo");
  if (demo) {
    showStatus({
      atmos: { active: true, status: { received: ["ddplus-atmos-dash", "ddplus-5.1-dash", "heaac-2-dash"] } },
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
  } catch (err) {}
  if (!dolby) {
    document.getElementById("presets").disabled = true;
    document.getElementById("no-dolby").hidden = false;
  }
})();
