"""Customises the Xcode project made by Apple's converter.

The converter generates a small macOS app whose window is a WKWebView
showing Main.html, Style.css and Script.js. This module:

  1. replaces those three files with Surroundflix's window (same file
     names, so the Xcode project needs no changes);
  2. patches ViewController.swift so links open in the default browser and
     the page gets the user's system languages;
  3. lets the app reach the network (GitHub, for the update check);
  4. makes the extension's bundle identifier start with the app's, which
     macOS requires (the converter can disagree with itself on the case);
  5. makes the window resizable and big enough for its content, and keeps
     the app open after "Open Safari Settings" (Apple's template quits).

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

LANG_SNIPPET = f"""
        {LANG_MARKER}
        if let data = try? JSONSerialization.data(withJSONObject: Locale.preferredLanguages),
           let json = String(data: data, encoding: .utf8) {{
            webView.evaluateJavaScript("setPreferredLanguages(\\(json))")
        }}
"""

LINK_METHOD = f"""
    {LINK_MARKER}
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
"""

# A block comment, so a one-line closure like `{ terminate(nil) }` keeps its brace.
KEEP_OPEN_MARKER = "/* surroundflix: keep the app open after opening Safari's settings */"
WINDOW_SIZE = (600, 720)

DID_FINISH = re.compile(
    r"func webView\(_ webView: WKWebView, didFinish navigation: WKNavigation!\)\s*\{"
)


def _app_files(project_dir: Path, name: str) -> list[Path]:
    """Files called `name` that belong to the app, not the extension."""
    return [
        p
        for p in sorted(project_dir.rglob(name))
        if "Extension" not in str(p.relative_to(project_dir))
    ]


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
            src = src[: m.end()] + LANG_SNIPPET + src[m.end() :]
    if LINK_MARKER not in src:
        end = src.rstrip().rfind("}")
        if end != -1:
            src = src[:end] + LINK_METHOD + src[end:]
    if KEEP_OPEN_MARKER not in src:
        src = src.replace("NSApplication.shared.terminate(nil)", KEEP_OPEN_MARKER)
    return src


def patch_storyboard_source(xml: str) -> str:
    """Resizable, minimisable window at WINDOW_SIZE (Apple's is 425 x 325, fixed)."""

    def style(m: re.Match) -> str:
        attrs = m.group(1)
        for flag in ("miniaturizable", "resizable"):
            if f'{flag}="YES"' not in attrs:
                attrs += f' {flag}="YES"'
        return f'<windowStyleMask key="styleMask"{attrs}/>'

    xml = re.sub(r'<windowStyleMask key="styleMask"([^/>]*)/>', style, xml)
    rect = re.search(
        r'<rect key="contentRect" x="[^"]*" y="[^"]*" width="(\d+)" height="(\d+)"/>', xml
    )
    if rect:
        old = f'width="{rect.group(1)}" height="{rect.group(2)}"'
        new = f'width="{WINDOW_SIZE[0]}" height="{WINDOW_SIZE[1]}"'
        # The window's content rect and the view controller's views share Apple's size.
        xml = xml.replace(old, new)
    return xml


def patch_storyboard(project_dir: Path) -> list[str]:
    files = _app_files(project_dir, "Main.storyboard")
    if not files:
        return ["warning: Main.storyboard not found, the window keeps Apple's fixed size"]
    before = files[0].read_text("utf-8")
    after = patch_storyboard_source(before)
    if after == before:
        return []
    files[0].write_text(after, "utf-8")
    return [f"window made resizable: {files[0].relative_to(project_dir)}"]


def patch_view_controller(project_dir: Path) -> list[str]:
    files = _app_files(project_dir, "ViewController.swift")
    if not files:
        return ["warning: ViewController.swift not found, links and languages not patched"]
    path = files[0]
    before = path.read_text("utf-8")
    after = patch_view_controller_source(before)
    notes = []
    if LANG_MARKER not in after:
        notes.append(
            "warning: didFinish not found, the window will use the default language detection"
        )
    if after != before:
        path.write_text(after, "utf-8")
        notes.append(f"patched {path.relative_to(project_dir)}")
    return notes


# Matches both project formats: `PRODUCT_BUNDLE_IDENTIFIER = id;` in
# project.pbxproj and `"PRODUCT_BUNDLE_IDENTIFIER": "id",` in project.xcproj.
BUNDLE_ID = re.compile(r'(PRODUCT_BUNDLE_IDENTIFIER"?\s*[:=]\s*"?)([A-Za-z0-9.\-]+)')


def project_files(project_dir: Path) -> list[Path]:
    return sorted(project_dir.rglob("project.pbxproj")) + sorted(
        project_dir.rglob("project.xcproj")
    )


def fix_bundle_ids(project_dir: Path) -> list[str]:
    notes = []
    for proj in project_files(project_dir):
        text = proj.read_text("utf-8")
        ids = [m.group(2) for m in BUNDLE_ID.finditer(text)]
        apps = {i for i in ids if not i.endswith(".Extension")}
        exts = {i for i in ids if i.endswith(".Extension")}
        if len(apps) != 1 or not exts:
            continue
        app = apps.pop()
        wanted = f"{app}.Extension"
        bad = {e for e in exts if not e.startswith(app + ".")}
        if not bad:
            continue
        proj.write_text(
            BUNDLE_ID.sub(
                lambda m, w=wanted, b=bad: m.group(1) + (w if m.group(2) in b else m.group(2)), text
            ),
            "utf-8",
        )
        for swift in project_dir.rglob("*.swift"):
            code = swift.read_text("utf-8")
            fixed = code
            for old in bad:
                fixed = fixed.replace(f'"{old}"', f'"{wanted}"')
            if fixed != code:
                swift.write_text(fixed, "utf-8")
        notes.append(f"extension bundle identifier set to {wanted}")
    return notes


def allow_network(project_dir: Path) -> list[str]:
    notes = []
    entitlements = _app_files(project_dir, "*.entitlements")
    if not entitlements:
        # Newer Xcode templates declare the sandbox in build settings instead.
        if any(
            "ENABLE_OUTGOING_NETWORK_CONNECTIONS" in f.read_text("utf-8")
            for f in project_files(project_dir)
        ):
            return ["network access already enabled in the build settings"]
        return ["warning: no entitlements found; the update check may be blocked by the sandbox"]
    for path in entitlements:
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
    return (
        fix_bundle_ids(project_dir)
        + replace_window(project_dir)
        + patch_view_controller(project_dir)
        + patch_storyboard(project_dir)
        + allow_network(project_dir)
    )
