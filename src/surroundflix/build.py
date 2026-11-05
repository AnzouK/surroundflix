"""Builds the two distributables from the JS templates.

dist/
  userscript/surroundflix.user.js    for the free "Userscripts" Safari app
  safari-webextension/               feed this to Apple's converter (Xcode)
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from . import __version__
from .profiles import DEFAULT_PRESET, resolve

CONFIG_PLACEHOLDER = "/*__SURROUNDFLIX_CONFIG__*/ null"
NETFLIX_MATCH = "https://www.netflix.com/*"
# Change this once, here, when the repository is public.
HOMEPAGE = "https://github.com/AnzouK/surroundflix"
ICON_SIZES = (48, 96, 128, 256, 512, 1024)


@dataclass
class BuildResult:
    userscript: Path
    webextension: Path


def _template(name: str) -> str:
    return resources.files("surroundflix").joinpath("templates", name).read_text("utf-8")


def _icon_bytes(size: int) -> bytes:
    return resources.files("surroundflix").joinpath("icons", f"icon-{size}.png").read_bytes()


def render_page_script(preset: str = DEFAULT_PRESET, debug: bool = False) -> str:
    """Return page.js with the chosen profiles baked in."""
    config = {
        "version": __version__,
        "preset": preset,
        "profiles": resolve(preset),
        "debug": debug,
    }
    template = _template("page.js")
    if CONFIG_PLACEHOLDER not in template:
        raise RuntimeError("page.js template is missing the config placeholder")
    return template.replace(CONFIG_PLACEHOLDER, json.dumps(config))


def render_userscript(preset: str = DEFAULT_PRESET, debug: bool = False) -> str:
    header = "\n".join(
        [
            "// ==UserScript==",
            "// @name         Surroundflix",
            f"// @version      {__version__}",
            "// @description  Ask Netflix for 5.1 / Atmos audio in Safari (Spatial Audio friendly)",
            f"// @homepageURL  {HOMEPAGE}",
            f"// @match        {NETFLIX_MATCH}",
            "// @run-at       document-start",
            "// @inject-into  page",
            "// @grant        none",
            "// ==/UserScript==",
            "",
        ]
    )
    return header + "\n" + render_page_script(preset, debug)


def render_manifest() -> dict:
    return {
        "manifest_version": 3,
        "name": "Surroundflix",
        "version": __version__,
        "description": "Ask Netflix for its 5.1 / Atmos audio tracks in Safari.",
        "homepage_url": HOMEPAGE,
        "icons": {str(s): f"images/icon-{s}.png" for s in ICON_SIZES},
        # No "permissions" at all: the extension only runs on netflix.com.
        "content_scripts": [
            {
                "matches": [NETFLIX_MATCH],
                "js": ["content.js"],
                "run_at": "document_start",
                "all_frames": False,
            }
        ],
        "web_accessible_resources": [
            {"resources": ["page.js"], "matches": [NETFLIX_MATCH]}
        ],
    }


def build(out_dir: Path, preset: str = DEFAULT_PRESET, debug: bool = False) -> BuildResult:
    out_dir = Path(out_dir)
    us_dir = out_dir / "userscript"
    ext_dir = out_dir / "safari-webextension"
    for d in (us_dir, ext_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    userscript = us_dir / "surroundflix.user.js"
    userscript.write_text(render_userscript(preset, debug), "utf-8")

    (ext_dir / "page.js").write_text(render_page_script(preset, debug), "utf-8")
    (ext_dir / "content.js").write_text(_template("content.js"), "utf-8")
    (ext_dir / "manifest.json").write_text(json.dumps(render_manifest(), indent=2) + "\n", "utf-8")
    (ext_dir / "images").mkdir()
    for s in ICON_SIZES:
        (ext_dir / "images" / f"icon-{s}.png").write_bytes(_icon_bytes(s))

    return BuildResult(userscript=userscript, webextension=ext_dir)


def converter_command(ext_dir: Path, project_dir: Path, bundle_id: str) -> list[str]:
    """Apple's tool that wraps a WebExtension in a macOS app (needs Xcode)."""
    return [
        "xcrun", "safari-web-extension-converter", str(ext_dir),
        "--project-location", str(project_dir),
        "--app-name", "Surroundflix",
        "--bundle-identifier", bundle_id,
        "--macos-only", "--swift", "--copy-resources",
        "--no-open", "--no-prompt", "--force",
    ]


def make_xcode_project(ext_dir: Path, project_dir: Path, bundle_id: str, dry_run: bool = False) -> list[str]:
    cmd = converter_command(ext_dir, project_dir, bundle_id)
    if dry_run:
        return cmd
    if platform.system() != "Darwin":
        raise RuntimeError("The Xcode step only runs on macOS. Use --dry-run to print the command.")
    if shutil.which("xcrun") is None:
        raise RuntimeError("xcrun not found. Install Xcode from the App Store, then run: xcode-select --install")
    subprocess.run(cmd, check=True)
    return cmd
