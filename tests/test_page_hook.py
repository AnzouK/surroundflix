"""Runs the generated page script under Node with a fake `window` and
checks the JSON.stringify hook behaves as intended."""

import json
import shutil
import subprocess

import pytest

from surroundflix.build import render_page_script
from surroundflix.profiles import NO_DOLBY_PROFILES, PRESETS

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node is not installed")

HARNESS = r"""
globalThis.window = globalThis;
const ATTR = %(attr)s;
globalThis.document = { documentElement: { getAttribute: () => ATTR } };
globalThis.MediaSource = { isTypeSupported: (t) => %(dolby)s && t.includes("ec-3") };
%(script)s
const out = {};
const flat = {version: 2, url: "licensedManifest",
  params: {profiles: ["heaac-2-dash", "playready-h264mpl40-dash"]}};
out.flat = JSON.parse(JSON.stringify(flat)).params.profiles;

const grouped = {version: 2, params: {profileGroups: [
  {name: "default", profiles: ["heaac-2-dash", "hevc-main10-L41-dash-cenc"]}]}};
out.grouped = JSON.parse(JSON.stringify(grouped)).params.profileGroups[0].profiles;

const videoOnly = {params: {profiles: ["playready-h264mpl40-dash"]}};
out.videoOnly = JSON.parse(JSON.stringify(videoOnly)).params.profiles;

out.unrelated = JSON.stringify({name: "x", list: [1, 2]});
out.space = JSON.stringify({a: 1}, null, 2);

JSON.parse(JSON.stringify({result: {audio_tracks: [
  {streams: [{content_profile: "ddplus-5.1-dash"}, {content_profile: "heaac-2-dash"}]}]}}));
out.state = window.__surroundflix;
out.native = JSON.stringify.toString().includes("native code");
console.log(JSON.stringify(out));
"""


def run(preset="atmos", attr=None, dolby=True, check_dolby=False):
    code = HARNESS % {
        "attr": json.dumps(attr),
        "dolby": "true" if dolby else "false",
        "script": render_page_script(preset, check_dolby=check_dolby),
    }
    proc = subprocess.run([node, "-e", code], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_flat_profiles_get_dolby_added():
    out = run()
    for p in PRESETS["atmos"]:
        assert p in out["flat"]
    assert out["flat"][:2] == ["heaac-2-dash", "playready-h264mpl40-dash"]


def test_profile_groups_shape_is_patched():
    assert "ddplus-atmos-dash" in run()["grouped"]


def test_lists_without_audio_profiles_are_left_alone():
    assert run()["videoOnly"] == ["playready-h264mpl40-dash"]


def test_unrelated_calls_are_untouched():
    out = run()
    assert out["unrelated"] == '{"name":"x","list":[1,2]}'
    assert out["space"] == '{\n  "a": 1\n}'


def test_state_and_response_inspection():
    out = run()
    assert out["state"]["patchedRequests"] == 2
    assert out["state"]["lastManifestAudio"] == ["ddplus-5.1-dash", "heaac-2-dash"]
    assert out["native"] is True


def test_default_surround_preset_has_no_atmos():
    out = run("surround")
    assert "ddplus-5.1hq-dash" in out["flat"]
    assert "ddplus-atmos-dash" not in out["flat"]


def test_popup_choice_overrides_default():
    out = run("atmos", attr="surround")
    assert "ddplus-atmos-dash" not in out["flat"]
    assert out["state"]["preset"] == "surround"


def test_unknown_popup_value_falls_back_to_default():
    assert "ddplus-atmos-dash" in run("atmos", attr="dts")["flat"]


def test_safari_build_ignores_dolby_detection():
    # Safari builds never switch to AAC, even if detection were wrong.
    assert "ddplus-5.1-dash" in run(dolby=False, check_dolby=False)["flat"]


def test_chrome_without_dolby_asks_for_aac():
    out = run(dolby=False, check_dolby=True)
    assert out["flat"] == ["heaac-2-dash", "playready-h264mpl40-dash", *NO_DOLBY_PROFILES]
    assert out["state"]["dolbySupported"] is False


def test_chrome_with_dolby_keeps_dolby():
    assert "ddplus-atmos-dash" in run(dolby=True, check_dolby=True)["flat"]
