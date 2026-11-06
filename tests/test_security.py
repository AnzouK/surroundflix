"""Security tests: permissions, untrusted page data, network destinations,
release links and the CI workflows."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from surroundflix import build, playercore
from surroundflix.build import REPO, shared_js

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "src" / "surroundflix" / "templates"
WORKFLOWS = ROOT / ".github" / "workflows"
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
def test_manifest_asks_for_the_minimum(dist, target):
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


# JavaScript (ESLint, run in CI, already bans eval, innerHTML and the like) ----


def all_js_templates():
    return sorted(TEMPLATES.rglob("*.js"))


@pytest.mark.parametrize("path", all_js_templates(), ids=lambda p: p.name)
def test_only_expected_network_destinations(path):
    urls = set(re.findall(r"https?://[^\s\"'`)]+", path.read_text()))
    allowed = ("https://api.github.com/repos/", "https://github.com/")
    assert all(u.startswith(allowed) for u in urls), urls
    # Only the app window talks to a server (GitHub's API, for updates);
    # shared.js just compares links with a github.com prefix.
    if path.name != "Script.js":
        assert not any("api.github.com" in u for u in urls), path.name
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
def test_content_script_answers_only_its_own_message():
    other, empty, own = run_content_script('{"received": ["ddplus-5.1-dash"]}')
    assert other == {"kept": False, "sent": []} and empty == {"kept": False, "sent": []}
    assert own["sent"] == [{"active": True, "status": {"received": ["ddplus-5.1-dash"]}}]


@needs_node
def test_content_script_ignores_an_oversized_status():
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
def test_page_controlled_preset_cannot_break_the_request(attr):
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
def test_update_link_must_point_to_this_repository(url, ok):
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
        ("v9999999999.0.0<img>", "0.1.0", True),
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
    ],
)
def test_playercore_accepts_netflix_hosts(url):
    assert playercore.validate_url(url) == url


# CI workflows --------------------------------------------------------------------


def workflows():
    return sorted(WORKFLOWS.glob("*.yml"))


@pytest.mark.parametrize("path", workflows(), ids=lambda p: p.name)
def test_workflow_is_hardened(path):
    data = yaml.safe_load(path.read_text())
    triggers = data.get(True, data.get("on"))  # YAML reads a bare `on` as True
    assert "permissions" in data, "set an explicit, least-privilege token"
    assert "pull_request_target" not in (triggers or {}), (
        "pull_request_target runs fork code with secrets"
    )
    for job in data["jobs"].values():
        if "uses" in job:  # calls a reusable workflow, which sets its own limits
            continue
        assert "timeout-minutes" in job
        for step in job.get("steps", []):
            run = step.get("run", "")
            # Untrusted values must go through env:, never straight into a shell.
            assert not re.search(
                r"\$\{\{\s*(github\.event|github\.head_ref|vars\.|inputs\.)", run
            ), step


def test_read_only_token_where_nothing_is_written():
    for name in ("ci.yml", "security.yml"):
        data = yaml.safe_load((WORKFLOWS / name).read_text())
        assert data["permissions"] == {"contents": "read"}, name


@pytest.mark.parametrize("path", workflows(), ids=lambda p: p.name)
def test_actions_are_pinned_by_commit(path):
    """A tag can be moved by whoever controls the action; a commit SHA can't."""
    for job in yaml.safe_load(path.read_text())["jobs"].values():
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if uses and not uses.startswith("./"):
                assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", uses), uses
