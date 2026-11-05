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
