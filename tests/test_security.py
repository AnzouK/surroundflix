"""Security tests.

Surroundflix runs inside netflix.com, next to code it doesn't control, and
its app talks to GitHub. These tests pin down the promises made in
SECURITY.md and PRIVACY.md: minimal permissions, no string-to-code or
string-to-HTML paths, page-controlled data treated as untrusted, only
expected network destinations, and hardened CI workflows.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from surroundflix import build, playercore, xcode
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


# JavaScript: no string-to-code or string-to-HTML ---------------------------

DANGEROUS = re.compile(
    r"\beval\s*\(|new\s+Function\s*\(|\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML"
    r"|document\.write|set(?:Timeout|Interval)\s*\(\s*['\"`]|javascript:"
)


def all_js_templates():
    return sorted(TEMPLATES.rglob("*.js"))


@pytest.mark.parametrize("path", all_js_templates(), ids=lambda p: p.name)
def test_no_dangerous_sinks(path):
    hits = [line for line in path.read_text().splitlines() if DANGEROUS.search(line)]
    assert not hits, hits


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


def test_content_script_answers_only_its_own_message():
    src = (TEMPLATES / "content.js").read_text()
    assert 'message.type !== "surroundflix-status"' in src
    assert "onMessageExternal" not in src


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


def test_app_renders_update_text_without_html():
    src = (TEMPLATES / "app" / "Script.js").read_text()
    assert "isTrustedReleaseUrl(release.html_url, REPO)" in src
    assert "textContent" in src and "createTextNode" in src


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

    monkeypatch.setattr(playercore.urllib.request, "urlopen", boom)
    with pytest.raises(ValueError):
        playercore.load(url="file:///etc/passwd")


@pytest.mark.parametrize(
    "url",
    [
        "https://assets.nflxext.com/player/html/ffe/cadmium-playercore-6.0064.915.911.js",
        "https://www.netflix.com/",
    ],
)
def test_playercore_accepts_netflix_hosts(url):
    assert playercore.validate_url(url) == url


def test_app_opens_only_https_links_outside():
    assert 'url.scheme == "https"' in xcode.LINK_METHOD
    assert ".linkActivated" in xcode.LINK_METHOD


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


# Repository hygiene --------------------------------------------------------------


def tracked_text_files():
    skip = {".png", ".pyc"}
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).parts
        if not path.is_file() or path.suffix in skip:
            continue
        if (
            rel[0] in {".git", ".venv", "dist", "build", "release", ".idea", ".pytest_cache"}
            or "egg-info" in rel[0]
        ):
            continue
        if "__pycache__" in rel:
            continue
        yield path


def test_no_personal_paths_or_secrets_in_the_repository():
    pattern = re.compile(
        r"/Users/[a-z]|-----BEGIN [A-Z ]*PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}"
        r"|[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com|anthropic\.com|fsf\.org)[A-Za-z0-9-]+\.[a-z]{2,}"
    )
    me = Path(__file__).name
    hits = []
    for path in tracked_text_files():
        if path.name in {me, "LICENSE"}:
            continue
        for i, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()[:80]}")
    assert not hits, hits
