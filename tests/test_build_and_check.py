import json

import pytest

from surroundflix import build, playercore
from surroundflix.cli import main
from surroundflix.profiles import resolve


def test_unknown_preset_raises():
    with pytest.raises(ValueError):
        resolve("dts")


def test_build_outputs(tmp_path):
    result = build.build(tmp_path)
    us = result.userscript.read_text()
    assert us.startswith("// ==UserScript==")
    assert "@run-at       document-start" in us
    assert "@inject-into  page" in us
    assert "__SURROUNDFLIX_CONFIG__" not in us
    assert (
        "@updateURL    https://github.com/AnzouK/surroundflix/releases/latest/download/surroundflix.user.js"
        in us
    )
    assert "@downloadURL" in us

    for ext in (result.webextension, result.chrome):
        manifest = json.loads((ext / "manifest.json").read_text())
        assert manifest["manifest_version"] == 3
        assert manifest["permissions"] == ["storage"]
        assert manifest["action"]["default_popup"] == "popup.html"
        for f in ("content.js", "page.js", "popup.html", "popup.js", "popup.css"):
            assert (ext / f).exists()
        for path in manifest["icons"].values():
            assert (ext / path).stat().st_size > 0
        for f in ext.glob("*.js"):
            assert "__SURROUNDFLIX_" not in f.read_text(), f

    safari = json.loads((result.webextension / "manifest.json").read_text())
    assert "world" not in json.dumps(safari["content_scripts"])
    assert "INJECT = true" in (result.webextension / "content.js").read_text()
    chrome = json.loads((result.chrome / "manifest.json").read_text())
    assert any(cs.get("world") == "MAIN" for cs in chrome["content_scripts"])
    assert "INJECT = false" in (result.chrome / "content.js").read_text()
    assert '"checkDolby": true' in (result.chrome / "page.js").read_text()

    for f in ("Main.html", "Style.css", "Script.js", "Icon.png"):
        assert (result.app / f).exists()


def test_dmg_refuses_off_macos(monkeypatch, tmp_path):
    from surroundflix import package

    monkeypatch.setattr(package.platform, "system", lambda: "Linux")
    with pytest.raises(RuntimeError, match="macOS"):
        package.build_app(tmp_path, "atmos", "io.example.sf")


def test_xcode_dry_run_command(tmp_path):
    cmd = build.make_xcode_project(tmp_path / "ext", tmp_path / "xc", "io.example.sf", dry_run=True)
    assert cmd[:2] == ["xcrun", "safari-web-extension-converter"]
    assert "--macos-only" in cmd


SAMPLE_HTML = '<script src="https://assets.nflxext.com/player/html/ffe/cadmium-playercore-6.0051.123.911.js"></script>'
GOOD_CORE = (
    'x="heaac-2-dash";w="heaac-5.1-dash";y="ddplus-5.1-dash";z="ddplus-atmos-dash";r={profiles:[]}'
)


def test_find_url_and_version():
    url = playercore.find_playercore_url(SAMPLE_HTML)
    assert url.endswith("cadmium-playercore-6.0051.123.911.js")
    assert playercore.version_from_url(url) == "6.0051.123.911"


def test_analyze_ok_and_missing():
    assert playercore.analyze(GOOD_CORE).ok
    bad = playercore.analyze(GOOD_CORE.replace("ddplus-atmos-dash", "eac3-joc"))
    assert not bad.ok and bad.missing == ["ddplus-atmos-dash"]


def test_state_roundtrip(tmp_path):
    state = tmp_path / "state.json"
    rep = playercore.analyze(GOOD_CORE, url="cadmium-playercore-6.1.js")
    assert playercore.compare_with_state(rep, state)["changed"] is True
    playercore.save_state(rep, state)
    assert playercore.compare_with_state(rep, state)["changed"] is False


def test_cli_check_with_file(tmp_path, capsys):
    core = tmp_path / "cadmium-playercore-6.2.js"
    core.write_text(GOOD_CORE)
    assert main(["check", "--file", str(core), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
