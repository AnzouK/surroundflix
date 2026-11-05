import json
import re
import shutil
import subprocess

import pytest

from surroundflix.build import load_i18n, shared_js

I18N = load_i18n()
EN = I18N["strings"]["en"]


@pytest.mark.parametrize("lang", sorted(I18N["strings"]))
def test_every_language_is_complete(lang):
    table = I18N["strings"][lang]
    assert set(table) == set(EN), f"{lang} keys differ from English"
    for key, text in table.items():
        assert text.strip(), f"{lang}.{key} is empty"
        assert re.findall(r"\{\w+\}", text) == re.findall(r"\{\w+\}", EN[key]), (
            f"{lang}.{key} placeholders"
        )


def test_language_names_match_tables():
    assert set(I18N["languages"]) == set(I18N["strings"])


def test_menu_has_one_portuguese_entry():
    assert list(I18N["menu"]) == ["en", "fr", "pt"]
    for code in I18N["menu"]:
        assert code == "pt" or code in I18N["strings"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize(
    "choice,prefs,expected",
    [
        ("pt", ["pt-AO"], "pt-AO"),
        ("pt", ["en-US", "pt-BR"], "pt-BR"),
        ("pt", ["fr-FR"], "pt-PT"),
        ("pt", ["pt"], "pt-PT"),
        ("auto", ["pt-AO", "fr"], "pt-AO"),
        ("fr", ["pt-BR"], "fr"),
        ("en", ["pt-BR"], "en"),
    ],
)
def test_resolve_lang(choice, prefs, expected):
    code = shared_js() + f"\nconsole.log(resolveLang({json.dumps(choice)}, {json.dumps(prefs)}));"
    out = subprocess.run(
        ["node", "-e", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == expected


def test_no_long_dashes():
    raw = json.dumps(I18N, ensure_ascii=False)
    assert chr(0x2014) not in raw and chr(0x2013) not in raw


def test_angolan_portuguese_keeps_its_spelling():
    ao = I18N["strings"]["pt-AO"]
    assert "actualizações" in ao["updates_check"]
    assert "activado" in ao["status_on"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize(
    "prefs,expected",
    [
        (["pt-AO"], "pt-AO"),
        (["pt_BR"], "pt-BR"),
        (["pt"], "pt-PT"),
        (["pt-MZ", "en"], "pt-PT"),
        (["fr-CA"], "fr"),
        (["de-DE", "fr-FR"], "fr"),
        (["de"], "en"),
        ([], "en"),
    ],
)
def test_pick_lang(prefs, expected):
    code = shared_js() + f"\nconsole.log(pickLang({json.dumps(prefs)}));"
    out = subprocess.run(
        ["node", "-e", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == expected


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize(
    "received,expected",
    [
        (["heaac-2-dash", "ddplus-5.1-dash", "ddplus-atmos-dash"], "Dolby Atmos"),
        (["ddplus-5.1-dash", "ddplus-5.1hq-dash"], "Dolby Digital Plus 5.1 (HQ)"),
        (["heaac-2-dash", "heaac-5.1-dash"], "AAC 5.1"),
        (["heaac-2-dash", "ddplus-2.0-dash"], None),
        ([], None),
    ],
)
def test_best_audio(received, expected):
    code = shared_js() + f"\nconsole.log(JSON.stringify(bestAudio({json.dumps(received)})));"
    out = subprocess.run(
        ["node", "-e", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert json.loads(out) == expected


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize(
    "video,lang,expected",
    [
        ({"height": 1080, "bitrate": 5800}, "en", "1080p \u00b7 5.8 Mb/s"),
        ({"height": 2160, "bitrate": 15250}, "fr", "2160p \u00b7 15,3 Mb/s"),
        ({"bitrate": 3000}, "en", "3 Mb/s"),
        ({"height": 1080, "bitrate": "5800"}, "en", ""),
        (None, "en", ""),
    ],
)
def test_format_video(video, lang, expected):
    code = (
        shared_js()
        + f"\nconsole.log(JSON.stringify(formatVideo({json.dumps(video)}, {json.dumps(lang)})));"
    )
    out = subprocess.run(
        ["node", "-e", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert json.loads(out) == expected
