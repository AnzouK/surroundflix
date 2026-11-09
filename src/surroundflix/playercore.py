"""Checks that Netflix's player (Cadmium) still knows the profile names
Surroundflix asks for.

This only catches one kind of change: Netflix dropping the Dolby or AAC
5.1 profile names from its player. A change in the request or response
format, or in the server's answers, goes unnoticed here.
"""

from __future__ import annotations

import hashlib
import http.client
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .profiles import EXPECTED_IN_PLAYERCORE

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


# Connections from CI runners are sometimes cut mid-download.
RETRY_DELAYS = (3, 10)


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(validate_url(url), headers={"User-Agent": USER_AGENT})  # noqa: S310
    for delay in (*RETRY_DELAYS, None):
        try:
            with _open(req, timeout) as resp:
                data = resp.read(MAX_DOWNLOAD + 1)
            break
        except urllib.error.HTTPError:
            raise
        except (OSError, http.client.HTTPException):
            if delay is None:
                raise
            time.sleep(delay)
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


def analyze(source: str, url: str | None = None) -> Report:
    data = source.encode("utf-8")
    return Report(
        url=url,
        version=version_from_url(url),
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        found={needle: needle in source for needle in EXPECTED_IN_PLAYERCORE},
    )


def load(url: str | None = None, file: Path | None = None) -> Report:
    if file is not None:
        return analyze(Path(file).read_text("utf-8", errors="replace"), url=url or Path(file).name)
    if url is None:
        raise ValueError("Give a playercore URL or a local file")
    return analyze(_get(url), url=url)
