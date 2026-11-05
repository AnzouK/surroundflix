"""Builds Surroundflix.app with Xcode and wraps it in a .dmg (macOS only).

Steps:
  1. Apple's converter turns the WebExtension into an Xcode project.
  2. xcodebuild compiles the app, ad-hoc signed (no Apple Developer account).
  3. hdiutil puts the app, an Applications shortcut, the userscript and a
     short install note into a compressed disk image.
"""

from __future__ import annotations

import json
import platform
import shutil

# Runs Apple's tools (xcrun, xcodebuild, hdiutil) with fixed arguments, never a shell.
import subprocess  # nosec B404
from pathlib import Path

from . import __version__
from .build import build, make_xcode_project

INSTALL_NOTE = """Surroundflix {version}

Option A: the app
  1. Drag Surroundflix into Applications and open it.
     If macOS blocks it: System Settings > Privacy & Security > Open Anyway.
  2. Safari > Settings > Advanced: tick "Show features for web developers".
  3. Safari > Settings > Developer: tick "Allow unsigned extensions".
     Safari resets this option every time it quits.
  4. Safari > Settings > Extensions: enable Surroundflix, allow it on netflix.com.
  The Surroundflix button in Safari's toolbar switches between 5.1 and Atmos
  and 5.1 only.

Option B: userscript (Safari only, no unsigned-extension setting needed)
  1. Install the free "Userscripts" app from the Mac App Store.
  2. Open surroundflix.user.js with it and allow it on netflix.com.

Full guide: {homepage}
"""


def _require_macos() -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("Building the app and the .dmg needs macOS with Xcode installed.")
    for tool in ("xcrun", "xcodebuild", "hdiutil"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"'{tool}' not found. Install Xcode from the App Store first.")


def _find_project(project_dir: Path) -> Path:
    found = sorted(project_dir.rglob("*.xcodeproj"))
    if not found:
        raise RuntimeError(f"No .xcodeproj found in {project_dir}")
    return found[0]


def _app_scheme(project: Path) -> str:
    out = subprocess.run(  # nosec B603 B607
        ["xcodebuild", "-list", "-json", "-project", str(project)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    schemes = json.loads(out)["project"]["schemes"]
    for s in schemes:
        if "extension" not in s.lower():
            return s
    return schemes[0]


def build_app(work_dir: Path, preset: str, bundle_id: str) -> Path:
    _require_macos()
    result = build(work_dir / "dist", preset=preset)
    project_dir = work_dir / "xcode"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    make_xcode_project(result.webextension, project_dir, bundle_id)

    project = _find_project(project_dir)
    derived = work_dir / "derived"
    subprocess.run(  # nosec B603 B607
        [
            "xcodebuild",
            "-project",
            str(project),
            "-scheme",
            _app_scheme(project),
            "-configuration",
            "Release",
            "-derivedDataPath",
            str(derived),
            "CODE_SIGN_IDENTITY=-",
            "CODE_SIGN_STYLE=Manual",
            "DEVELOPMENT_TEAM=",
            "MARKETING_VERSION=" + __version__,
            "build",
        ],
        check=True,
    )
    apps = sorted((derived / "Build" / "Products" / "Release").glob("*.app"))
    if not apps:
        raise RuntimeError("xcodebuild finished but no .app was produced")
    return apps[0]


def make_dmg(app: Path, userscript: Path, out_file: Path, homepage: str) -> Path:
    _require_macos()
    staging = out_file.parent / "dmg-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    shutil.copytree(app, staging / app.name, symlinks=True)
    (staging / "Applications").symlink_to("/Applications")
    shutil.copy2(userscript, staging / userscript.name)
    (staging / "Install.txt").write_text(
        INSTALL_NOTE.format(version=__version__, homepage=homepage), "utf-8"
    )

    out_file.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # nosec B603 B607
        [
            "hdiutil",
            "create",
            "-volname",
            f"Surroundflix {__version__}",
            "-srcfolder",
            str(staging),
            "-ov",
            "-format",
            "UDZO",
            str(out_file),
        ],
        check=True,
    )
    shutil.rmtree(staging)
    return out_file
