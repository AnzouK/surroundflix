/*
 * Surroundflix background script.
 *
 * Only extension pages can change the toolbar button, so the content script
 * sends the label here. Nothing else runs in the background.
 */
(function () {
  "use strict";
  var api = globalThis.browser || globalThis.chrome;
  var LABELS = ["5.1", "ATM"];

  function quietly(call) {
    try {
      Promise.resolve(call()).then(null, function () {});
    } catch (err) {}
  }

  api.runtime.onMessage.addListener(function (message, sender) {
    if (!message || message.type !== "surroundflix-badge") return false;
    if (!sender || !sender.tab || typeof sender.tab.id !== "number") return false;
    var tabId = sender.tab.id;
    var text = LABELS.indexOf(message.label) === -1 ? "" : message.label;
    // Safari draws the badge in its own colour and ignores this.
    if (text) quietly(function () { return api.action.setBadgeBackgroundColor({ tabId: tabId, color: "#3a3a3c" }); });
    quietly(function () { return api.action.setBadgeText({ tabId: tabId, text: text }); });
    return false;
  });
})();
