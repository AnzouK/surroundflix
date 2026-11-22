"""Checks that Netflix's player (Cadmium) still knows the profile names
Surroundflix asks for.

This only catches one kind of change: Netflix dropping the Dolby or AAC
5.1 profile names from its player. A change in the request or response
format, or in the server's answers, goes unnoticed here.
"""

from __future__ import annotations

import difflib
import hashlib
import http.client
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .profiles import EXPECTED_IN_PLAYERCORE, H264_MAIN, NO_DOLBY_PROFILES, PRESETS

PLAYERCORE_URL_RE = re.compile(
    r"https://assets\.nflxext\.com/[^\"'\s<>]*?cadmium-playercore[^\"'\s<>]*?\.js"
)
VERSION_RE = re.compile(r"cadmium-playercore-([0-9][0-9.]*[0-9])")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Safari/605.1.15"
)


@dataclass
class Report:
    url: str | None
    version: str | None
    sha256: str
    size: int
    found: dict[str, bool] = field(default_factory=dict)
    # For each missing name: the likely new name in this playercore, or None.
    suggestions: dict[str, str | None] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(self.found.values())

    @property
    def missing(self) -> list[str]:
        return [k for k, v in self.found.items() if not v]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        d["missing"] = self.missing
        return d


# Only Netflix's own HTTPS hosts are fetched, redirects included. Without
# this, a URL given to `check --url` (or the PLAYERCORE_URL variable in CI)
# could be file:///... and read a local file, or point the job elsewhere.
ALLOWED_HOSTS = ("netflix.com", "nflxext.com")
MAX_DOWNLOAD = 20 * 1024 * 1024  # the playercore is a few MB


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError:
        port = -1
    if parsed.username or parsed.password or port not in (None, 443):
        raise ValueError(f"Refusing to fetch {url!r}: no credentials or custom port")
    if parsed.scheme != "https" or not any(
        host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS
    ):
        raise ValueError(
            f"Refusing to fetch {url!r}: only https:// URLs on netflix.com or nflxext.com"
        )
    return url


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    """Applies validate_url() to every redirect, not just the first URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_CheckedRedirects)


def _open(req: urllib.request.Request, timeout: int):
    return _OPENER.open(req, timeout=timeout)


# Connections from CI runners are often cut mid-download, at about the same
# point on every try. A try that brought new bytes is followed at once by a
# request for the rest (Range); one that brought nothing waits first.
RETRY_DELAYS = (3, 10)
MAX_TRIES = 100


def _get(url: str, timeout: int = 30) -> str:
    url = validate_url(url)
    data, version, stalled = b"", None, 0
    for _ in range(MAX_TRIES):
        headers = {"User-Agent": USER_AGENT}
        if data:
            headers["Range"] = f"bytes={len(data)}-"
            if version:
                # A file that changed in between comes back whole.
                headers["If-Range"] = version
        req = urllib.request.Request(url, headers=headers)  # noqa: S310
        try:
            with _open(req, timeout) as resp:
                if data and getattr(resp, "status", 200) != 206:
                    data = b""  # the server sent the whole file again
                if not data:
                    sent = getattr(resp, "headers", None) or {}
                    version = sent.get("ETag") or sent.get("Last-Modified")
                data += resp.read(MAX_DOWNLOAD + 1 - len(data))
            break
        except urllib.error.HTTPError as err:
            if data and err.code == 416:
                data, version = b"", None  # the range no longer exists: start over
                continue
            raise
        except (OSError, http.client.HTTPException) as err:
            partial = getattr(err, "partial", b"")
            if partial and len(data) + len(partial) <= MAX_DOWNLOAD:
                data += partial
                stalled = 0
                continue
            if stalled == len(RETRY_DELAYS):
                raise
            time.sleep(RETRY_DELAYS[stalled])
            stalled += 1
    else:
        raise OSError(f"{url} kept being cut off")
    if len(data) > MAX_DOWNLOAD:
        raise ValueError(f"{url} is larger than {MAX_DOWNLOAD} bytes")
    return data.decode("utf-8", errors="replace")


def find_playercore_url(html: str) -> str | None:
    # Netflix's page config escapes slashes in URLs (https:\x2F\x2Fassets...).
    html = re.sub(r"\\(?:x2f|u002f|/)", "/", html, flags=re.I)
    m = PLAYERCORE_URL_RE.search(html)
    return m.group(0) if m else None


def discover_url(page: str = "https://www.netflix.com/") -> str | None:
    """Best effort: Netflix may only expose the URL to signed-in pages."""
    return find_playercore_url(_get(page))


def version_from_url(url: str | None) -> str | None:
    if not url:
        return None
    m = VERSION_RE.search(url)
    return m.group(1) if m else None


# A profile name as a quoted or backticked string literal, e.g. heaac-2-dash,
# h264mpl30-dash-playready-prk-qc or hevc-main10-L41-dash-cenc.
PROFILE_NAME = r"[A-Za-z][A-Za-z0-9.-]{4,62}[A-Za-z0-9]"
_LITERAL_RE = re.compile(r"([\"'`])(" + PROFILE_NAME + r")\1")
_PROFILE_NAME_RE = re.compile(PROFILE_NAME)


def is_profile_name(name: object) -> bool:
    return (
        isinstance(name, str) and _PROFILE_NAME_RE.fullmatch(name) is not None and "-dash" in name
    )


def profile_names(source: str) -> set[str]:
    """Every string literal in the playercore that looks like a profile name."""
    return {m.group(2) for m in _LITERAL_RE.finditer(source) if "-dash" in m.group(2)}


# Names Surroundflix already uses are never offered as a replacement.
IN_USE = frozenset(
    [
        *EXPECTED_IN_PLAYERCORE,
        *H264_MAIN,
        *NO_DOLBY_PROFILES,
        *(n for ps in PRESETS.values() for n in ps),
    ]
)
MIN_RATIO = 0.85


def _family(name: str) -> str:
    # The part before "-dash" without its numbers: "ddplus-hq" for
    # ddplus-5.1hq-dash, "hmpl" for h264mpl40-dash-playready-prk-qc.
    return re.sub(r"[0-9.]+", "", name.split("-dash", 1)[0])


def _numbers(name: str) -> list[str]:
    return re.findall(r"[0-9]+", name)


# DRM and variant words: a name with other ones is a different profile.
VARIANT_WORDS = frozenset(
    ["playready", "widevine", "fairplay", "cenc", "cbcs", "clear", "live", "prk", "qc"]
)
MIN_MARGIN = 0.05


def _variants(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", name.lower()) if w in VARIANT_WORDS}


def _without_version(name: str) -> str:
    # ddplus-atmos2-dash and ddplus-atmos-dash-v2 -> ddplus-atmos-dash
    return re.sub(r"(?<=[a-z])[0-9]+(?=-dash|$)|-v[0-9]+$", "", name)


def _could_be_renamed(old: str, new: str) -> bool:
    nums = _numbers(old)
    if not nums and _numbers(_without_version(new)):
        return False
    return (
        _family(new) == _family(old)
        and _variants(new) == _variants(old)
        and _numbers(new)[: len(nums)] == nums
    )


def suggest_replacements(
    missing: list[str], names: set[str], exclude: frozenset[str] = IN_USE
) -> dict[str, str | None]:
    """For each missing name, the likely new name among `names`, or None.

    A candidate must not be a name Surroundflix already uses, must be at
    least 85% similar (difflib ratio), keep the same family (codec, profile
    and layout letters before "-dash") and the same DRM words, and keep the
    old name's numbers in order, only adding new ones after them
    (prk-qc -> prk-qc2, never mpl40 -> mpl41, 5.1 -> 2.0 or
    ddplus-atmos-dash -> ddplus-atmos-2.0-dash). The best candidate must also
    beat the next one by 0.05, otherwise None: a wrong rename is worse than
    none.
    """
    out: dict[str, str | None] = {}
    for old in missing:
        scored = sorted(
            (
                (difflib.SequenceMatcher(None, old, new).ratio(), new)
                for new in names
                if new != old and new not in exclude and _could_be_renamed(old, new)
            ),
            reverse=True,
        )
        ok = bool(scored) and scored[0][0] >= MIN_RATIO
        if ok and len(scored) > 1 and scored[0][0] - scored[1][0] < MIN_MARGIN:
            ok = False
        out[old] = scored[0][1] if ok else None
    return out


def _has_name(source: str, name: str) -> bool:
    # A whole name, so a rename that only adds to the end (prk-qc -> prk-qc2)
    # still counts as missing.
    return re.search(rf"(?<![A-Za-z0-9._-]){re.escape(name)}(?![A-Za-z0-9._-])", source) is not None


def analyze(source: str, url: str | None = None) -> Report:
    data = source.encode("utf-8")
    found = {needle: _has_name(source, needle) for needle in EXPECTED_IN_PLAYERCORE}
    missing = [k for k, v in found.items() if not v]
    return Report(
        url=url,
        version=version_from_url(url),
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        found=found,
        suggestions=suggest_replacements(missing, profile_names(source)) if missing else {},
    )


def load(url: str | None = None, file: Path | None = None) -> Report:
    if file is not None:
        return analyze(Path(file).read_text("utf-8", errors="replace"), url=url or Path(file).name)
    if url is None:
        raise ValueError("Give a playercore URL or a local file")
    return analyze(_get(url), url=url)
