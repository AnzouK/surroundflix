"""Prepares a release from your Mac: dates the CHANGELOG section with
today's date (your computer's), sets the version, commits on a release
branch, tags it and pushes both. The tag starts .github/workflows/release.yml,
which builds the .dmg, the userscript and the Chrome zip and publishes the
release with that CHANGELOG section as notes.

    python3 scripts/release.py            # the version already in the code
    python3 scripts/release.py 0.2.0      # a new version: [Unreleased] becomes [0.2.0]
    python3 scripts/release.py --dry-run  # show what would change, touch nothing

Run it on an up-to-date main with nothing uncommitted. Afterwards, merge the
release branch's pull request (Rebase and merge) so main gets the dated
CHANGELOG too.
"""

from __future__ import annotations

import argparse
import datetime
import re

# Runs git with fixed arguments, never a shell.
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "AnzouK/surroundflix"
CHANGELOG = ROOT / "CHANGELOG.md"
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "surroundflix" / "__init__.py"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def _section(text: str, name: str) -> re.Match | None:
    """The '## [name]' heading line and the body up to the next '## [' heading."""
    return re.search(
        rf"^## \[{re.escape(name)}\][^\n]*\n(?P<body>.*?)(?=^## \[|\Z)", text, re.M | re.S
    )


def release_changelog(text: str, version: str, day: datetime.date) -> str:
    """Returns the CHANGELOG with the release section dated. If the version
    has no section yet, the [Unreleased] entries become it."""
    if not VERSION.match(version):
        raise ValueError(f"'{version}' isn't a version like 1.2.3")
    unreleased = _section(text, "Unreleased")
    if unreleased is None:
        raise ValueError("CHANGELOG.md has no '## [Unreleased]' section")
    pending = unreleased.group("body").strip()
    heading = f"## [{version}] - {day.isoformat()}"
    current = _section(text, version)
    if current is not None:
        line = current.group(0).split("\n", 1)[0]
        if line.strip() != f"## [{version}]":
            raise ValueError(f"{version} is already dated in CHANGELOG.md: {line}")
        if pending:
            raise ValueError(
                f"[Unreleased] has entries: move them into [{version}], or release "
                "them as a new version (python3 scripts/release.py X.Y.Z)"
            )
        return text.replace(line, heading, 1)
    if not pending:
        raise ValueError(f"no [{version}] section and nothing under [Unreleased] to release")
    start, end = unreleased.span("body")
    return text[:start] + f"\n{heading}\n\n{pending}\n\n" + text[end:]


def set_version(pyproject: str, init: str, version: str) -> tuple[str, str]:
    pyproject = re.sub(
        r'^version = "[^"]+"', f'version = "{version}"', pyproject, count=1, flags=re.M
    )
    init = re.sub(
        r'^__version__ = "[^"]+"', f'__version__ = "{version}"', init, count=1, flags=re.M
    )
    return pyproject, init


def git(*args: str, capture: bool = True) -> str:
    result = subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=ROOT, check=True, capture_output=capture, text=True
    )
    return (result.stdout or "").strip()


def check_repo(tag: str) -> None:
    if git("status", "--porcelain"):
        raise RuntimeError("uncommitted changes: commit or stash them first")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise RuntimeError("run this on main: git checkout main && git pull")
    git("fetch", "--quiet", "--tags", "origin")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        raise RuntimeError("main isn't up to date with GitHub: git pull")
    if git("tag", "--list", tag):
        raise RuntimeError(f"tag {tag} already exists")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", nargs="?", help="default: the version in the code")
    parser.add_argument("--dry-run", action="store_true", help="show the changes only")
    args = parser.parse_args(argv)

    init_text = INIT.read_text()
    current = re.search(r'^__version__ = "([^"]+)"', init_text, re.M).group(1)
    version = args.version or current
    tag, branch = f"v{version}", f"release/v{version}"
    today = datetime.date.today()  # your computer's date
    try:
        changelog = release_changelog(CHANGELOG.read_text(), version, today)
        pyproject, init_text = set_version(PYPROJECT.read_text(), init_text, version)
        if not args.dry_run:
            check_repo(tag)
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as err:
        print(f"surroundflix release: {err}", file=sys.stderr)
        return 1

    section = _section(changelog, version).group(0)
    print(f"Release {tag}, dated {today.isoformat()}:\n\n{section.strip()}\n")
    if args.dry_run:
        print("Dry run: nothing changed.")
        return 0

    git("checkout", "-b", branch)
    CHANGELOG.write_text(changelog, "utf-8")
    PYPROJECT.write_text(pyproject, "utf-8")
    INIT.write_text(init_text, "utf-8")
    git("add", str(CHANGELOG), str(PYPROJECT), str(INIT))
    git("commit", "--quiet", "-m", f"chore(release): {tag}")
    git("tag", "-a", tag, "-m", f"Surroundflix {version}")
    git("push", "--quiet", "-u", "origin", branch, capture=False)
    git("push", "--quiet", "origin", tag, capture=False)
    print(f"Pushed {branch} and {tag}. The release builds here:")
    print(f"  https://github.com/{REPO}/actions/workflows/release.yml")
    print("Then merge the release branch (Rebase and merge):")
    print(f"  https://github.com/{REPO}/compare/main...{branch}?expand=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
