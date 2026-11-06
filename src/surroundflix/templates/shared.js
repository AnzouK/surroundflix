/* Helpers shared by the extension popup and the app window: translations,
 * audio format labels and the update check. The builder replaces the
 * placeholder with templates/i18n.json. */
var I18N = /*__SURROUNDFLIX_I18N__*/ null;

// Picks the best supported language for a list like navigator.languages.
// Plain "pt" goes to European Portuguese; pt-AO and pt-BR match exactly.
function pickLang(prefs) {
  var supported = Object.keys(I18N.strings);
  var lower = supported.map(function (l) { return l.toLowerCase(); });
  var list = (prefs || []).filter(Boolean).map(function (p) {
    return String(p).replace(/_/g, "-").toLowerCase();
  });
  for (var i = 0; i < list.length; i++) {
    var exact = lower.indexOf(list[i]);
    if (exact !== -1) return supported[exact];
    var base = list[i].split("-")[0];
    if (base === "pt") return "pt-PT";
    var byBase = lower.indexOf(base);
    if (byBase !== -1) return supported[byBase];
  }
  return "en";
}

// The language menu shows a single "Português"; the variant (Portugal,
// Brazil or Angola) comes from the system languages, Portugal by default.
function pickPortuguese(prefs) {
  var pt = (prefs || []).filter(function (p) { return /^pt/i.test(String(p)); });
  var lang = pickLang(pt);
  return lang.indexOf("pt-") === 0 ? lang : "pt-PT";
}

// Resolves a language menu value ("auto", "en", "fr" or "pt").
function resolveLang(choice, prefs) {
  if (choice === "pt") return pickPortuguese(prefs);
  if (choice && choice !== "auto" && I18N.strings[choice]) return choice;
  return pickLang(prefs);
}

function t(lang, key, vars) {
  var table = I18N.strings[lang] || {};
  var text = table[key] || I18N.strings.en[key] || key;
  if (vars) {
    Object.keys(vars).forEach(function (name) {
      text = text.split("{" + name + "}").join(vars[name]);
    });
  }
  return text;
}

// Netflix audio profile names, best first, with the label shown to users.
var AUDIO_FORMATS = [
  ["ddplus-atmos-dash", "Dolby Atmos"],
  ["ddplus-5.1hq-dash", "Dolby Digital Plus 5.1 (HQ)"],
  ["ddplus-5.1-dash", "Dolby Digital Plus 5.1"],
  ["heaac-5.1-dash", "AAC 5.1"]
];

// Returns the label of the best multichannel format in a list of profiles,
// or null when Netflix only sent stereo.
// The list comes from the page, which Netflix (or another script on it)
// controls, so anything that isn't an array of strings counts as nothing.
function bestAudio(profiles) {
  if (!Array.isArray(profiles)) return null;
  for (var i = 0; i < AUDIO_FORMATS.length; i++) {
    if (profiles.indexOf(AUDIO_FORMATS[i][0]) !== -1) return AUDIO_FORMATS[i][1];
  }
  return null;
}

// Compares "1.2.10" with "v1.2.9". Pre-release suffixes ("-beta") are
// ignored; anything unparsable is never "newer".
function isNewerVersion(candidate, current) {
  function parts(v) {
    var m = /^v?(\d+)\.(\d+)(?:\.(\d+))?/.exec(String(v || ""));
    return m ? [+m[1], +m[2], +(m[3] || 0)] : null;
  }
  var a = parts(candidate), b = parts(current);
  if (!a || !b) return false;
  for (var i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] > b[i];
  }
  return false;
}

// Only links to this repository's releases are shown as "Download", so a
// tampered API answer can't turn the button into a link elsewhere.
function isTrustedReleaseUrl(url, repo) {
  if (typeof url !== "string" || /[\s"'<>\\]/.test(url)) return false;
  var parsed;
  try {
    parsed = new URL(url);
  } catch (err) {
    return false;
  }
  // The parser resolves "..", "%2e%2e" and the like, so the path checked is
  // the one the browser would open.
  return parsed.protocol === "https:" && parsed.host === "github.com" &&
    !parsed.username && !parsed.password &&
    parsed.pathname.indexOf("/" + repo + "/releases/") === 0;
}

// "1080p · 5.8 Mb/s" from {height, bitrate (kb/s)}, with the language's
// decimal separator. Returns "" when the values aren't usable numbers.
var CODEC_LABELS = {
  h264: "H.264", h264main: "H.264 Main", h264high: "H.264 High", hevc: "HEVC", av1: "AV1", vp9: "VP9"
};
var RANGE_LABELS = { dv: "Dolby Vision", hdr: "HDR" };

function codecLabel(name) {
  return Object.prototype.hasOwnProperty.call(CODEC_LABELS, name) ? CODEC_LABELS[name] : "";
}

// A positive whole-ish number no larger than `max`, as Netflix would send.
// The status comes from the page, so anything else is ignored.
function plausible(n, max) {
  return typeof n === "number" && isFinite(n) && n > 0 && n <= max;
}

function formatVideo(video, lang) {
  if (!video || !plausible(video.bitrate, 1000000)) return "";
  var parts = [];
  if (plausible(video.height, 10000)) parts.push(Math.round(video.height) + "p");
  var codec = codecLabel(video.codec);
  if (codec) {
    var range = Object.prototype.hasOwnProperty.call(RANGE_LABELS, video.dynamicRange) ? RANGE_LABELS[video.dynamicRange] : "";
    parts.push(range ? codec + " " + range : codec);
  }
  parts.push((video.bitrate / 1000).toLocaleString(lang, { maximumFractionDigits: 1 }) + " Mb/s");
  return parts.join(" \u00b7 ");
}

function applyI18n(doc, lang) {
  doc.documentElement.lang = lang;
  var nodes = doc.querySelectorAll("[data-i18n]");
  for (var i = 0; i < nodes.length; i++) {
    nodes[i].textContent = t(lang, nodes[i].getAttribute("data-i18n"));
  }
}
