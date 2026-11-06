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
    codec=None,
    built_codec="auto",
):
    attrs = {}
    if codec is not None:
        attrs["data-surroundflix-codec"] = codec
    if attr is not None:
        attrs["data-surroundflix-preset"] = attr
    if video is not None:
        attrs["data-surroundflix-video"] = video
    code = HARNESS % {
        "extra": extra,
        "attrs": json.dumps(attrs),
        "dolby": "true" if dolby else "false",
        "script": render_page_script(
            preset, check_dolby=check_dolby, video_quality=built_video, video_codec=built_codec
        ),
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


def test_streams_without_a_size_dont_disable_the_mode():
    extra = """
    const m = {result: {video_tracks: [{streams: [{bitrate: 500}, {bitrate: 900, res_h: 1080},
      {bitrate: 300, res_h: 480}]}]}};
    out.kept = JSON.parse(JSON.stringify(m)).result.video_tracks[0].streams.map(s => s.bitrate);
    """
    assert run(extra=extra, video="min720")["kept"] == [900]


def test_no_sizes_at_all_leaves_the_list_alone():
    extra = """
    const m = {result: {video_tracks: [{streams: [{bitrate: 500}, {bitrate: 900}]}]}};
    out.kept = JSON.parse(JSON.stringify(m)).result.video_tracks[0].streams.length;
    """
    assert run(extra=extra, video="min720")["kept"] == 2


def test_best_prefers_resolution_over_bitrate():
    # H.264 1080p at 8 Mb/s must not beat HEVC 2160p at 7 Mb/s.
    extra = """
    const m = {result: {video_tracks: [{streams: [
      {content_profile: "playready-h264hpl40-dash", bitrate: 8000, res_h: 1080},
      {content_profile: "hevc-main10-L51-dash-cenc-prk", bitrate: 7000, res_h: 2160},
      {content_profile: "hevc-main10-L51-dash-cenc-prk", bitrate: 5000, res_h: 2160}]}]}};
    out.kept = JSON.parse(JSON.stringify(m)).result.video_tracks[0].streams.map(s => s.bitrate);
    """
    assert run(extra=extra, video="best")["kept"] == [7000]


MIXED = """
    const manifest = {result: {video_tracks: [{streams: [
      {content_profile: "av1-main-L40-dash-cbcs-prk", bitrate: 1800, res_h: 1080},
      {content_profile: "av1-main-L30-dash-cbcs-prk", bitrate: 700, res_h: 720},
      {content_profile: "playready-h264hpl40-dash", bitrate: 4300, res_h: 1080},
      {content_profile: "hevc-dv5-main10-L51-dash-cenc-prk", bitrate: 10400, res_h: 2160},
      {content_profile: "hevc-main10-L41-dash-cenc-prk", bitrate: 5000, res_h: 1080}]}]}};
    const parsed = JSON.parse(JSON.stringify(manifest));
    out.kept = parsed.result.video_tracks[0].streams.map(s => s.bitrate);
    out.video = window.__surroundflix.lastManifestVideo;
"""


@pytest.mark.parametrize(
    "codec,kept",
    [
        ("auto", [1800, 700, 4300, 10400, 5000]),
        ("h264", [4300]),
        ("av1", [1800, 700]),
        ("hevc", [10400, 5000]),
        ("vp9", [1800, 700, 4300, 10400, 5000]),  # not offered: Netflix's list stays
    ],
)
def test_video_codecs(codec, kept):
    out = run(extra=MIXED, codec=codec)
    assert out["kept"] == kept
    assert out["video"]["codecs"] == ["av1", "h264high", "hevc"]
    assert out["video"]["codecChoice"] == codec


def test_codec_and_quality_combine():
    # HEVC first, then the 4K floor within it.
    out = run(extra=MIXED, codec="hevc", video="min2160")
    assert out["kept"] == [10400]
    assert (out["video"]["codec"], out["video"]["dynamicRange"]) == ("hevc", "dv")


def test_best_stream_codec_is_reported():
    out = run(extra=MIXED, codec="h264")
    assert (out["video"]["codec"], out["video"]["dynamicRange"]) == ("h264high", None)


@pytest.mark.parametrize("value", ["", "x265", "constructor", "__proto__", "HEVC"])
def test_unknown_codec_values_mean_automatic(value):
    assert run(extra=MIXED, codec=value)["kept"] == [1800, 700, 4300, 10400, 5000]


def test_userscript_build_sets_the_default_codec():
    assert run(extra=MIXED, built_codec="h264")["kept"] == [4300]
    assert run(extra=MIXED, built_codec="h264", codec="auto")["kept"] == [
        1800,
        700,
        4300,
        10400,
        5000,
    ]


def test_unknown_built_codec_is_refused():
    with pytest.raises(ValueError):
        render_page_script(video_codec="x265")


REQUEST = """
    const req = {version: 2, url: "licensedManifest", params: {profiles: [
      "heaac-2-dash", "playready-h264mpl40-dash", "playready-h264hpl40-dash",
      "vp9-profile0-L40-dash-cenc", "av1-main-L40-dash-cbcs-prk", "webvtt-lssdh-ios8"]}};
    out.request = JSON.parse(JSON.stringify(req)).params.profiles;
    const groups = {params: {profileGroups: [{name: "audio", profiles: ["heaac-2-dash"]},
      {name: "video", profiles: ["hevc-main10-L41-dash-cenc-prk", "playready-h264hpl40-dash"]}]}};
    out.groups = JSON.parse(JSON.stringify(groups)).params.profileGroups[1].profiles;
"""


def test_request_lists_only_the_chosen_codec():
    out = run(extra=REQUEST, codec="h264", check_dolby=True, dolby=False)
    assert out["request"] == [
        "heaac-2-dash",
        "playready-h264mpl40-dash",
        "playready-h264hpl40-dash",
        "webvtt-lssdh-ios8",
        *NO_DOLBY_PROFILES,
    ]
    assert out["groups"] == ["playready-h264hpl40-dash"]


def test_request_without_the_chosen_codec_is_left_alone():
    # Safari without an AV1 decoder never lists AV1: nothing is removed.
    out = run(extra=REQUEST, codec="hevc")
    assert "av1-main-L40-dash-cbcs-prk" in out["request"]
    assert out["groups"] == ["hevc-main10-L41-dash-cenc-prk"]


def test_automatic_codec_keeps_the_request():
    out = run(extra=REQUEST)
    assert "vp9-profile0-L40-dash-cenc" in out["request"]
    assert "av1-main-L40-dash-cbcs-prk" in out["request"]


def test_h264_profiles_can_be_chosen():
    main = run(extra=REQUEST, codec="h264main")["request"]
    assert "playready-h264mpl40-dash" in main and "playready-h264hpl40-dash" not in main
    high = run(extra=REQUEST, codec="h264high")["request"]
    assert "playready-h264hpl40-dash" in high and "playready-h264mpl40-dash" not in high
    assert "av1-main-L40-dash-cbcs-prk" not in main + high


def test_h264_main_stream_is_named():
    extra = """
    const m = {result: {video_tracks: [{streams: [
      {content_profile: "playready-h264mpl40-dash", bitrate: 5200, res_h: 1080},
      {content_profile: "playready-h264hpl40-dash", bitrate: 4300, res_h: 1080}]}]}};
    out.kept = JSON.parse(JSON.stringify(m)).result.video_tracks[0].streams.map(s => s.bitrate);
    out.video = window.__surroundflix.lastManifestVideo;
    """
    out = run(extra=extra, codec="h264main")
    assert out["kept"] == [5200]
    assert out["video"]["codec"] == "h264main"
    assert run(extra=extra, codec="h264")["kept"] == [5200, 4300]


def test_h264_main_is_added_when_the_browser_lists_only_high():
    extra = """
    const req = {params: {profiles: ["heaac-2-dash", "playready-h264hpl30-dash",
      "playready-h264hpl40-dash", "av1-main-L40-dash-cbcs-prk"]}};
    out.request = JSON.parse(JSON.stringify(req)).params.profiles;
    out.requestedVideo = window.__surroundflix.requestedVideo;
    """
    out = run(extra=extra, codec="h264main")
    assert out["requestedVideo"] == [
        "playready-h264mpl30-dash",
        "playready-h264mpl40-dash",
        "h264mpl30-dash-playready-prk-qc",
        "h264mpl31-dash-playready-prk-qc",
        "h264mpl40-dash-playready-prk-qc",
    ]
    assert "playready-h264hpl40-dash" not in out["request"]
    assert "av1-main-L40-dash-cbcs-prk" not in out["request"]


def test_netflix_request_object_is_left_intact():
    # Cadmium may reuse its lists for the next title: a choice changed in the
    # popup between two requests must apply to the second one.
    extra = """
    const req = {params: {profiles: ["heaac-2-dash", "playready-h264hpl40-dash",
      "hevc-main10-L41-dash-cenc-prk", "av1-main-L40-dash-cbcs-prk"]}};
    ATTRS["data-surroundflix-codec"] = "h264";
    out.first = JSON.parse(JSON.stringify(req)).params.profiles;
    ATTRS["data-surroundflix-codec"] = "auto";
    ATTRS["data-surroundflix-preset"] = "surround";
    out.second = JSON.parse(JSON.stringify(req)).params.profiles;
    out.original = req.params.profiles;
    """
    out = run(extra=extra)
    assert "hevc-main10-L41-dash-cenc-prk" not in out["first"]
    assert "ddplus-atmos-dash" in out["first"]
    assert "hevc-main10-L41-dash-cenc-prk" in out["second"]
    assert "ddplus-atmos-dash" not in out["second"] and "ddplus-5.1-dash" in out["second"]
    assert out["original"] == [
        "heaac-2-dash",
        "playready-h264hpl40-dash",
        "hevc-main10-L41-dash-cenc-prk",
        "av1-main-L40-dash-cbcs-prk",
    ]
