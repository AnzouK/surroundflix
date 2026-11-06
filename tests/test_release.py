"""scripts/release.py: dating the CHANGELOG and setting the version."""

import datetime
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import release  # noqa: E402

DAY = datetime.date(2026, 11, 6)
HEAD = "# Changelog\n\nIntro.\n\n"


def test_existing_section_gets_the_date():
    text = HEAD + "## [Unreleased]\n\n## [0.1.0]\n\nFirst version.\n"
    out = release.release_changelog(text, "0.1.0", DAY)
    assert out == HEAD + "## [Unreleased]\n\n## [0.1.0] - 2026-11-06\n\nFirst version.\n"


def test_unreleased_entries_become_the_new_version():
    text = (
        HEAD + "## [Unreleased]\n\n### Added\n\n- Codec menu.\n\n## [0.1.0] - 2026-11-06\n\nOld.\n"
    )
    out = release.release_changelog(text, "0.2.0", DAY)
    assert out == (
        HEAD + "## [Unreleased]\n\n## [0.2.0] - 2026-11-06\n\n### Added\n\n- Codec menu.\n\n"
        "## [0.1.0] - 2026-11-06\n\nOld.\n"
    )


@pytest.mark.parametrize(
    "text,version,message",
    [
        (HEAD + "## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\nX.\n", "0.1.0", "already dated"),
        (HEAD + "## [Unreleased]\n\n- New.\n\n## [0.1.0]\n\nX.\n", "0.1.0", "has entries"),
        (HEAD + "## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\nX.\n", "0.2.0", "nothing under"),
        (HEAD + "## [0.1.0]\n\nX.\n", "0.1.0", "no '## [Unreleased]'"),
        (HEAD + "## [Unreleased]\n\n- New.\n", "1.0", "isn't a version"),
    ],
)
def test_mistakes_are_refused(text, version, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        release.release_changelog(text, version, DAY)


def test_version_is_set_in_both_files():
    pyproject, init = release.set_version(
        '[project]\nname = "surroundflix"\nversion = "0.1.0"\n',
        '"""Surroundflix."""\n\n__version__ = "0.1.0"\n',
        "0.2.0",
    )
    assert 'version = "0.2.0"' in pyproject and '__version__ = "0.2.0"' in init


def released_changelog():
    """The repository's CHANGELOG with the current version dated: as it is
    once released, or as release.py would date it before the release."""
    import surroundflix

    text = (ROOT / "CHANGELOG.md").read_text()
    version = surroundflix.__version__
    if re.search(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", text, re.M):
        return text
    return release.release_changelog(text, version, DAY)


def test_the_real_changelog_can_be_released():
    import surroundflix

    text = released_changelog()
    assert re.search(
        rf"^## \[{re.escape(surroundflix.__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", text, re.M
    )


def test_release_notes_are_the_section_plus_the_install_guide(tmp_path):
    """Runs the release workflow's own awk on a released CHANGELOG."""
    import shutil
    import subprocess

    import surroundflix

    if shutil.which("awk") is None:
        pytest.skip("awk is not installed")
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    awk = re.search(r"awk -v v=\"\$VERSION\" '(.*?)' CHANGELOG.md", workflow, re.S).group(1)
    version = surroundflix.__version__
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(released_changelog())
    notes = subprocess.run(
        ["awk", "-v", f"v={version}", awk, str(changelog)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert notes.strip() and "## [" not in notes
    assert "release-install.md" in workflow


def test_install_guide_names_every_release_file():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    guide = (ROOT / ".github" / "release-install.md").read_text()
    for name in ("Surroundflix.dmg", "surroundflix.user.js", "surroundflix-chrome.zip"):
        assert name in workflow and name in guide, name
