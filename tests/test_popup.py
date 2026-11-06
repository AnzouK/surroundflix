"""Runs popup.js under Node against a minimal DOM. The menus get the
<option> elements of the real popup.html."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from surroundflix.build import load_i18n, render_popup_script

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node is not installed")
EN = load_i18n()["strings"]["en"]


def options(select_id):
    html = (Path(__file__).parent.parent / "src/surroundflix/templates/popup.html").read_text()
    block = re.search(rf'<select id="{select_id}".*?</select>', html, re.S).group(0)
    tags = re.findall(r"<option[^>]*>", block)
    return [
        [
            re.search(r'value="([^"]+)"', tag).group(1),
            (re.findall(r'data-browser="([^"]+)"', tag) or [None])[0],
        ]
        for tag in tags
    ]


FAKE_DOM = r"""
function El(id) {
  this.id = id; this.children = []; this.textContent = ""; this._value = "";
  this.hidden = true; this.disabled = false; this.checked = false; this.attrs = {};
}
// Like a <select>: a value no <option> has leaves it empty.
Object.defineProperty(El.prototype, "value", {
  get: function () { return this._value; },
  set: function (v) {
    var known = this.children.some(function (c) { return c._value === v; });
    this._value = !this.children.length || known ? v : "";
  }
});
El.prototype.appendChild = function (c) { c.parent = this; this.children.push(c); return c; };
El.prototype.remove = function () {
  var self = this;
  this.parent.children = this.parent.children.filter(function (c) { return c !== self; });
};
El.prototype.addEventListener = function () {};
El.prototype.querySelectorAll = function () { return this.children.slice(); };
El.prototype.getAttribute = function (k) { return this.attrs[k] || null; };
El.prototype.text = function () {
  return this.textContent + this.children.map(function (c) { return c.textContent; }).join("");
};
var els = {};
function getEl(id) { return els[id] || (els[id] = new El(id)); }
function fill(id, list) {
  list.forEach(function (o) {
    var opt = new El(); opt._value = o[0];
    if (o[1]) opt.attrs["data-browser"] = o[1];
    getEl(id).appendChild(opt);
  });
}
fill("video-quality", %(quality)s);
fill("video-codec", %(codec)s);
var radios = ["atmos", "surround"].map(function (v) { var r = new El(); r._value = v; return r; });
var saved = {};
globalThis.window = globalThis;
globalThis.navigator = { languages: ["en-US"] };
globalThis.location = { search: %(search)s };
// A Mac without an AV1 decoder.
globalThis.MediaSource = { isTypeSupported: function (t) { return t.indexOf("av01") === -1; } };
globalThis.document = {
  documentElement: {},
  getElementById: getEl,
  querySelectorAll: function (s) { return s.indexOf("preset") !== -1 ? radios : []; },
  querySelector: function () { return radios.filter(function (r) { return r.checked; })[0] || null; },
  createElement: function () { return new El(); },
  createTextNode: function (text) { var n = new El(); n.textContent = text; return n; },
};
"""


def run(search="", preset="atmos", storage=None, reply=None):
    code = FAKE_DOM % {
        "search": json.dumps(search),
        "quality": json.dumps(options("video-quality")),
        "codec": json.dumps(options("video-codec")),
    }
    if storage is not None or reply is not None:
        code += (
            "globalThis.chrome = {storage: {local: {"
            f"get: function () {{ return Promise.resolve({json.dumps(storage or {})}); }},"
            " set: function (x) { Object.assign(saved, x); }}},"
            " tabs: {query: function () {"
            " return Promise.resolve([{id: 1, url: 'https://www.netflix.com/watch/1'}]); },"
            f" sendMessage: function () {{ return Promise.resolve({json.dumps(reply)}); }}}}}};\n"
        )
    code += render_popup_script(preset, check_dolby=False)
    code += """
setTimeout(function () {
  console.log(JSON.stringify({status: getEl("tab-status").text(),
    preset: getEl("preset-desc").textContent, video: getEl("tab-video").text(),
    rangeHidden: getEl("tab-range").hidden, codec: getEl("video-codec").value,
    checked: radios.filter(function (r) { return r.checked; }).map(function (r) { return r.value; }),
    saved: saved}));
}, 50);
"""
    proc = subprocess.run([node, "-e", code], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def tab(min_height, max_height):
    video = {"mode": "auto", "height": 1080, "bitrate": 5000, "codec": "h264"}
    video.update(minHeight=min_height, maxHeight=max_height)
    return {"active": True, "status": {"received": ["ddplus-5.1-dash"], "video": video}}


def test_demo_preview_outside_extension():
    out = run(search="?demo=atmos")
    assert "Dolby Atmos" in out["status"]
    assert "2160p" in out["video"] and out["rangeHidden"] is False


def test_description_matches_default_preset():
    assert run(preset="surround")["preset"] == EN["pdesc_surround"]


def test_stored_preset_updates_description():
    assert run(storage={"preset": "surround"})["preset"] == EN["pdesc_surround"]


def test_unknown_stored_preset_falls_back():
    assert run(preset="surround", storage={"preset": "dts"})["checked"] == ["surround"]


def test_undecodable_stored_codec_resets_to_auto():
    out = run(storage={"videoCodec": "av1"})
    assert out["codec"] == "auto" and out["saved"] == {"videoCodec": "auto"}


def test_video_range():
    assert run(reply=tab(720, 2160))["rangeHidden"] is False
    out = run(reply=tab(2160, 720))
    assert out["video"] and out["rangeHidden"] is True
