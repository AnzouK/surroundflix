"""Netflix audio profile names and the presets Surroundflix can request.

Netflix's player (Cadmium) sends a list of "profiles" to the manifest
endpoint. Each profile is a codec + layout the client claims it can play.
On the web, Safari only advertises stereo, so the server only returns
stereo tracks. Surroundflix appends the Dolby Digital Plus profiles below.
"""

from __future__ import annotations

# Dolby Digital Plus (E-AC-3) profiles, as named by Netflix.
DDPLUS_20 = "ddplus-2.0-dash"
DDPLUS_51 = "ddplus-5.1-dash"
DDPLUS_51_HQ = "ddplus-5.1hq-dash"  # higher bitrate 5.1
DDPLUS_ATMOS = "ddplus-atmos-dash"  # E-AC-3 JOC; Safari decodes the 5.1 bed

PRESETS: dict[str, list[str]] = {
    # 5.1 only. Use this if the Atmos preset ever breaks playback.
    "surround": [DDPLUS_20, DDPLUS_51, DDPLUS_51_HQ],
    # 5.1 plus the Atmos stream when a title has one (default).
    "atmos": [DDPLUS_20, DDPLUS_51, DDPLUS_51_HQ, DDPLUS_ATMOS],
}

DEFAULT_PRESET = "atmos"

# Browsers without a Dolby decoder (Chrome) get Netflix's AAC 5.1 instead,
# on titles that still offer it.
HEAAC_51 = "heaac-5.1-dash"
NO_DOLBY_PROFILES = [HEAAC_51]

# Strings the static playercore check expects to find. If Netflix renames
# or drops these, the injected profiles would be ignored.
EXPECTED_IN_PLAYERCORE = [DDPLUS_51, DDPLUS_ATMOS, "heaac-2-dash", "profiles"]


def resolve(preset: str) -> list[str]:
    """Return the profile list for a preset name, raising on unknown names."""
    try:
        return list(PRESETS[preset])
    except KeyError:
        known = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown preset '{preset}'. Choose one of: {known}") from None
