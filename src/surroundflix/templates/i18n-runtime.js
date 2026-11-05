/* Shared by the extension popup and the app window. The builder replaces
 * the placeholder with templates/i18n.json. */
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
function bestAudio(profiles) {
  for (var i = 0; i < AUDIO_FORMATS.length; i++) {
    if ((profiles || []).indexOf(AUDIO_FORMATS[i][0]) !== -1) return AUDIO_FORMATS[i][1];
  }
  return null;
}

function applyI18n(doc, lang) {
  doc.documentElement.lang = lang;
  var nodes = doc.querySelectorAll("[data-i18n]");
  for (var i = 0; i < nodes.length; i++) {
    nodes[i].textContent = t(lang, nodes[i].getAttribute("data-i18n"));
  }
}
