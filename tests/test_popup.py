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
El.prototype.addEventListener = function (type, fn) { this["on" + type] = fn; };
El.prototype.select = function () {};
El.prototype.focus = function () { document.activeElement = this; };
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
var radios = ["atmos", "surround", "netflix"].map(function (v) { var r = new El(); r._value = v; return r; });
var saved = {}, reloaded = null, closed = false;
globalThis.close = function () { closed = true; };
globalThis.window = globalThis;
var copied = null;
// Node 21+ has its own read-only navigator.
Object.defineProperty(globalThis, "navigator", { configurable: true, value: {
  languages: ["en-US"], userAgent: "TestBrowser/1.0",
  clipboard: { writeText: function (text) { copied = text; return Promise.resolve(); } } } });
globalThis.location = { search: %(search)s };
// A Mac without an AV1 decoder.
globalThis.MediaSource = { isTypeSupported: function (t) {
  return t.indexOf("av01") === -1 && (%(dolby)s || t.indexOf("ec-3") === -1); } };
globalThis.document = {
  documentElement: {},
  getElementById: getEl,
  querySelectorAll: function (s) { return s.indexOf("preset") !== -1 ? radios : []; },
  querySelector: function () { return radios.filter(function (r) { return r.checked; })[0] || null; },
  createElement: function () { return new El(); },
  createTextNode: function (text) { var n = new El(); n.textContent = text; return n; },
  body: new El("body"),
  activeElement: null,
  execCommand: function () { return false; },
};
"""


def run(search="", preset="atmos", storage=None, reply=None, then="", chrome=False):
    code = FAKE_DOM % {
        "search": json.dumps(search),
        "dolby": "false" if chrome else "true",
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
            f" sendMessage: function () {{ return Promise.resolve({json.dumps(reply)}); }},"
            " reload: function (id) { reloaded = id; return Promise.resolve(); }}};\n"
        )
    code += render_popup_script(preset, check_dolby=chrome)
    if then:
        code += f"setTimeout(function () {{ {then} }}, 20);\n"
    code += """
setTimeout(function () {
  console.log(JSON.stringify({status: getEl("tab-status").text(),
    debugHidden: getEl("debug").hidden, copied: copied, result: getEl("debug-result").textContent,
    preset: getEl("preset-desc").textContent, video: getEl("tab-video").text(),
    rangeHidden: getEl("tab-range").hidden, codec: getEl("video-codec").value,
    checked: radios.filter(function (r) { return r.checked; }).map(function (r) { return r.value; }),
    disabled: radios.filter(function (r) { return r.disabled; }).map(function (r) { return r.value; }),
    saved: saved, applyHidden: getEl("apply-now").hidden, reloaded: reloaded, closed: closed}));
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


def test_debug_button_hidden_without_netflix():
    assert run(storage={})["debugHidden"] is True


def test_debug_info_is_copied():
    click = 'getEl("copy-debug").onclick();'
    out = run(storage={"videoCodec": "hevc"}, reply=tab(720, 2160), then=click)
    assert out["debugHidden"] is False and out["result"] == EN["debug_copied"]
    info = json.loads(out["copied"])
    assert info["browser"] == "TestBrowser/1.0"
    assert info["settings"] == {"preset": "atmos", "videoQuality": "auto", "videoCodec": "hevc"}
    assert info["page"]["received"] == ["ddplus-5.1-dash"]


CHANGE_QUALITY = 'getEl("video-quality").value = "best"; getEl("video-quality").onchange();'


def test_apply_now_after_a_change():
    assert run(storage={}, reply=tab(720, 2160))["applyHidden"] is True
    out = run(storage={}, reply=tab(720, 2160), then=CHANGE_QUALITY)
    assert out["applyHidden"] is False and out["saved"] == {"videoQuality": "best"}


def test_apply_now_hidden_outside_netflix():
    assert run(storage={}, then=CHANGE_QUALITY)["applyHidden"] is True


def test_apply_now_reloads_the_tab():
    out = run(
        storage={}, reply=tab(720, 2160), then=CHANGE_QUALITY + 'getEl("apply-now").onclick();'
    )
    assert out["reloaded"] == 1 and out["closed"] is True


def copy_with(write, exec_command):
    return (
        f"navigator.clipboard.writeText = function () {{ return {write}; }};"
        f"document.execCommand = function () {{ return {exec_command}; }};"
        'getEl("copy-debug").onclick();'
    )


def test_debug_copy_fallback():
    out = run(storage={}, reply=tab(720, 2160), then=copy_with("Promise.reject(1)", "true"))
    assert out["result"] == EN["debug_copied"]


def test_debug_copy_failure():
    out = run(storage={}, reply=tab(720, 2160), then=copy_with("Promise.reject(1)", "false"))
    assert out["result"] == EN["debug_failed"]


def test_debug_info_keeps_known_fields():
    reply = tab(720, 2160)
    reply["status"]["injected"] = "x"
    out = run(storage={}, reply=reply, then='getEl("copy-debug").onclick();')
    assert "injected" not in json.loads(out["copied"])["page"]
    assert run(storage={}, reply={"active": True, "status": 42})["debugHidden"] is True
    assert run(storage={}, reply={"active": True, "status": {"x": 1}})["debugHidden"] is True


def test_netflix_preset_description():
    assert run(storage={"preset": "netflix"})["preset"] == EN["pdesc_netflix"]


def test_chrome_shows_5_1_only():
    out = run(storage={}, chrome=True)
    assert out["disabled"] == ["atmos"] and out["checked"] == ["surround"]
    assert out["preset"] == EN["pdesc_surround"]
    assert run(storage={"preset": "atmos"}, chrome=True)["checked"] == ["surround"]
    assert run(storage={"preset": "netflix"}, chrome=True)["checked"] == ["netflix"]
