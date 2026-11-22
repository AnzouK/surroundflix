"""The command line and the macOS packaging, without macOS: Apple's tools
are replaced by fakes that record their arguments."""

import json
import plistlib
import subprocess
from pathlib import Path

import pytest

from surroundflix import build, package, playercore
from surroundflix.cli import main
from surroundflix.profiles import DDPLUS_ATMOS, EXPECTED_IN_PLAYERCORE, H264_MAIN


def test_presets_command(capsys):
    assert main(["presets"]) == 0
    out = capsys.readouterr().out
    assert "atmos (default)" in out and "surround:" in out


def test_build_command(tmp_path, capsys):
    assert main(["build", "--out", str(tmp_path), "--preset", "surround", "--debug"]) == 0
    assert "Chrome extension" in capsys.readouterr().out
    assert '"debug": true' in (tmp_path / "safari-webextension" / "page.js").read_text()


def test_xcode_dry_run_command(tmp_path, capsys):
    out, project = str(tmp_path / "d"), str(tmp_path / "x")
    args = ["xcode", "--out", out, "--project", project, "--dry-run", "--video-codec", "h264"]
    assert main(args) == 0
    assert "safari-web-extension-converter" in capsys.readouterr().out
    script = (tmp_path / "d" / "userscript" / "surroundflix.user.js").read_text()
    assert '"videoCodec": "h264"' in script


def test_check_refuses_bad_url(capsys):
    assert main(["check", "--url", "file:///etc/passwd"]) == 2
    assert "Refusing" in capsys.readouterr().err


def test_check_without_url_when_discovery_fails(monkeypatch, capsys):
    monkeypatch.setattr(playercore, "discover_url", lambda: None)
    assert main(["check"]) == 2


def test_check_reports_missing(tmp_path, capsys):
    core = tmp_path / "cadmium-playercore-6.3.js"
    core.write_text('"heaac-2-dash" profiles')
    assert main(["check", "--file", str(core)]) == 1
    assert "MISSING" in capsys.readouterr().out


def test_check_downloads_validated_url(monkeypatch, capsys):
    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return " ".join(f'"{n}"' for n in EXPECTED_IN_PLAYERCORE).encode()

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return Resp()

    monkeypatch.setattr(playercore, "_open", fake_urlopen)
    url = "https://assets.nflxext.com/player/html/ffe/cadmium-playercore-6.0064.915.911.js"
    assert main(["check", "--url", url, "--json"]) == 0
    assert seen["url"] == url
    assert json.loads(capsys.readouterr().out)["version"] == "6.0064.915.911"


def test_download_size_is_capped(monkeypatch):
    class Big:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b"x" * n

    monkeypatch.setattr(playercore, "_open", lambda req, timeout: Big())
    with pytest.raises(ValueError, match="larger"):
        playercore.load(url="https://assets.nflxext.com/huge.js")


@pytest.fixture
def fake_macos(monkeypatch, tmp_path):
    """Pretend to be macOS; record every Apple tool call and fake its output."""
    calls = []

    def fake_run(cmd, check=True, capture_output=False, text=False):
        calls.append(cmd)
        if cmd[:2] == ["xcrun", "--find"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="/usr/bin/converter")
        if cmd[:2] == ["xcrun", "safari-web-extension-converter"]:
            project = tmp_path / "work" / "xcode" / "Surroundflix"
            res = project / "Surroundflix" / "Resources"
            (res / "Base.lproj").mkdir(parents=True)
            (project / "Surroundflix.xcodeproj").mkdir()
            for name in ("Style.css", "Script.js", "Icon.png"):
                (res / name).write_text("apple")
            (res / "Base.lproj" / "Main.html").write_text("apple")
            with (project / "Surroundflix" / "Surroundflix.entitlements").open("wb") as fh:
                plistlib.dump({"com.apple.security.app-sandbox": True}, fh)
        if cmd[:2] == ["xcodebuild", "-list"]:
            schemes = {"project": {"schemes": ["Surroundflix Extension", "Surroundflix"]}}
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(schemes))
        if cmd[:2] == ["xcodebuild", "-project"]:
            app = (
                tmp_path
                / "work"
                / "derived"
                / "Build"
                / "Products"
                / "Release"
                / "Surroundflix.app"
            )
            (app / "Contents").mkdir(parents=True)
        if cmd[0] == "hdiutil":
            (tmp_path / "out" / "Surroundflix.dmg").write_text("dmg")
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    # Same result on Linux CI and on a real Mac, where lsregister exists.
    lsregister = tmp_path / "lsregister"
    lsregister.write_text("")
    monkeypatch.setattr(package, "LSREGISTER", str(lsregister))
    for mod in (package, build):
        monkeypatch.setattr(mod.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(mod.shutil, "which", lambda tool: "/usr/bin/" + tool)
        monkeypatch.setattr(mod.subprocess, "run", fake_run)
    return calls


def test_dmg_command(tmp_path, fake_macos, capsys):
    out = tmp_path / "out" / "Surroundflix.dmg"
    assert main(["dmg", "--work", str(tmp_path / "work"), "--output", str(out)]) == 0
    tools = [c[1] if c[0] == "xcrun" else Path(c[0]).name for c in fake_macos]
    assert tools == [
        "--find",
        "safari-web-extension-converter",
        "xcodebuild",
        "xcodebuild",
        "hdiutil",
        "lsregister",
    ]
    # The build copy is unregistered so Safari doesn't list the extension twice.
    assert fake_macos[-1][1:] == [
        "-u",
        str(tmp_path / "work" / "derived" / "Build" / "Products" / "Release" / "Surroundflix.app"),
    ]
    build_cmd = fake_macos[3]
    assert build_cmd[build_cmd.index("-scheme") + 1] == "Surroundflix"
    assert "CODE_SIGN_IDENTITY=-" in build_cmd
    for cmd in fake_macos:
        assert all(isinstance(arg, str) for arg in cmd)
    assert "Disk image" in capsys.readouterr().out
    note = tmp_path / "out" / "dmg-staging"
    assert not note.exists(), "staging folder is cleaned up"


def test_find_project_missing(tmp_path):
    with pytest.raises(RuntimeError):
        package._find_project(tmp_path)


def test_requires_xcode(monkeypatch):
    monkeypatch.setattr(package.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(package.shutil, "which", lambda tool: None)
    with pytest.raises(RuntimeError, match="Xcode"):
        package._require_macos()


def test_clt_error_message(tmp_path, fake_macos, monkeypatch, capsys):
    def no_converter(cmd, check=True, capture_output=False, text=False):
        return subprocess.CompletedProcess(cmd, 72, stdout="", stderr="unable to find utility")

    monkeypatch.setattr(build.subprocess, "run", no_converter)
    assert main(["dmg", "--work", str(tmp_path / "work"), "--output", str(tmp_path / "o.dmg")]) == 1
    err = capsys.readouterr().err
    assert "xcode-select -s /Applications/Xcode.app/Contents/Developer" in err
    assert "Traceback" not in err


def test_check_network_error_is_inconclusive(monkeypatch, capsys):
    import urllib.error

    def refused(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(playercore, "_open", refused)
    url = "https://assets.nflxext.com/x/cadmium-playercore-6.0.js"
    # 2, not 1: nothing was checked, so no "profile missing" issue.
    assert main(["check", "--url", url]) == 2


def test_check_cut_connection_is_inconclusive(monkeypatch):
    import http.client

    calls = []

    def cut(req, timeout):
        calls.append(req.full_url)
        raise http.client.IncompleteRead(b"")

    monkeypatch.setattr(playercore, "_open", cut)
    monkeypatch.setattr(playercore.time, "sleep", lambda s: None)
    url = "https://assets.nflxext.com/x/cadmium-playercore-6.0.js"
    assert main(["check", "--url", url]) == 2
    assert len(calls) == 3


def test_cut_download_is_retried(monkeypatch):
    import http.client

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return " ".join(f'"{n}"' for n in EXPECTED_IN_PLAYERCORE).encode()

    answers = [http.client.IncompleteRead(b"x" * 10), Resp()]

    def flaky(req, timeout):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(playercore, "_open", flaky)
    monkeypatch.setattr(playercore.time, "sleep", lambda s: None)
    assert main(["check", "--url", "https://assets.nflxext.com/x/cadmium-playercore-6.0.js"]) == 0


def test_cut_download_resumes(monkeypatch):
    import http.client

    body = " ".join(f'"{n}"' for n in EXPECTED_IN_PLAYERCORE).encode()
    ranges = []

    class Resp:
        headers = {"ETag": '"v1"'}

        def __init__(self, start, status, cut):
            self.start, self.status, self.cut = start, status, cut

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            if self.cut:
                raise http.client.IncompleteRead(body[self.start : self.start + 40])
            return body[self.start :]

    def cut_twice(req, timeout):
        header = req.get_header("Range")
        assert req.get_header("If-range") == ('"v1"' if header else None)
        ranges.append(header)
        start = int(header[len("bytes=") : -1]) if header else 0
        return Resp(start, 206 if header else 200, cut=len(ranges) < 3)

    def no_sleep(seconds):
        raise AssertionError("a try that made progress doesn't wait")

    monkeypatch.setattr(playercore, "_open", cut_twice)
    monkeypatch.setattr(playercore.time, "sleep", no_sleep)
    assert main(["check", "--url", "https://assets.nflxext.com/x/cadmium-playercore-6.0.js"]) == 0
    assert ranges == [None, "bytes=40-", "bytes=80-"]


def test_unsatisfiable_range_starts_over(monkeypatch):
    import http.client
    import urllib.error

    body = " ".join(f'"{n}"' for n in EXPECTED_IN_PLAYERCORE).encode()
    ranges = []

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            if len(ranges) == 1:
                raise http.client.IncompleteRead(body[:40])
            return body

    def shrunk(req, timeout):
        ranges.append(req.get_header("Range"))
        if len(ranges) == 2:
            raise urllib.error.HTTPError(req.full_url, 416, "Range Not Satisfiable", {}, None)
        return Resp()

    monkeypatch.setattr(playercore, "_open", shrunk)
    assert main(["check", "--url", "https://assets.nflxext.com/x/cadmium-playercore-6.0.js"]) == 0
    assert ranges == [None, "bytes=40-", None]


REPO_ROOT = Path(__file__).resolve().parents[1]
# Names come from profiles.py so these tests still pass after a rename.
OLD = H264_MAIN[-1]
NEW = OLD + "-v2"


def _fix_root(tmp_path):
    """A copy of the two files fix-profiles may change, under tmp_path."""
    for rel in ("src/surroundflix/profiles.py", "src/surroundflix/templates/page.js"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text((REPO_ROOT / rel).read_text())
    return tmp_path


def _fix(tmp_path, suggestions, missing=None):
    report = tmp_path / "report.json"
    missing = list(suggestions) if missing is None else missing
    report.write_text(json.dumps({"missing": missing, "suggestions": suggestions}))
    return main(["fix-profiles", "--report", str(report), "--root", str(tmp_path)])


def test_fix_profiles_renames_quoted(tmp_path, capsys):
    root = _fix_root(tmp_path)
    page = root / "src/surroundflix/templates/page.js"
    page.write_text(page.read_text() + f"\n// {OLD}\nvar x = 'x{OLD}';\n")
    assert _fix(root, {OLD: NEW}) == 0
    profiles = (root / "src/surroundflix/profiles.py").read_text()
    assert f'"{NEW}"' in profiles and f'"{OLD}"' not in profiles
    js = page.read_text()
    assert f'"{NEW}"' in js and f'"{OLD}"' not in js
    assert f"// {OLD}\n" in js and f"'x{OLD}'" in js  # only exact quoted literals
    assert f'"{H264_MAIN[3]}"' in js
    out = capsys.readouterr().out
    assert f"{OLD} -> {NEW}" in out and "page.js: 1 replaced" in out


@pytest.mark.parametrize(
    "bad",
    [
        NEW + '"; import os; "',
        "../../etc/passwd-dash",
        EXPECTED_IN_PLAYERCORE[0],
        "x" * 70 + "-dash",
        5,
        [],
    ],
)
def test_fix_profiles_refuses_invalid(tmp_path, capsys, bad):
    root = _fix_root(tmp_path)
    before = (root / "src/surroundflix/profiles.py").read_text()
    assert _fix(root, {OLD: bad}) == 1
    assert (root / "src/surroundflix/profiles.py").read_text() == before
    assert "refusing" in capsys.readouterr().err


def test_fix_profiles_refuses_unknown_old(tmp_path, capsys):
    root = _fix_root(tmp_path)
    assert _fix(root, {"ddplus-2.0-dash": "ddplus-2.0hq-dash"}) == 1
    assert "not a name Surroundflix checks" in capsys.readouterr().err


def test_fix_profiles_nothing_to_do(tmp_path, capsys):
    root = _fix_root(tmp_path)
    assert _fix(root, {OLD: None}) == 1
    assert "Nothing was renamed" in capsys.readouterr().out


def test_fix_profiles_skips_name_used_elsewhere(tmp_path, capsys):
    root = _fix_root(tmp_path)
    (root / "src/surroundflix/templates/content.js").write_text(f'x = "{DDPLUS_ATMOS}";')
    assert _fix(root, {DDPLUS_ATMOS: DDPLUS_ATMOS + "-v2"}) == 1
    assert "also used in content.js" in capsys.readouterr().out
    assert f'"{DDPLUS_ATMOS}"' in (root / "src/surroundflix/profiles.py").read_text()


def test_fix_profiles_partial(tmp_path, capsys):
    root = _fix_root(tmp_path)
    assert _fix(root, {OLD: NEW, DDPLUS_ATMOS: None}) == 2
    assert f'"{NEW}"' in (root / "src/surroundflix/profiles.py").read_text()
    assert "no likely new name" in capsys.readouterr().out


def test_fix_profiles_refuses_same_target(tmp_path, capsys):
    root = _fix_root(tmp_path)
    other = next(n for n in H264_MAIN if n != OLD)
    assert _fix(root, {OLD: NEW, other: NEW}) == 1
    assert "refusing" in capsys.readouterr().err


def test_fix_profiles_needs_files(tmp_path, capsys):
    assert _fix(tmp_path, {OLD: NEW}) == 1
    assert "not found" in capsys.readouterr().err


def test_check_json_has_suggestions(tmp_path, capsys):
    core = tmp_path / "cadmium-playercore-6.4.js"
    core.write_text(" ".join(f'"{n}"' for n in EXPECTED_IN_PLAYERCORE).replace(OLD, NEW))
    assert main(["check", "--file", str(core), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["suggestions"] == {OLD: NEW}
