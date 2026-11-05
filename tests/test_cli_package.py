"""The command line and the macOS packaging, without macOS: Apple's tools
are replaced by fakes that record their arguments."""

import json
import plistlib
import subprocess

import pytest

from surroundflix import build, package, playercore
from surroundflix.cli import main


def test_presets_command(capsys):
    assert main(["presets"]) == 0
    out = capsys.readouterr().out
    assert "atmos (default)" in out and "surround:" in out


def test_build_command(tmp_path, capsys):
    assert main(["build", "--out", str(tmp_path), "--preset", "surround", "--debug"]) == 0
    assert "Chrome extension" in capsys.readouterr().out
    assert '"debug": true' in (tmp_path / "safari-webextension" / "page.js").read_text()


def test_xcode_dry_run_command(tmp_path, capsys):
    assert (
        main(["xcode", "--out", str(tmp_path / "d"), "--project", str(tmp_path / "x"), "--dry-run"])
        == 0
    )
    assert "safari-web-extension-converter" in capsys.readouterr().out


def test_check_refuses_bad_url(capsys):
    assert main(["check", "--url", "file:///etc/passwd"]) == 2
    assert "Refusing" in capsys.readouterr().err


def test_check_without_url_when_discovery_fails(monkeypatch, capsys):
    monkeypatch.setattr(playercore, "discover_url", lambda: None)
    assert main(["check"]) == 2


def test_check_reports_missing_and_state(tmp_path, capsys):
    core = tmp_path / "cadmium-playercore-6.3.js"
    core.write_text('"heaac-2-dash" profiles')
    state = tmp_path / "state.json"
    assert main(["check", "--file", str(core), "--state", str(state), "--update-state"]) == 1
    out = capsys.readouterr().out
    assert "MISSING" in out and "changed since last check: yes" in out
    assert json.loads(state.read_text())["ok"] is False


def test_check_downloads_with_the_validated_url(monkeypatch, capsys):
    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b'"heaac-2-dash" "heaac-5.1-dash" "ddplus-5.1-dash" "ddplus-atmos-dash" profiles'

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return Resp()

    monkeypatch.setattr(playercore.urllib.request, "urlopen", fake_urlopen)
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

    monkeypatch.setattr(playercore.urllib.request, "urlopen", lambda req, timeout: Big())
    with pytest.raises(ValueError, match="larger"):
        playercore.load(url="https://assets.nflxext.com/huge.js")


@pytest.fixture
def fake_macos(monkeypatch, tmp_path):
    """Pretend to be macOS; record every Apple tool call and fake its output."""
    calls = []

    def fake_run(cmd, check, capture_output=False, text=False):
        calls.append(cmd)
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

    for mod in (package, build):
        monkeypatch.setattr(mod.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(mod.shutil, "which", lambda tool: "/usr/bin/" + tool)
        monkeypatch.setattr(mod.subprocess, "run", fake_run)
    return calls


def test_dmg_command(tmp_path, fake_macos, capsys):
    out = tmp_path / "out" / "Surroundflix.dmg"
    assert main(["dmg", "--work", str(tmp_path / "work"), "--output", str(out)]) == 0
    tools = [c[0] if c[0] != "xcrun" else c[1] for c in fake_macos]
    assert tools == ["safari-web-extension-converter", "xcodebuild", "xcodebuild", "hdiutil"]
    build_cmd = fake_macos[2]
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
