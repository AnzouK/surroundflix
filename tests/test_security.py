"""Security tests: permissions, untrusted page data, network destinations,
release links and the CI workflows."""

import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pytest

from surroundflix import build, playercore
from surroundflix.build import REPO, shared_js

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "src" / "surroundflix" / "templates"
NETFLIX = ["https://www.netflix.com/*"]
node = shutil.which("node")
needs_node = pytest.mark.skipif(node is None, reason="node is not installed")


def run_js(code: str) -> str:
    return subprocess.run(
        [node, "-e", code], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    return build.build(tmp_path_factory.mktemp("dist"))


# Extension manifests -------------------------------------------------------


@pytest.mark.parametrize("target", ["webextension", "chrome"])
def test_minimal_manifest_permissions(dist, target):
    manifest = json.loads((getattr(dist, target) / "manifest.json").read_text())
    assert manifest["permissions"] == ["storage"]
    for key in (
        "host_permissions",
        "optional_permissions",
        "optional_host_permissions",
        "externally_connectable",
        "content_security_policy",
    ):
        assert key not in manifest, f"{key} widens what the extension can do"
    # One background script, for the label on the toolbar button.
    background = manifest["background"]
    assert background.get("service_worker", background.get("scripts")) in (
        "background.js",
        ["background.js"],
    )
    assert not background.get("persistent", False)
    for cs in manifest["content_scripts"]:
        assert cs["matches"] == NETFLIX
        assert not cs.get("all_frames", False)


def test_safari_exposes_only_page_js_to_netflix(dist):
    manifest = json.loads((dist.webextension / "manifest.json").read_text())
    assert manifest["web_accessible_resources"] == [{"resources": ["page.js"], "matches": NETFLIX}]


def test_chrome_exposes_nothing(dist):
    manifest = json.loads((dist.chrome / "manifest.json").read_text())
    assert "web_accessible_resources" not in manifest


def test_userscript_header(dist):
    header = dist.userscript.read_text().split("// ==/UserScript==")[0]
    assert re.findall(r"@match\s+(\S+)", header) == NETFLIX
    assert re.findall(r"@grant\s+(\S+)", header) == ["none"]
    for key in ("updateURL", "downloadURL"):
        url = re.search(rf"@{key}\s+(\S+)", header).group(1)
        assert url.startswith(f"https://github.com/{REPO}/releases/")


# JavaScript -------------------------------------------------------------------


def all_js_templates():
    return sorted(TEMPLATES.rglob("*.js"))


@pytest.mark.parametrize("path", all_js_templates(), ids=lambda p: p.name)
def test_only_expected_network_destinations(path):
    urls = set(re.findall(r"https?://[^\s\"'`)]+", path.read_text()))
    hosts = {urlparse(u).hostname for u in urls}
    assert all(u.startswith("https://") for u in urls), urls
    assert hosts <= {"api.github.com", "github.com"}, hosts
    # Only the app window talks to a server (GitHub's API, for updates);
    # shared.js only checks release links.
    if path.name != "Script.js":
        assert "api.github.com" not in hosts, path.name
    if path.name not in {"Script.js", "shared.js"}:
        assert not urls, f"{path.name} should not reference any server: {urls}"


CONTENT_HARNESS = r"""
var listener = null, sent = [], badges = [], statusChanged = null;
globalThis.chrome = {
  storage: {local: {get: function () { return Promise.resolve({}); }},
            onChanged: {addListener: function () {}}},
  runtime: {onMessage: {addListener: function (f) { listener = f; }},
            sendMessage: function (m) { badges.push(m); return Promise.resolve(); }}};
var STATUS = %s;
globalThis.location = {pathname: "/watch/81484026"};
globalThis.MutationObserver = function (f) { statusChanged = f; };
MutationObserver.prototype.observe = function () {};
globalThis.setInterval = function () {};
globalThis.window = globalThis;
globalThis.addEventListener = function () {};
globalThis.document = {documentElement: {
  getAttribute: function (k) { return k === "data-surroundflix-status" ? STATUS : null; },
  setAttribute: function () {}}};
%s
var answers = [];
[{type: "other"}, null, {type: "surroundflix-status"}].forEach(function (m) {
  sent = [];
  var kept = listener(m, {}, function (r) { sent.push(r); });
  answers.push({kept: kept, sent: sent});
});
console.log(JSON.stringify(answers));
"""


def run_content_script(status):
    content = build._fill(build._template("content.js"), {"INJECT": False})
    return json.loads(run_js(CONTENT_HARNESS % (json.dumps(status), content)))


@needs_node
def test_content_script_filters_messages():
    other, empty, own = run_content_script('{"received": ["ddplus-5.1-dash"]}')
    assert other == {"kept": False, "sent": []} and empty == {"kept": False, "sent": []}
    assert own["sent"] == [{"active": True, "status": {"received": ["ddplus-5.1-dash"]}}]


@needs_node
def test_content_script_ignores_oversized_status():
    huge = json.dumps({"received": ["x" * 20000]})
    assert run_content_script(huge)[2]["sent"][0]["status"] is None


BADGE_STEPS = r"""
function label() { return badges.length ? badges[badges.length - 1].label : null; }
var seen = [label()];
[%s].forEach(function (step) {
  if (step.path) location.pathname = step.path;
  if ("status" in step) STATUS = step.status;
  statusChanged();
  seen.push(label());
});
console.log(JSON.stringify({seen: seen, count: badges.length}));
"""


def badge_labels(first, *steps):
    content = build._fill(build._template("content.js"), {"INJECT": False})
    harness = CONTENT_HARNESS.split("var answers")[0] % (json.dumps(first), content)
    return json.loads(run_js(harness + BADGE_STEPS % ",".join(json.dumps(s) for s in steps)))


@needs_node
def test_badge_matches_received_audio():
    atmos = json.dumps({"received": ["heaac-2-dash", "ddplus-5.1-dash", "ddplus-atmos-dash"]})
    aac = json.dumps({"received": ["heaac-2-dash", "heaac-5.1-dash"]})
    stereo = json.dumps({"received": ["heaac-2-dash"]})
    out = badge_labels(None, {"status": atmos}, {"status": aac}, {"status": stereo})
    assert out["seen"] == ["", "ATM", "5.1", ""]


@needs_node
def test_badge_only_on_watch_pages():
    atmos = json.dumps({"received": ["ddplus-atmos-dash"]})
    out = badge_labels(atmos, {"path": "/browse"}, {"path": "/browse"}, {"path": "/watch/1"})
    assert out["seen"] == ["ATM", "", "", "ATM"]
    assert out["count"] == 3  # nothing is sent when the label doesn't change


@needs_node
def test_badge_ignores_forged_status():
    for forged in (
        '{"received": "ddplus-atmos-dash"}',
        '{"received": [5.1, {"a": 1}]}',
        "not json",
    ):
        assert badge_labels(forged)["seen"] == [""]


ATMOS = {"received": ["ddplus-atmos-dash"], "video": {"height": 2160}}
STEREO = {"received": ["heaac-2-dash"], "video": {"height": 720}}


def with_titles(titles):
    return json.dumps({**STEREO, "titles": titles})


@needs_node
def test_status_follows_open_title():
    status = with_titles({"1": ATMOS, "2": STEREO})
    out = badge_labels(None, {"path": "/watch/1", "status": status}, {"path": "/watch/2"})
    assert out["seen"] == ["", "ATM", ""]
    # The latest manifest is another title's: nothing to report for this one.
    other = json.dumps({**ATMOS, "title": "2", "titles": {"2": ATMOS}})
    assert badge_labels(other, {"path": "/watch/3"})["seen"] == ["", ""]
    # It came without an id: it stands in, as before.
    latest = json.dumps({**ATMOS, "title": None, "titles": {"2": STEREO}})
    assert badge_labels(latest, {"path": "/watch/3"})["seen"] == ["ATM", "ATM"]


@needs_node
def test_popup_gets_open_title():
    harness = CONTENT_HARNESS.replace('"/watch/81484026"', '"/watch/1"')
    content = build._fill(build._template("content.js"), {"INJECT": False})
    code = harness % (json.dumps(with_titles({"1": ATMOS, "2": STEREO})), content)
    reply = json.loads(run_js(code))[2]["sent"][0]
    assert reply == {"active": True, "status": ATMOS}
    # Outside the player, a trailer's manifest is not reported.
    code = CONTENT_HARNESS.replace('"/watch/81484026"', '"/browse"') % (
        json.dumps(json.dumps(ATMOS)),
        content,
    )
    reply = json.loads(run_js(code))[2]["sent"][0]
    assert reply == {"active": True, "status": {"received": None, "video": None}}


@needs_node
def test_forged_titles_ignored():
    forgeries = [
        '"x"',
        "[1, 2]",
        "null",
        '{"1": "x"}',
        '{"1": ["a"]}',
        '{"1": null}',
        '{"__proto__": {"received": []}}',
    ]
    for forged in forgeries:
        status = '{"received": ["ddplus-atmos-dash"], "titles": ' + forged + "}"
        assert badge_labels(None, {"path": "/watch/1", "status": status})["seen"] == ["", "ATM"]
    # Fields of the wrong type are dropped, not passed on.
    status = '{"received": ["ddplus-atmos-dash"], "titles": {"1": {"received": 123, "video": 456}}}'
    assert badge_labels(None, {"path": "/watch/1", "status": status})["seen"] == ["", ""]
    # A "__proto__" key stays an own key: nothing is polluted.
    status = '{"received": ["heaac-2-dash"], "titles": {"__proto__": {"received": 1}}}'
    content = build._fill(build._template("content.js"), {"INJECT": False})
    code = (CONTENT_HARNESS % (json.dumps(status), content)).replace(
        "console.log(JSON.stringify(answers));",
        "console.log(JSON.stringify({answers: answers, leaked: ({}).received || null}));",
    )
    out = json.loads(run_js(code))
    assert out["leaked"] is None
    assert out["answers"][2]["sent"][0]["status"] == {"received": ["heaac-2-dash"]}


BACKGROUND_HARNESS = r"""
var listener = null, calls = [];
globalThis.chrome = {
  runtime: {onMessage: {addListener: function (f) { listener = f; }}},
  action: {setBadgeBackgroundColor: function () { throw new Error("unsupported"); },
           setBadgeText: function (d) { calls.push(d); return Promise.resolve(); }}};
%s
[%s].forEach(function (m) { listener(m[0], m[1]); });
console.log(JSON.stringify(calls));
"""


@needs_node
def test_background_only_sets_known_labels():
    tab = {"tab": {"id": 7}}
    messages = [
        [{"type": "surroundflix-badge", "label": "ATM"}, tab],
        [{"type": "surroundflix-badge", "label": "5.1"}, tab],
        [{"type": "surroundflix-badge", "label": "<b>free money</b>"}, tab],
        [{"type": "surroundflix-badge", "label": "ATM"}, {}],
        [{"type": "surroundflix-status"}, tab],
        [None, tab],
    ]
    code = BACKGROUND_HARNESS % (
        build._template("background.js"),
        ",".join(json.dumps(m) for m in messages),
    )
    assert json.loads(run_js(code)) == [
        {"tabId": 7, "text": "ATM"},
        {"tabId": 7, "text": "5.1"},
        {"tabId": 7, "text": ""},
    ]


# Data from the page is untrusted ---------------------------------------------

PAGE_HARNESS = r"""
globalThis.window = globalThis;
globalThis.document = { documentElement: { getAttribute: () => %s, setAttribute: () => {} } };
%s
const req = {params: {profiles: ["heaac-2-dash"]}};
console.log(JSON.stringify(JSON.parse(JSON.stringify(req)).params.profiles));
"""


@needs_node
@pytest.mark.parametrize(
    "attr", ["constructor", "__proto__", "toString", "hasOwnProperty", "", "x" * 5000]
)
def test_invalid_preset_attr_ignored(attr):
    out = json.loads(run_js(PAGE_HARNESS % (json.dumps(attr), build.render_page_script("atmos"))))
    assert out == ["heaac-2-dash", *build.PRESETS["atmos"]]
    assert all(isinstance(p, str) for p in out)


@needs_node
@pytest.mark.parametrize(
    "forged",
    ['"ddplus-atmos-dash"', "{}", "null", "42", '{"indexOf": 1}', '[{"x": 1}]'],
)
def test_forged_status_shows_nothing(forged):
    assert run_js(shared_js() + f"\nconsole.log(JSON.stringify(bestAudio({forged})));") == "null"


@needs_node
@pytest.mark.parametrize(
    "url,ok",
    [
        (f"https://github.com/{REPO}/releases/tag/v1.0.0", True),
        (f"https://github.com/{REPO}/releases/latest", True),
        ("javascript:alert(1)", False),
        (f"http://github.com/{REPO}/releases/tag/v1.0.0", False),
        ("https://github.com/someone-else/surroundflix/releases/tag/v9", False),
        (f"https://github.com/{REPO}evil/releases/", False),
        (f"https://github.com/{REPO}/releases.evil.com/", False),
        (f'https://github.com/{REPO}/releases/x" onclick="y', False),
        (f"https://github.com/{REPO}/releases/../../evil/repo/releases/tag/v9", False),
        (f"https://github.com/{REPO}/releases/%2e%2e/%2e%2e/evil/x", False),
        (f"https://user@github.com/{REPO}/releases/tag/v1", False),
        (f"https://github.com:8443/{REPO}/releases/tag/v1", False),
        (None, False),
        (42, False),
    ],
)
def test_update_url_validation(url, ok):
    code = (
        shared_js() + f"\nconsole.log(isTrustedReleaseUrl({json.dumps(url)}, {json.dumps(REPO)}));"
    )
    assert run_js(code) == ("true" if ok else "false")


@needs_node
@pytest.mark.parametrize(
    "candidate,current,newer",
    [
        ("v1.0.0", "0.1.0", True),
        ("1.2.10", "1.2.9", True),
        ("v1.10.0", "1.9.0", True),
        ("v1.9.0", "1.10.0", False),
        ("v0.1.0", "0.1.0", False),
        ("v1.0.0-beta", "1.0.0", False),
        ("garbage", "0.1.0", False),
        (None, "0.1.0", False),
        ("v2.0.0-beta", "1.0.0", False),
        ("v9.0.0<img>", "0.1.0", False),
        ("v9999999999.0.0", "0.1.0", False),
    ],
)
def test_version_comparison_is_strict(candidate, current, newer):
    code = (
        shared_js()
        + f"\nconsole.log(isNewerVersion({json.dumps(candidate)}, {json.dumps(current)}));"
    )
    assert run_js(code) == ("true" if newer else "false")


# Python side -------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://assets.nflxext.com/player.js",
        "https://example.com/cadmium-playercore.js",
        "https://nflxext.com.evil.example/x.js",
        "https://evilnflxext.com/x.js",
        "ftp://assets.nflxext.com/x.js",
        "https://user@evil.example/assets.nflxext.com/x.js",
        "https://user:pass@assets.nflxext.com/x.js",
        "https://assets.nflxext.com:8443/x.js",
        "https://assets.nflxext.com:99999/x.js",
    ],
)
def test_playercore_refuses_unexpected_urls(url):
    with pytest.raises(ValueError):
        playercore.validate_url(url)


def test_playercore_refuses_before_any_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("urlopen must not be reached")

    monkeypatch.setattr(playercore, "_open", boom)
    with pytest.raises(ValueError):
        playercore.load(url="file:///etc/passwd")


@pytest.mark.parametrize(
    "target", ["http://169.254.169.254/latest/meta-data", "https://evil.example/x.js"]
)
def test_playercore_redirects_are_checked(target):
    import urllib.request

    handler = playercore._CheckedRedirects()
    req = urllib.request.Request("https://assets.nflxext.com/x.js")
    with pytest.raises(ValueError):
        handler.redirect_request(req, None, 302, "Found", {}, target)


@pytest.mark.parametrize(
    "url",
    [
        "https://assets.nflxext.com/player/html/ffe/cadmium-playercore-6.0064.915.911.js",
        "https://www.netflix.com/",
        "https://www.netflix.com:443/browse",
    ],
)
def test_playercore_accepts_netflix_hosts(url):
    assert playercore.validate_url(url) == url


# Playback log (content.js) -----------------------------------------------------

HISTORY_HARNESS = r"""
var statusChanged = null, writes = [], changed = null;
var STORED = %(stored)s, STATUS = null, TITLE = null, NOW = 1.8e12, PRIVATE = false;
Date.now = function () { return NOW; };
globalThis.chrome = {
  storage: {local: {get: function () { return Promise.resolve(STORED); },
                    set: function (x) { writes.push(x.history); return Promise.resolve(); }},
            onChanged: {addListener: function (f) { changed = f; }}},
  extension: {get inIncognitoContext() { return PRIVATE; }},
  runtime: {onMessage: {addListener: function () {}},
            sendMessage: function () { return Promise.resolve(); }}};
globalThis.location = {pathname: "/watch/1"};
globalThis.MutationObserver = function (f) { statusChanged = f; };
MutationObserver.prototype.observe = function () {};
globalThis.setInterval = function () {};
globalThis.window = globalThis;
globalThis.addEventListener = function () {};
globalThis.document = {
  documentElement: {
    getAttribute: function (k) { return k === "data-surroundflix-status" ? STATUS : null; },
    setAttribute: function () {}},
  querySelector: function (s) {
    if (s !== '[data-uia="video-title"]' || TITLE === null) return null;
    return {childNodes: TITLE.map(function (t) { return {textContent: t}; })};
  }};
%(content)s
setTimeout(function () {
  [%(steps)s].forEach(function (step) {
    if (step.path) location.pathname = step.path;
    if ("status" in step) STATUS = step.status === null ? null : JSON.stringify(step.status);
    if ("title" in step) TITLE = step.title;
    if (step.wait) NOW += step.wait;
    if ("enabled" in step) changed({historyEnabled: {newValue: step.enabled}}, "local");
    if (step.clear) changed({history: {newValue: []}}, "local");
    if ("private" in step) PRIVATE = step.private;
    statusChanged();
  });
  console.log(JSON.stringify(writes));
}, 10);
"""

ATMOS_4K = {
    "received": ["heaac-2-dash", "ddplus-5.1-dash", "ddplus-atmos-dash"],
    "video": {"height": 2160, "codec": "hevc", "dynamicRange": "dv", "bitrate": 10400},
}


def history_writes(*steps, stored=None):
    content = build._fill(build._template("content.js"), {"INJECT": False})
    code = HISTORY_HARNESS % {
        "stored": json.dumps(stored or {}),
        "content": content,
        "steps": ",".join(json.dumps(s) for s in steps),
    }
    return json.loads(run_js(code))


def logged(title_id, at=1.8e12, **fields):
    entry = dict.fromkeys(["audio", "height", "codec", "hdr", "bitrate"])
    return {"id": title_id, "at": at, **entry, **fields}


@needs_node
def test_history_records_title():
    writes = history_writes({"status": ATMOS_4K, "title": ["  Example\nSeries ", "   ", "E1"]})
    assert writes == [
        [
            {
                "id": "1",
                "at": 1800000000000,
                "audio": "ddplus-atmos-dash",
                "height": 2160,
                "codec": "hevc",
                "hdr": "dv",
                "bitrate": 10400,
                "name": "Example Series E1",
            }
        ]
    ]


@needs_node
def test_history_stereo_and_no_name():
    writes = history_writes({"status": {"received": ["heaac-2-dash"]}})
    assert writes == [[logged("1", audio="stereo")]]


@needs_node
def test_history_skips_without_title():
    assert history_writes({"path": "/browse", "status": ATMOS_4K}) == []
    assert history_writes({"status": None}) == []
    assert history_writes({"status": {"received": None, "video": None}}) == []
    # Another title's manifest is not this one's.
    other = {**ATMOS_4K, "title": "2", "titles": {"2": ATMOS_4K}}
    assert history_writes({"status": other}) == []


@needs_node
def test_history_disabled():
    assert history_writes({"status": ATMOS_4K}, stored={"historyEnabled": False}) == []
    writes = history_writes({"enabled": False, "status": ATMOS_4K})
    assert writes == []


@needs_node
def test_history_watched_again_moves_up_with_new_date():
    stored = {"history": [logged("2", audio="stereo"), logged("1", at=1.7e12, audio="stereo")]}
    writes = history_writes({"status": ATMOS_4K}, stored=stored)
    assert [e["id"] for e in writes[-1]] == ["1", "2"]
    assert writes[-1][0]["at"] == 1.8e12 and writes[-1][0]["audio"] == "ddplus-atmos-dash"


@needs_node
def test_history_same_viewing_keeps_date():
    stored = {"history": [logged("1", at=1.8e12 - 60000, audio="stereo")]}
    writes = history_writes({"status": ATMOS_4K}, stored=stored)
    assert writes[-1][0]["at"] == 1.8e12 - 60000
    assert writes[-1][0]["audio"] == "ddplus-atmos-dash"


@needs_node
def test_history_last_title_watched_days_later():
    stored = {"history": [logged("1", at=1.7e12, audio="stereo")]}
    writes = history_writes({"status": ATMOS_4K}, stored=stored)
    assert writes[-1][0]["at"] == 1.8e12


@needs_node
def test_history_private_window():
    assert history_writes({"private": True, "status": ATMOS_4K}) == []


@needs_node
def test_history_clear_while_playing():
    atmos = {"audio": "ddplus-atmos-dash", "height": 2160, "codec": "hevc", "hdr": "dv"}
    writes = history_writes(
        {"status": ATMOS_4K}, {"clear": True, "wait": 30000}, {"path": "/watch/2"}
    )
    # The title playing when the log was cleared isn't added back, the next one is.
    assert writes == [
        [logged("1", bitrate=10400, **atmos)],
        [logged("2", at=1.8e12 + 30000, bitrate=10400, **atmos)],
    ]


@needs_node
def test_history_video_only():
    writes = history_writes({"status": {"received": None, "video": {"height": 720}}})
    assert writes == [[logged("1", height=720)]]


@needs_node
def test_history_writes_only_changes():
    stored = {"history": [logged("1", audio="ddplus-atmos-dash", height=2160, codec="hevc")]}
    stored["history"][0].update(hdr="dv", bitrate=10400)
    assert history_writes({"status": ATMOS_4K}, {"wait": 30000}, stored=stored) == []
    # A name seen once is kept when the controls hide it again.
    writes = history_writes(
        {"status": ATMOS_4K, "title": ["Example"]}, {"title": None, "wait": 30000}
    )
    assert len(writes) == 1 and writes[0][0]["name"] == "Example"


@needs_node
def test_history_cap():
    stored = {"history": [logged(str(n), audio="stereo") for n in range(100, 140)]}
    writes = history_writes({"status": ATMOS_4K}, stored=stored)
    assert len(writes[0]) == 30 and writes[0][0]["id"] == "1"
    assert writes[0][-1]["id"] == "128"


@needs_node
def test_history_drops_forged_values():
    forged = {
        "received": [5.1, {"a": 1}],
        "video": {
            "height": 1e9,
            "codec": "<b>",
            "dynamicRange": "__proto__",
            "bitrate": "5000",
        },
    }
    assert history_writes({"status": forged}) == []
    forged["video"]["bitrate"] = 5000
    writes = history_writes({"status": forged, "title": ["x" * 500]})
    assert writes == [[logged("1", bitrate=5000, name="x" * 80)]]
    junk = [
        "x",
        None,
        {"id": "1e3", "at": 1.8e12, "audio": "stereo"},
        {"id": "5", "at": "now", "audio": "stereo"},
        {"id": "6", "at": 1.8e12, "audio": "<b>", "bitrate": 1e12},
        {"id": "7", "at": 1.8e12, "audio": "stereo", "name": 42, "extra": "y"},
    ]
    writes = history_writes({"status": ATMOS_4K}, stored={"history": junk})
    assert [e["id"] for e in writes[0]] == ["1", "7"] and "extra" not in writes[0][1]


@needs_node
def test_history_throttle():
    steps = [{"status": {"received": ["heaac-2-dash"]}}, {"status": ATMOS_4K, "wait": 4000}]
    steps.append({"wait": 4000})
    assert len(history_writes(*steps)) == 1
    writes = history_writes(*steps, {"wait": 4000})
    assert [w[0]["audio"] for w in writes] == ["stereo", "ddplus-atmos-dash"]
