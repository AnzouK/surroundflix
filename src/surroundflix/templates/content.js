/*
 * Surroundflix content script (Safari Web Extension).
 *
 * Content scripts run in an isolated copy of the page's JavaScript, so a
 * JSON.stringify wrapper set here would never be seen by Netflix's player.
 * This file's only job is to load page.js into the page's own context.
 */
(function () {
  "use strict";
  var api = globalThis.browser || globalThis.chrome;
  var script = document.createElement("script");
  script.src = api.runtime.getURL("page.js");
  script.onload = function () { script.remove(); };
  (document.head || document.documentElement).appendChild(script);
})();
