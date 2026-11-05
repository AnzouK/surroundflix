"""Customises the Xcode project made by Apple's converter.

The converter generates a small macOS app whose window is a WKWebView
showing Main.html, Style.css and Script.js. This module:

  1. replaces those three files with Surroundflix's window (same file
     names, so the Xcode project needs no changes);
  2. patches ViewController.swift so links open in the default browser and
     the page gets the user's system languages;
  3. lets the app reach the network (GitHub, for the update check).

Every step is idempotent, so running it twice changes nothing.
"""

from __future__ import annotations

import os
import plistlib
import re
from pathlib import Path

from .build import _template, render_app_html, render_app_script

LANG_MARKER = "// surroundflix: system languages"
LINK_MARKER = "// surroundflix: open links in the default browser"

LANG_SNIPPET = """
        {marker}
        if let data = try? JSONSerialization.data(withJSONObject: Locale.preferredLanguages),
           let json = String(data: data, encoding: .utf8) {{
            webView.evaluateJavaScript("setPreferredLanguages(\\(json))")
        }}
""".format(marker=LANG_MARKER)

LINK_METHOD = """
    {marker}
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {{
        if navigationAction.navigationType == .linkActivated,
           let url = navigationAction.request.url, url.scheme == "https" {{
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }}
        decisionHandler(.allow)
    }}
""".format(marker=LINK_MARKER)

DID_FINISH = re.compile(r"func webView\(_ webView: WKWebView, didFinish navigation: WKNavigation!\)\s*\{")


def _app_files(project_dir: Path, name: str) -> list[Path]:
    """Files called `name` that belong to the app, not the extension."""
    return [p for p in sorted(project_dir.rglob(name)) if "Extension" not in str(p.relative_to(project_dir))]


def _nearest(start: Path, name: str, root: Path) -> Path | None:
    for folder in (start, *start.parents):
        candidate = folder / name
        if candidate.exists():
            return candidate
        if folder == root:
            break
    return None


def _rel(target: Path, base: Path) -> str:
    return os.path.relpath(target, base).replace(os.sep, "/")


def replace_window(project_dir: Path) -> list[str]:
    mains = _app_files(project_dir, "Main.html")
    if not mains:
        return ["warning: Main.html not found, the app keeps Apple's default window"]
    main = mains[0]
    style = _nearest(main.parent, "Style.css", project_dir)
    script = _nearest(main.parent, "Script.js", project_dir)
    icon = _nearest(main.parent, "Icon.png", project_dir)
    if style is None or script is None:
        return ["warning: Style.css or Script.js not found next to Main.html, window not replaced"]

    main.write_text(
        render_app_html(
            style=_rel(style, main.parent),
            script=_rel(script, main.parent),
            icon=_rel(icon, main.parent) if icon else "",
        ),
        "utf-8",
    )
    style.write_text(_template("app/Style.css"), "utf-8")
    script.write_text(render_app_script(), "utf-8")
    return [f"app window replaced: {main.relative_to(project_dir)}"]


def patch_view_controller_source(src: str) -> str:
    if LANG_MARKER not in src:
        m = DID_FINISH.search(src)
        if m:
            src = src[: m.end()] + LANG_SNIPPET + src[m.end():]
    if LINK_MARKER not in src:
        end = src.rstrip().rfind("}")
        if end != -1:
            src = src[:end] + LINK_METHOD + src[end:]
    return src


def patch_view_controller(project_dir: Path) -> list[str]:
    files = _app_files(project_dir, "ViewController.swift")
    if not files:
        return ["warning: ViewController.swift not found, links and languages not patched"]
    path = files[0]
    before = path.read_text("utf-8")
    after = patch_view_controller_source(before)
    notes = []
    if LANG_MARKER not in after:
        notes.append("warning: didFinish not found, the window will use the default language detection")
    if after != before:
        path.write_text(after, "utf-8")
        notes.append(f"patched {path.relative_to(project_dir)}")
    return notes


def allow_network(project_dir: Path) -> list[str]:
    notes = []
    for path in _app_files(project_dir, "*.entitlements"):
        with path.open("rb") as fh:
            data = plistlib.load(fh)
        if data.get("com.apple.security.network.client") is True:
            continue
        data["com.apple.security.network.client"] = True
        with path.open("wb") as fh:
            plistlib.dump(data, fh)
        notes.append(f"network access enabled in {path.relative_to(project_dir)}")
    return notes


def customize_project(project_dir: Path) -> list[str]:
    project_dir = Path(project_dir)
    return replace_window(project_dir) + patch_view_controller(project_dir) + allow_network(project_dir)
