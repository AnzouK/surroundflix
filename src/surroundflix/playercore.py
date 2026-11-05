"""Watches Netflix's Cadmium playercore for changes that could break us.

Surroundflix doesn't patch the playercore, but it relies on two facts
about it: the player still knows the Dolby and AAC 5.1 profile names, and its
manifest request still carries a "profiles" list. This module downloads
the current playercore and checks both, so a scheduled GitHub Action can
open an issue the day Netflix ships something that matters.
"""

from __future__ import annotations

import hashlib
import json
import re
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


# Only Netflix's own HTTPS hosts are fetched. Without this, a URL given to
# `check --url` (or the PLAYERCORE_URL variable in CI) could be file:///...
# and read a local file, or point the job at any server.
ALLOWED_HOSTS = ("netflix.com", "nflxext.com")
MAX_DOWNLOAD = 20 * 1024 * 1024  # the playercore is a few MB


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(
        host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS
    ):
        raise ValueError(
            f"Refusing to fetch {url!r}: only https:// URLs on netflix.com or nflxext.com"
        )
    return url


def _get(url: str, timeout: int = 30) -> str:
    # validate_url() allows only https on Netflix hosts, so file:// and
    # other schemes never reach urlopen.
    req = urllib.request.Request(validate_url(url), headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310
        data = resp.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError(f"{url} is larger than {MAX_DOWNLOAD} bytes")
    return data.decode("utf-8", errors="replace")


def find_playercore_url(html: str) -> str | None:
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


def compare_with_state(report: Report, state_file: Path) -> dict:
    """Compare against the last known report and return what changed."""
    previous = None
    if state_file.exists():
        previous = json.loads(state_file.read_text("utf-8"))
    changed = previous is None or previous.get("sha256") != report.sha256
    return {
        "changed": changed,
        "previous_version": previous.get("version") if previous else None,
        "current_version": report.version,
        "ok": report.ok,
        "missing": report.missing,
    }


def save_state(report: Report, state_file: Path) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(report.to_dict(), indent=2) + "\n", "utf-8")
