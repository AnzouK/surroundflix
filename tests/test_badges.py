"""Title badges: the page script reads Netflix's playbackBadges and adds the
Atmos / 5.1 / 4K badges Netflix's page leaves out. Runs under Node with a
tiny fake DOM shaped like Netflix's metadata lines."""

import json
import shutil
import subprocess

import pytest

from surroundflix.build import render_page_script

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node is not installed")

# Just enough DOM for the badge code: class, [attr] and [attr="value"]
# selectors, tree edits and attributes.
FAKE_DOM = r"""
function matches(el, sel) {
  sel = sel.trim();
  if (sel[0] === ".") return (" " + el.className + " ").indexOf(" " + sel.slice(1) + " ") !== -1;
  var m = /^\[([\w-]+)(?:="([^"]*)")?\]$/.exec(sel);
  if (m) return m[2] === undefined ? el.hasAttribute(m[1]) : el.getAttribute(m[1]) === m[2];
  throw new Error("unsupported selector " + sel);
}
function El(tag, attrs, text, kids) {
  this.tagName = tag; this.attrs = {}; this.children = []; this.parentElement = null;
  this.style = {}; this.className = ""; this.textContent = text || "";
  for (var k in attrs || {}) { if (k === "class") this.className = attrs[k]; else this.attrs[k] = attrs[k]; }
  (kids || []).forEach(function (c) { this.appendChild(c); }, this);
}
El.prototype.getAttribute = function (k) { return k in this.attrs ? this.attrs[k] : null; };
El.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
El.prototype.hasAttribute = function (k) { return k in this.attrs; };
El.prototype.removeAttribute = function (k) { delete this.attrs[k]; };
El.prototype.matches = function (s) { return s.split(",").some(function (p) { return matches(this, p); }, this); };
El.prototype.appendChild = function (c) { return this.insertBefore(c, null); };
El.prototype.insertBefore = function (c, ref) {
  if (c.parentElement) c.parentElement.removeChild(c);
  var i = ref ? this.children.indexOf(ref) : -1;
  if (i === -1) this.children.push(c); else this.children.splice(i, 0, c);
  c.parentElement = this; return c;
};
El.prototype.removeChild = function (c) {
  this.children.splice(this.children.indexOf(c), 1); c.parentElement = null; return c;
};
Object.defineProperty(El.prototype, "nextSibling", { get: function () {
  var p = this.parentElement; return p ? p.children[p.children.indexOf(this) + 1] || null : null; } });
El.prototype.querySelectorAll = function (s) {
  var out = [];
  (function visit(el) { el.children.forEach(function (c) { if (c.matches(s)) out.push(c); visit(c); }); })(this);
  return out;
};
El.prototype.querySelector = function (s) { return this.querySelectorAll(s)[0] || null; };
function h(tag, attrs, text, kids) { return new El(tag, attrs, text, kids); }

var ATTRS = %(attrs)s;
var html = h("html");
html.getAttribute = function (k) { return k in ATTRS ? ATTRS[k] : null; };
var body = h("body");
html.appendChild(body);
globalThis.window = globalThis;
globalThis.location = { search: %(search)s, pathname: %(path)s };
globalThis.document = {
  documentElement: html,
  createElement: function (t) { return h(t); },
  querySelectorAll: function (s) { return html.querySelectorAll(s); },
};
globalThis.MediaSource = { isTypeSupported: function () { return %(dolby)s; } };
globalThis.__observers = [];
globalThis.MutationObserver = function (cb) { this.cb = cb; };
MutationObserver.prototype.observe = function (target, opts) {
  __observers.push({cb: this.cb, opts: opts}); };
function attributesChanged() {
  __observers.filter(function (o) { return o.opts.attributes; }).forEach(function (o) { o.cb([]); });
}
function tracking(id) {
  return h("div", {"class": "ptrack-content",
    "data-ui-tracking-context": encodeURIComponent(JSON.stringify({video_id: id}))});
}
function line(items) { return h("div", {"class": "videoMetadata--line"}, "", items); }
function labels(l) { return l.children.map(function (c) {
  var badge = c.className === "player-feature-badge";
  return (c.style.display === "none" ? "~" : "") + (badge ? c.textContent : c.className); }); }
"""

PAGE = r"""
// A card for The Witcher (Atmos, 4K) and one for The Blacklist (5.1, 4K).
var witcher = line([h("div", {"class": "year"}, "2025"),
  h("svg", {"class": "svg-icon svg-icon-dolby-vision"}),
  h("div", {"class": "spatial-audio"}),
  h("div", {"class": "accessibility"}, "AD")]);
var blacklist = line([h("div", {"class": "year"}, "2014"),
  h("span", {"class": "player-feature-badge", "data-uia": "player-feature-badge-hd"}, "HD")]);
var unknown = line([h("div", {"class": "year"}, "2001")]);
body.appendChild(h("div", {"class": "titleCard--container"}, "", [tracking(81484026),
  h("div", {}, "", [h("div", {}, "", [witcher])])]));
body.appendChild(h("div", {"class": "titleCard--container"}, "", [tracking(70281312),
  h("div", {}, "", [blacklist])]));
body.appendChild(h("div", {"class": "titleCard--container"}, "", [tracking(1), unknown]));
"""

RESPONSE = {
    "data": {
        "videos": [
            {
                "videoId": 81484026,
                "playbackBadges": [
                    "VIDEO_HD",
                    "VIDEO_ULTRA_HD",
                    "VIDEO_DOLBY_VISION",
                    "AUDIO_DOLBY_ATMOS",
                    "AUDIO_SPATIAL",
                    "AUDIO_FIVE_DOT_ONE",
                ],
            },
            {
                "videoId": 70281312,
                "playbackBadges": ["VIDEO_HD", "VIDEO_ULTRA_HD", "AUDIO_FIVE_DOT_ONE"],
            },
        ]
    }
}


def run(check_dolby=False, dolby=True, preset=None, search="", path="/browse", extra=""):
    attrs = {"data-surroundflix-preset": preset} if preset else {}
    code = (
        FAKE_DOM
        % {
            "attrs": json.dumps(attrs),
            "search": json.dumps(search),
            "path": json.dumps(path),
            "dolby": "true" if dolby else "false",
        }
        + render_page_script("atmos", check_dolby=check_dolby)
        + PAGE
        + f"JSON.parse({json.dumps(json.dumps(RESPONSE))});\n"
        + extra
        + """
setTimeout(function () {
  console.log(JSON.stringify({witcher: labels(witcher), blacklist: labels(blacklist),
    unknown: labels(unknown), titles: window.__surroundflix.titlesWithBadges,
    extra: globalThis.__extra || null}));
}, 400);
"""
    )
    proc = subprocess.run([node, "-e", code], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_safari_shows_atmos_and_4k():
    out = run()
    assert out["witcher"] == [
        "year",
        "svg-icon svg-icon-dolby-vision",
        "spatial-audio",
        "Ultra HD 4K",
        "Dolby Atmos",
        "accessibility",
    ]
    assert out["titles"] == 2


def test_4k_replaces_netflix_hd_and_5_1_is_added():
    assert run()["blacklist"] == ["year", "~HD", "Ultra HD 4K", "5.1"]


def test_titles_netflix_did_not_describe_are_left_alone():
    assert run()["unknown"] == ["year"]


def test_chrome_without_dolby_shows_5_1_only():
    out = run(check_dolby=True, dolby=False)
    assert "Dolby Atmos" not in out["witcher"] and "5.1" in out["witcher"]
    assert "Ultra HD 4K" not in out["witcher"] + out["blacklist"]
    assert out["blacklist"] == ["year", "HD", "5.1"]


def test_surround_preset_shows_5_1():
    out = run(preset="surround")
    assert "Dolby Atmos" not in out["witcher"] and "5.1" in out["witcher"]


def test_redrawing_does_not_duplicate():
    parse = f"JSON.parse({json.dumps(json.dumps(RESPONSE))});"
    extra = "setTimeout(function () { " + parse + " }, 120);"
    out = run(extra=extra)
    assert out["witcher"].count("Dolby Atmos") == 1
    assert out["blacklist"].count("5.1") == 1


def test_reused_line_follows_new_title():
    # React reuses the card for another title: the badges follow it.
    extra = """
    setTimeout(function () {
      var card = blacklist.parentElement.parentElement;
      card.removeChild(card.children[0]);
      card.insertBefore(tracking(81484026), card.children[0]);
      JSON.parse('{"data":{"x":{"videoId":5,"playbackBadges":[]}}}');
    }, 150);
    """
    assert run(extra=extra)["blacklist"] == ["year", "~HD", "Ultra HD 4K", "Dolby Atmos"]


def test_reused_line_unknown_title_cleared():
    # The line now belongs to a title Netflix sent no badges for.
    extra = """
    setTimeout(function () {
      var card = blacklist.parentElement.parentElement;
      card.removeChild(card.children[0]);
      card.insertBefore(tracking(424242), card.children[0]);
      JSON.parse('{"data":{"x":{"videoId":5,"playbackBadges":[]}}}');
    }, 150);
    """
    assert run(extra=extra)["blacklist"] == ["year", "HD"]


def test_modal_id_from_jbv():
    extra = """
    var modal = line([h("span", {"class": "duration"}, "1 h")]);
    var outside = line([h("span", {"class": "duration"}, "2 h")]);
    body.appendChild(h("div", {"class": "detail-modal"}, "", [modal]));
    body.appendChild(h("div", {}, "", [outside]));
    setTimeout(function () { globalThis.__extra = [labels(modal), labels(outside)]; }, 200);
    """
    out = run(search="?jbv=70281312", extra=extra)
    assert out["extra"][0] == ["duration", "Ultra HD 4K", "5.1"]
    # A line outside the modal doesn't borrow the modal's title.
    assert out["extra"][1] == ["duration"]


def test_title_page_url_fallback():
    extra = """
    var own = line([h("span", {"class": "duration"}, "1 h")]);
    body.appendChild(h("div", {"class": "detail-modal"}, "", [own]));
    setTimeout(function () { globalThis.__extra = labels(own); }, 200);
    """
    assert run(path="/title/70281312", extra=extra)["extra"] == ["duration", "Ultra HD 4K", "5.1"]


def test_modal_similar_cards_ignored():
    extra = """
    var similar = line([h("span", {"class": "duration"}, "1 h")]);
    body.appendChild(h("div", {"class": "detail-modal"}, "", [
      h("div", {"class": "titleCard--container"}, "", [similar])]));
    setTimeout(function () { globalThis.__extra = labels(similar); }, 200);
    """
    assert run(search="?jbv=70281312", extra=extra)["extra"] == ["duration"]


def test_netflix_badges_are_not_repeated():
    extra = """
    var native = line([h("span", {"class": "player-feature-badge"}, "5.1")]);
    body.appendChild(h("div", {}, "", [tracking(70281312), native]));
    setTimeout(function () { globalThis.__extra = labels(native); }, 200);
    """
    assert run(extra=extra)["extra"] == ["5.1", "Ultra HD 4K"]


def test_badge_lists_are_sanitised():
    extra = """
    JSON.parse('{"data":{"v":[{"videoId":"<img>","playbackBadges":["AUDIO_FIVE_DOT_ONE"]},'
      + '{"videoId":9,"playbackBadges":[1,{"a":2},"AUDIO_FIVE_DOT_ONE"]}]}}');
    """
    assert run(extra=extra)["titles"] == 3


def test_badges_update_on_preset_change():
    # The popup switches to "5.1 only" while the page is open: Atmos becomes 5.1.
    extra = """
    setTimeout(function () {
      ATTRS["data-surroundflix-preset"] = "surround";
      attributesChanged();
    }, 150);
    """
    assert run(extra=extra)["witcher"][-2:] == ["5.1", "accessibility"]
