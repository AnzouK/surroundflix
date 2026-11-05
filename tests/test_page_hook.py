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
const ATTRS = %(attrs)s;
globalThis.__attrs = {};
globalThis.document = { documentElement: {
  getAttribute: (k) => (k in ATTRS ? ATTRS[k] : null),
  setAttribute: (k, v) => { globalThis.__attrs[k] = v; } } };
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
out.status = JSON.parse(globalThis.__attrs["data-surroundflix-status"]);
(async () => {
  %(extra)s
  console.log(JSON.stringify(out));
})();
"""


def run(
    preset="atmos",
    attr=None,
    dolby=True,
    check_dolby=False,
    extra="",
    video=None,
    built_video="auto",
):
    attrs = {}
    if attr is not None:
        attrs["data-surroundflix-preset"] = attr
    if video is not None:
        attrs["data-surroundflix-video"] = video
    code = HARNESS % {
        "extra": extra,
        "attrs": json.dumps(attrs),
        "dolby": "true" if dolby else "false",
        "script": render_page_script(preset, check_dolby=check_dolby, video_quality=built_video),
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


def test_status_is_mirrored_on_html():
    status = run()["status"]
    assert status["received"] == ["ddplus-5.1-dash", "heaac-2-dash"]
    assert status["patchedRequests"] == 2
    assert "ddplus-atmos-dash" in status["requested"]


def test_nested_camel_case_manifest_is_read():
    extra = """
    JSON.parse(JSON.stringify({payload: {data: {audioTracks: [
      {downloadables: [{contentProfile: "heaac-5.1-dash"}, {contentProfile: "heaac-2-dash"}]}]}}}));
    out.camel = window.__surroundflix.lastManifestAudio;
    """
    assert run(extra=extra)["camel"] == ["heaac-5.1-dash", "heaac-2-dash"]


def test_response_json_is_read():
    extra = """
    const body = {result: {audio_tracks: [{streams: [{content_profile: "ddplus-atmos-dash"}]}]}};
    await new Response(JSON.stringify(body)).json();
    out.viaFetch = window.__surroundflix.lastManifestAudio;
    """
    assert run(extra=extra)["viaFetch"] == ["ddplus-atmos-dash"]


def test_video_profiles_are_ignored():
    extra = """
    JSON.parse(JSON.stringify({result: {audio_tracks: [{profile: "playready-h264mpl40-dash",
      streams: [{content_profile: "ddplus-5.1-dash"}]}]}}));
    out.mixed = window.__surroundflix.lastManifestAudio;
    """
    assert run(extra=extra)["mixed"] == ["ddplus-5.1-dash"]


VIDEO = """
    const manifest = {result: {
      audio_tracks: [{streams: [
        {content_profile: "ddplus-5.1-dash", bitrate: 384},
        {content_profile: "ddplus-5.1-dash", bitrate: 640},
        {content_profile: "ddplus-atmos-dash", bitrate: 448}]}],
      video_tracks: [{streams: [
        {content_profile: "hevc-main10", bitrate: 235, res_h: 270},
        {content_profile: "hevc-main10", bitrate: 5800, res_h: 1080},
        {content_profile: "hevc-main10", bitrate: 3000, res_h: 720},
        {content_profile: "hevc-main10", bitrate: 1050, res_h: 540}]}]}};
    const parsed = JSON.parse(JSON.stringify(manifest));
    out.kept = parsed.result.video_tracks[0].streams.map(s => s.res_h);
    out.audioKept = parsed.result.audio_tracks[0].streams.map(s => s.bitrate);
    out.video = window.__surroundflix.lastManifestVideo;
    out.videoStatus = JSON.parse(globalThis.__attrs["data-surroundflix-status"]).video;
"""


@pytest.mark.parametrize(
    "mode,kept",
    [
        ("auto", [270, 1080, 720, 540]),
        ("min720", [1080, 720]),
        ("min1080", [1080]),
        ("min2160", [1080]),  # no 4K offered: the tallest streams are kept
        ("best", [1080]),
        ("saver720", [270, 720, 540]),
    ],
)
def test_video_modes(mode, kept):
    out = run(extra=VIDEO, video=mode)
    assert out["kept"] == kept
    assert out["video"]["mode"] == mode
    assert (out["video"]["minHeight"], out["video"]["maxHeight"]) == (270, 1080)
    assert out["videoStatus"]["height"] == max(kept)


def test_auto_is_the_default_and_touches_nothing():
    out = run(extra=VIDEO)
    assert out["kept"] == [270, 1080, 720, 540]
    assert out["audioKept"] == [384, 640, 448]


def test_best_also_keeps_the_top_bitrate_of_each_audio_format():
    # 5.1 keeps 640 (not 384); Atmos is another format and stays.
    assert run(extra=VIDEO, video="best")["audioKept"] == [640, 448]


@pytest.mark.parametrize("value", ["", "1", "max", "constructor", "__proto__", "BEST"])
def test_unknown_video_values_mean_automatic(value):
    assert run(extra=VIDEO, video=value)["kept"] == [270, 1080, 720, 540]


def test_userscript_build_sets_the_default_mode():
    assert run(extra=VIDEO, built_video="min1080")["kept"] == [1080]
    # An explicit popup choice wins over the build default.
    assert run(extra=VIDEO, built_video="min1080", video="auto")["kept"] == [270, 1080, 720, 540]


def test_a_floor_above_every_stream_keeps_the_tallest():
    extra = """
    const m = {result: {video_tracks: [{streams: [
      {bitrate: 500, res_h: 480}, {bitrate: 900, res_h: 576}, {bitrate: 700, res_h: 576}]}]}};
    out.kept = JSON.parse(JSON.stringify(m)).result.video_tracks[0].streams.map(s => s.bitrate);
    """
    assert run(extra=extra, video="min1080")["kept"] == [900, 700]


def test_video_without_sizes_or_bitrates_is_left_alone():
    extra = """
    const m = {result: {video_tracks: [{streams: [{bitrate: 500}, {bitrate: 900, res_h: 1080}, {x: 1}]}]}};
    out.kept = JSON.parse(JSON.stringify(m)).result.video_tracks[0].streams.length;
    """
    assert run(extra=extra, video="min720")["kept"] == 3
