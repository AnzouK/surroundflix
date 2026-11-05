"""Builds the distributables from the templates.

dist/
  userscript/surroundflix.user.js   for the free "Userscripts" Safari app
  safari-webextension/              fed to Apple's converter (Xcode)
  chrome-extension/                 load unpacked in chrome://extensions
  app/                              the app window (Main.html, Style.css, Script.js)
"""

from __future__ import annotations

import json
import platform
import shutil

# Runs Apple's tools (xcrun, xcodebuild, hdiutil) with fixed arguments, never a shell.
import subprocess  # nosec B404
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from . import __version__
from .profiles import (
    DEFAULT_PRESET,
    DEFAULT_VIDEO_MODE,
    NO_DOLBY_PROFILES,
    PRESETS,
    VIDEO_MODES,
    resolve,
)

NETFLIX_MATCH = "https://www.netflix.com/*"
# Change this once, here, if the repository moves.
REPO = "AnzouK/surroundflix"
HOMEPAGE = f"https://github.com/{REPO}"
# Userscript managers check this file for a newer @version.
USERSCRIPT_URL = f"{HOMEPAGE}/releases/latest/download/surroundflix.user.js"
ICON_SIZES = (48, 96, 128, 256, 512, 1024)


@dataclass
class BuildResult:
    userscript: Path
    webextension: Path
    chrome: Path
    app: Path


def _template(name: str) -> str:
    return (
        resources.files("surroundflix").joinpath("templates", *name.split("/")).read_text("utf-8")
    )


def _icon_bytes(size: int) -> bytes:
    return resources.files("surroundflix").joinpath("icons", f"icon-{size}.png").read_bytes()


def _fill(template: str, values: dict[str, object]) -> str:
    """Replace `/*__SURROUNDFLIX_KEY__*/ default` placeholders with JSON values."""
    import re

    for key, value in values.items():
        pattern = re.compile(r"/\*__SURROUNDFLIX_" + key + r"__\*/ [^;\n]+")
        if not pattern.search(template):
            raise RuntimeError(f"template placeholder {key} not found")
        replacement = json.dumps(value, ensure_ascii=False)
        template = pattern.sub(lambda _m, r=replacement: r, template, count=1)
    return template


def load_i18n() -> dict:
    return json.loads(_template("i18n.json"))


def render_page_script(
    preset: str = DEFAULT_PRESET,
    debug: bool = False,
    check_dolby: bool = False,
    video_quality: str = DEFAULT_VIDEO_MODE,
) -> str:
    """Return page.js with the profiles baked in."""
    resolve(preset)
    if video_quality not in VIDEO_MODES:
        raise ValueError(
            f"Unknown video quality '{video_quality}'. Choose one of: {', '.join(VIDEO_MODES)}"
        )
    config = {
        "version": __version__,
        "preset": preset,
        "presets": PRESETS,
        "noDolbyProfiles": NO_DOLBY_PROFILES,
        "checkDolby": check_dolby,
        # Default video mode; the extensions' popup overrides it.
        "videoQuality": video_quality,
        "debug": debug,
    }
    return _fill(_template("page.js"), {"CONFIG": config})


def render_userscript(
    preset: str = DEFAULT_PRESET, debug: bool = False, video_quality: str = DEFAULT_VIDEO_MODE
) -> str:
    header = "\n".join(
        [
            "// ==UserScript==",
            "// @name         Surroundflix",
            f"// @version      {__version__}",
            "// @description  Ask Netflix for 5.1 / Atmos audio in Safari (Spatial Audio friendly)",
            f"// @homepageURL  {HOMEPAGE}",
            f"// @updateURL    {USERSCRIPT_URL}",
            f"// @downloadURL  {USERSCRIPT_URL}",
            f"// @match        {NETFLIX_MATCH}",
            "// @run-at       document-start",
            "// @inject-into  page",
            "// @grant        none",
            "// ==/UserScript==",
            "",
        ]
    )
    return header + "\n" + render_page_script(preset, debug, video_quality=video_quality)


def shared_js() -> str:
    return _fill(_template("shared.js"), {"I18N": load_i18n()})


def render_popup_script(preset: str, check_dolby: bool) -> str:
    popup = _fill(
        _template("popup.js"),
        {
            "DEFAULT_PRESET": preset,
            "CHECK_DOLBY": check_dolby,
            "DEFAULT_VIDEO_QUALITY": DEFAULT_VIDEO_MODE,
        },
    )
    return shared_js() + "\n" + popup


def render_app_script() -> str:
    app = _fill(_template("app/Script.js"), {"VERSION": __version__, "REPO": REPO})
    return shared_js() + "\n" + app


def render_app_html(
    style: str = "Style.css", script: str = "Script.js", icon: str = "Icon.png"
) -> str:
    html = _template("app/Main.html")
    return html.replace("{{STYLE}}", style).replace("{{SCRIPT}}", script).replace("{{ICON}}", icon)


def render_manifest(chrome: bool = False) -> dict:
    manifest: dict = {
        "manifest_version": 3,
        "name": "Surroundflix",
        "version": __version__,
        "description": "Ask Netflix for its 5.1 / Atmos audio tracks.",
        "homepage_url": HOMEPAGE,
        "icons": {str(s): f"images/icon-{s}.png" for s in ICON_SIZES if s <= 512},
        "action": {
            "default_popup": "popup.html",
            "default_icon": {"48": "images/icon-48.png", "96": "images/icon-96.png"},
        },
        # Only "storage", for the popup's audio choice. Runs on netflix.com only.
        "permissions": ["storage"],
    }
    if chrome:
        manifest["content_scripts"] = [
            {"matches": [NETFLIX_MATCH], "js": ["content.js"], "run_at": "document_start"},
            {
                "matches": [NETFLIX_MATCH],
                "js": ["page.js"],
                "run_at": "document_start",
                "world": "MAIN",
            },
        ]
    else:
        manifest["content_scripts"] = [
            {
                "matches": [NETFLIX_MATCH],
                "js": ["content.js"],
                "run_at": "document_start",
                "all_frames": False,
            }
        ]
        manifest["web_accessible_resources"] = [
            {"resources": ["page.js"], "matches": [NETFLIX_MATCH]}
        ]
    return manifest


def _write_extension(ext_dir: Path, preset: str, debug: bool, chrome: bool) -> None:
    ext_dir.mkdir(parents=True)
    (ext_dir / "page.js").write_text(render_page_script(preset, debug, check_dolby=chrome), "utf-8")
    (ext_dir / "content.js").write_text(
        _fill(_template("content.js"), {"INJECT": not chrome}), "utf-8"
    )
    (ext_dir / "popup.html").write_text(_template("popup.html"), "utf-8")
    (ext_dir / "popup.css").write_text(_template("popup.css"), "utf-8")
    (ext_dir / "popup.js").write_text(render_popup_script(preset, check_dolby=chrome), "utf-8")
    (ext_dir / "manifest.json").write_text(
        json.dumps(render_manifest(chrome), indent=2) + "\n", "utf-8"
    )
    (ext_dir / "images").mkdir()
    for s in ICON_SIZES:
        (ext_dir / "images" / f"icon-{s}.png").write_bytes(_icon_bytes(s))


def build(
    out_dir: Path,
    preset: str = DEFAULT_PRESET,
    debug: bool = False,
    video_quality: str = DEFAULT_VIDEO_MODE,
) -> BuildResult:
    out_dir = Path(out_dir)
    dirs = {
        name: out_dir / name
        for name in ("userscript", "safari-webextension", "chrome-extension", "app")
    }
    for d in dirs.values():
        if d.exists():
            shutil.rmtree(d)

    dirs["userscript"].mkdir(parents=True)
    userscript = dirs["userscript"] / "surroundflix.user.js"
    userscript.write_text(render_userscript(preset, debug, video_quality), "utf-8")

    _write_extension(dirs["safari-webextension"], preset, debug, chrome=False)
    _write_extension(dirs["chrome-extension"], preset, debug, chrome=True)

    app = dirs["app"]
    app.mkdir(parents=True)
    (app / "Main.html").write_text(render_app_html(icon="Icon.png"), "utf-8")
    (app / "Style.css").write_text(_template("app/Style.css"), "utf-8")
    (app / "Script.js").write_text(render_app_script(), "utf-8")
    (app / "Icon.png").write_bytes(_icon_bytes(256))

    return BuildResult(userscript, dirs["safari-webextension"], dirs["chrome-extension"], app)


def converter_command(ext_dir: Path, project_dir: Path, bundle_id: str) -> list[str]:
    """Apple's tool that wraps a WebExtension in a macOS app (needs Xcode)."""
    return [
        "xcrun",
        "safari-web-extension-converter",
        str(ext_dir),
        "--project-location",
        str(project_dir),
        "--app-name",
        "Surroundflix",
        "--bundle-identifier",
        bundle_id,
        "--macos-only",
        "--swift",
        "--copy-resources",
        "--no-open",
        "--no-prompt",
        "--force",
    ]


XCODE_SELECT_HELP = (
    "Apple's converter (safari-web-extension-converter) comes with the full Xcode, "
    "but the command line is using the Command Line Tools. Install Xcode from the "
    "App Store, open it once, then run:\n"
    "  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer && "
    "sudo xcodebuild -license accept"
)


def require_converter() -> None:
    """Fail early, with the fix, when xcrun points at the Command Line Tools."""
    found = subprocess.run(  # nosec B603 B607
        ["xcrun", "--find", "safari-web-extension-converter"],
        capture_output=True,
        text=True,
        check=False,
    )
    if found.returncode != 0:
        raise RuntimeError(XCODE_SELECT_HELP)


def make_xcode_project(
    ext_dir: Path, project_dir: Path, bundle_id: str, dry_run: bool = False
) -> list[str]:
    cmd = converter_command(ext_dir, project_dir, bundle_id)
    if dry_run:
        return cmd
    if platform.system() != "Darwin":
        raise RuntimeError("The Xcode step only runs on macOS. Use --dry-run to print the command.")
    if shutil.which("xcrun") is None:
        raise RuntimeError(
            "xcrun not found. Install Xcode from the App Store, then run: xcode-select --install"
        )
    require_converter()
    subprocess.run(cmd, check=True)  # nosec B603

    from .xcode import customize_project

    for note in customize_project(Path(project_dir)):
        print(note)
    return cmd
