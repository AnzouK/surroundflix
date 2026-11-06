"""Release helper, in two steps so the tag lands on main after CI.

    python3 scripts/release.py prepare 1.1.0   # [Unreleased] becomes [1.1.0]
    python3 scripts/release.py prepare         # or the version already in the code
    python3 scripts/release.py tag             # after the release PR is merged

prepare (on an up-to-date main): dates the CHANGELOG section with today's
date (your computer's), sets the version, commits on a release/v... branch
and pushes it. Open its pull request and merge it once CI is green.

tag (on the up-to-date main that contains that merge): checks that the
CHANGELOG section of the code's version is dated, then tags main and
pushes the tag. The tag starts .github/workflows/release.yml, which runs
the CI again, builds the .dmg, the userscript and the Chrome zip, and
publishes the release with that CHANGELOG section as notes.

--dry-run shows what would happen and changes nothing.
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


def dated_section(text: str, version: str) -> str:
    """The released section of `version`; refuses an undated or missing one."""
    section = _section(text, version)
    if section is None:
        raise ValueError(f"CHANGELOG.md has no [{version}] section")
    line = section.group(0).split("\n", 1)[0]
    if not re.fullmatch(rf"## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}", line.strip()):
        raise ValueError(
            f"[{version}] isn't dated yet: run 'prepare' and merge its pull request first"
        )
    return section.group(0)


def code_version() -> str:
    return re.search(r'^__version__ = "([^"]+)"', INIT.read_text(), re.M).group(1)


def prepare(version: str | None, dry_run: bool) -> int:
    version = version or code_version()
    tag, branch = f"v{version}", f"release/v{version}"
    today = datetime.date.today()  # your computer's date
    changelog = release_changelog(CHANGELOG.read_text(), version, today)
    pyproject, init = set_version(PYPROJECT.read_text(), INIT.read_text(), version)
    if not dry_run:
        check_repo(tag)
    print(
        f"Release {tag}, dated {today.isoformat()}:\n\n{_section(changelog, version).group(0).strip()}\n"
    )
    if dry_run:
        print("Dry run: nothing changed.")
        return 0
    git("checkout", "-b", branch)
    CHANGELOG.write_text(changelog, "utf-8")
    PYPROJECT.write_text(pyproject, "utf-8")
    INIT.write_text(init, "utf-8")
    git("add", str(CHANGELOG), str(PYPROJECT), str(INIT))
    git("commit", "--quiet", "-m", f"chore(release): {tag}")
    git("push", "--quiet", "-u", "origin", branch, capture=False)
    print(f"Pushed {branch}. Open its pull request, merge it once CI is green:")
    print(f"  https://github.com/{REPO}/compare/main...{branch}?expand=1")
    print("then, on main: git checkout main && git pull && python3 scripts/release.py tag")
    return 0


def tag_release(dry_run: bool) -> int:
    version = code_version()
    tag = f"v{version}"
    dated_section(CHANGELOG.read_text(), version)
    if not dry_run:
        check_repo(tag)
    print(f"Tag {tag} on the current main commit.")
    if dry_run:
        print("Dry run: nothing changed.")
        return 0
    git("tag", "-a", tag, "-m", f"Surroundflix {version}")
    git("push", "--quiet", "origin", tag, capture=False)
    print("Pushed. The release builds here:")
    print(f"  https://github.com/{REPO}/actions/workflows/release.yml")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    p = sub.add_parser("prepare", help="date the CHANGELOG and push a release branch")
    p.add_argument("version", nargs="?", help="default: the version in the code")
    p.add_argument("--dry-run", action="store_true", help="show the changes only")
    t = sub.add_parser("tag", help="tag main once the release branch is merged")
    t.add_argument("--dry-run", action="store_true", help="show the changes only")
    args = parser.parse_args(argv)
    try:
        if args.step == "prepare":
            return prepare(args.version, args.dry_run)
        return tag_release(args.dry_run)
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as err:
        print(f"surroundflix release: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
