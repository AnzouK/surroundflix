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
        "background",
    ):
        assert key not in manifest, f"{key} widens what the extension can do"
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
var listener = null, sent = [];
globalThis.chrome = {
  storage: {local: {get: function () { return Promise.resolve({}); }},
            onChanged: {addListener: function () {}}},
  runtime: {onMessage: {addListener: function (f) { listener = f; }}}};
var STATUS = %s;
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
