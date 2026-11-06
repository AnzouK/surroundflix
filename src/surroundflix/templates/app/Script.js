/* Surroundflix app window. The Swift side (ViewController.swift) calls
 * setPreferredLanguages(list) and show(...) once the page has loaded, and
 * listens for the "open-preferences" message. Opened in a normal browser,
 * the page runs as a preview: ?state=on|off&theme=dark&lang=pt-AO */
var APP_VERSION = /*__SURROUNDFLIX_VERSION__*/ "0.0.0";
var REPO = /*__SURROUNDFLIX_REPO__*/ "owner/surroundflix";

(function () {
  "use strict";

  var LANG_KEY = "surroundflix.language";
  var bridge = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.controller;
  var query = new URLSearchParams(location.search);
  var systemLanguages = navigator.languages || [navigator.language];
  var enabled = null;
  var lastUpdate = null;

  function $(id) { return document.getElementById(id); }

  // One of the menu values: "auto", "en", "fr", "pt".
  function storedLanguage() {
    var value = "auto";
    try { value = localStorage.getItem(LANG_KEY) || "auto"; } catch (err) {}
    if (value.indexOf("pt") === 0) value = "pt";
    return I18N.menu[value] ? value : "auto";
  }

  function currentLanguage() {
    // The preview URL may force an exact variant, e.g. ?lang=pt-AO.
    var preview = query.get("lang");
    if (preview && I18N.strings[preview]) return preview;
    return resolveLang(storedLanguage(), systemLanguages);
  }

  function renderStatus(lang) {
    var box = $("status");
    box.classList.toggle("on", enabled === true);
    box.classList.toggle("off", enabled === false);
    var key = enabled === null ? "status_checking" : enabled ? "status_on" : "status_off";
    $("status-text").textContent = t(lang, key);
    $("steps").hidden = enabled === true;
    $("all-set").hidden = enabled !== true;
  }

  function renderUpdate(lang) {
    var out = $("update-result");
    out.textContent = "";
    if (!lastUpdate) return;
    if (lastUpdate.state === "available") {
      out.appendChild(document.createTextNode(t(lang, "updates_available", { version: lastUpdate.version }) + " "));
      var link = document.createElement("a");
      link.href = lastUpdate.url;
      link.textContent = t(lang, "updates_download");
      out.appendChild(link);
    } else {
      out.textContent = t(lang, "updates_" + lastUpdate.state);
    }
  }

  function render() {
    var lang = currentLanguage();
    applyI18n(document, lang);
    renderStatus(lang);
    renderUpdate(lang);
  }

  function buildLanguageMenu() {
    var select = $("language");
    var auto = document.createElement("option");
    auto.value = "auto";
    auto.setAttribute("data-i18n", "language_auto");
    select.appendChild(auto);
    Object.keys(I18N.menu).forEach(function (code) {
      var opt = document.createElement("option");
      opt.value = code;
      opt.textContent = I18N.menu[code];
      select.appendChild(opt);
    });
    select.value = storedLanguage();
    select.addEventListener("change", function () {
      try { localStorage.setItem(LANG_KEY, select.value); } catch (err) {}
      render();
    });
  }

  function checkUpdates() {
    var button = $("check-updates");
    button.disabled = true;
    lastUpdate = { state: "checking" };
    renderUpdate(currentLanguage());
    fetch("https://api.github.com/repos/" + REPO + "/releases/latest", {
      headers: { Accept: "application/vnd.github+json" }
    }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    }).then(function (release) {
      if (!release || !isTrustedReleaseUrl(release.html_url, REPO)) throw new Error("unexpected answer");
      lastUpdate = isNewerVersion(release.tag_name, APP_VERSION)
        ? { state: "available", version: String(release.tag_name).replace(/^v/, ""), url: release.html_url }
        : { state: "latest" };
    }).catch(function () {
      lastUpdate = { state: "failed" };
    }).then(function () {
      button.disabled = false;
      renderUpdate(currentLanguage());
    });
  }

  // Called from Swift. Newer Xcode templates pass a platform name first.
  window.show = function () {
    var args = Array.prototype.slice.call(arguments);
    if (typeof args[0] === "string") args.shift();
    enabled = args[0] === true;
    render();
  };

  window.setPreferredLanguages = function (list) {
    if (Array.isArray(list) && list.length) systemLanguages = list;
    render();
  };

  $("version").textContent = APP_VERSION;
  $("repo-link").href = "https://github.com/" + REPO;
  $("open-settings").addEventListener("click", function () {
    if (bridge) bridge.postMessage("open-preferences");
  });
  $("check-updates").addEventListener("click", checkUpdates);
  buildLanguageMenu();

  // Back from Safari's settings while the extension was still off: reload,
  // so Swift reports the new state. Once it's on, nothing to refresh, and a
  // reload would wipe an update result the user came back to click.
  if (bridge) {
    var leftAt = 0;
    window.addEventListener("blur", function () { leftAt = Date.now(); });
    window.addEventListener("focus", function () {
      var away = leftAt && Date.now() - leftAt > 1000;
      leftAt = 0;
      if (away && enabled !== true) location.reload();
    });
  }

  if (!bridge) {
    if (query.get("theme")) document.documentElement.setAttribute("data-theme", query.get("theme"));
    if (query.get("state")) enabled = query.get("state") === "on";
  }
  render();
})();
