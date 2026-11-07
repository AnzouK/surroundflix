"""Builds design/showcase.svg, the README picture of the app window and the
toolbar popup, from the real templates, styles and English strings.

The SVG holds the actual HTML and CSS (in a <foreignObject>), so it stays
sharp at any size, and it switches between light and dark by itself with
prefers-color-scheme, like the app and the popup do.

Run it after changing the app window, the popup or their text:

    python scripts/make_showcase.py

Measuring the layout height needs Playwright (`pip install playwright`);
without it, pass --height.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from surroundflix import __version__  # noqa: E402
from surroundflix.build import REPO, load_i18n  # noqa: E402

TEMPLATES = ROOT / "src" / "surroundflix" / "templates"
OUT = ROOT / "design" / "showcase.svg"
WIDTH = 940

FRAME_CSS = """
.sf-frame { display: flex; gap: 28px; align-items: flex-start; justify-content: center;
  padding: 8px; font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif;
  --frame-line: #c9c5bd; --frame-muted: #59636e; --bar: #e6e3dd; --bar-text: #4a4d53;
  --pop-bg: #f4f2ee; }
@media (prefers-color-scheme: dark) { .sf-frame { --frame-line: #3d424a; --frame-muted: #9198a1;
  --bar: #2a2d32; --bar-text: #c9c7c2; --pop-bg: #1b1d21; } }
.sf-frame figure { margin: 0; }
.sf-frame figcaption { color: var(--frame-muted); text-align: center; margin-top: 10px; }
/* A macOS window: title bar with the three window buttons. */
.sf-window { border: 1px solid var(--frame-line); border-radius: 10px; overflow: hidden; }
.sf-bar { position: relative; height: 28px; background: var(--bar); color: var(--bar-text);
  border-bottom: 1px solid var(--frame-line); font-weight: 600; font-size: 13px;
  display: flex; align-items: center; justify-content: center; }
.sf-lights { position: absolute; left: 10px; top: 8px; display: flex; gap: 8px; }
.sf-lights i { width: 12px; height: 12px; border-radius: 50%; display: block; }
.sf-lights i:nth-child(1) { background: #ff5f57; } .sf-lights i:nth-child(2) { background: #febc2e; }
.sf-lights i:nth-child(3) { background: #28c840; }
/* Safari's popover: rounded panel with an arrow pointing at the toolbar button. */
.sf-pop { position: relative; margin-top: 9px; border: 1px solid var(--frame-line);
  border-radius: 10px; }
.sf-pop .sf-popup { border-radius: 10px; overflow: hidden; }
.sf-arrow { position: absolute; top: -7px; left: 50%; width: 12px; height: 12px; margin-left: -6px;
  background: var(--pop-bg); border-left: 1px solid var(--frame-line);
  border-top: 1px solid var(--frame-line); transform: rotate(45deg); }
.sf-app { width: 584px; } .sf-popup { width: 300px; }
"""


def split_rules(css: str) -> list[tuple[str, str]]:
    """Top-level (prelude, body) pairs; @media bodies stay raw."""
    rules, depth, start, prelude = [], 0, 0, ""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for i, ch in enumerate(css):
        if ch == "{":
            if depth == 0:
                prelude, start = css[start:i].strip(), i + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                rules.append((prelude, css[start:i]))
                start = i + 1
    return rules


def scope_selector(sel: str, scope: str) -> str | None:
    sel = sel.strip()
    if sel.startswith(':root[data-theme="dark"]'):
        return None  # manual theme switch, not used in the picture
    sel = sel.replace(':root:not([data-theme="light"])', scope)
    for root in (":root", "html", "body"):
        if sel == root:
            return scope
    if sel.startswith(scope):
        return sel
    return f"{scope} {sel}"


def scope_css(css: str, scope: str) -> str:
    out = []
    for prelude, body in split_rules(css):
        if prelude.startswith("@media"):
            inner = scope_css(body, scope)
            if inner.strip():
                out.append(f"{prelude} {{ {inner} }}")
            continue
        sels = [s for s in (scope_selector(p, scope) for p in prelude.split(",")) if s]
        if sels:
            out.append(f"{', '.join(sels)} {{{body}}}")
    return "\n".join(out)


def fill(markup: str, strings: dict) -> str:
    def text(m):
        value = strings[m.group(2)]
        value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'{m.group(1)}data-i18n="{m.group(2)}"{m.group(3)}>{value}<'

    return re.sub(r'(<[^>]*?)data-i18n="(\w+)"([^>]*)><', text, markup)


def xhtml(markup: str) -> str:
    """Make HTML5 markup valid XML for a foreignObject."""
    markup = re.sub(r"<(img|input|br|hr)\b([^>]*?)\s*/?>", r"<\1\2/>", markup)
    markup = re.sub(r"\s(hidden|checked|disabled|selected)(?=[\s/>])", r' \1="\1"', markup)
    return markup


def icon(size: int) -> str:
    """The icon as inline SVG. GitHub serves repository SVGs with a policy
    that blocks images inside them (even data: URIs), so no <img> here."""
    svg = (ROOT / "assets" / "icon.svg").read_text()
    svg = re.sub(r"<(title|metadata)>.*?</\1>", "", svg, flags=re.S)
    svg = re.sub(r'\s+xmlns:\w+="[^"]*"', "", svg)
    return re.sub(
        r'width="\d+" height="\d+"',
        f'width="{size}" height="{size}" aria-hidden="true"',
        svg,
        count=1,
    ).strip()


def app_markup(strings: dict, version: str) -> str:
    html = (TEMPLATES / "app" / "Main.html").read_text()
    main = re.search(r'<main class="window">.*?</main>', html, re.S).group(0)
    # Shown as it looks once set up: extension on, setup steps replaced by "all set".
    main = re.sub(r'\s*<ol id="steps">.*?</ol>', "", main, flags=re.S)
    main = main.replace('<p id="all-set" hidden ', '<p id="all-set" ')
    main = main.replace('data-i18n="status_checking"', 'data-i18n="status_on"')
    main = fill(main, strings)
    main = main.replace('class="status" id="status"', 'class="status on" id="status"')
    main = main.replace('id="version"></div>', f'id="version">{version}</div>')
    main = main.replace('href="#"', f'href="https://github.com/{REPO}"')
    main = main.replace(
        '<select id="language"></select>',
        f'<select id="language"><option>{strings["language_auto"]}</option></select>',
    )
    main = re.sub(r"<img [^>]*>", icon(64), main, count=1)
    return f'<div class="sf-app">{xhtml(main)}</div>'


def popup_markup(strings: dict) -> str:
    html = (TEMPLATES / "popup.html").read_text()
    main = re.search(r"<main>.*?</main>", html, re.S).group(0)
    main = re.sub(r'\s*<p class="note warn" id="no-dolby"[^>]*></p>', "", main)
    main = re.sub(r'\s*<button [^>]*id="apply-now"[^>]*></button>', "", main)
    main = fill(main, strings)
    main = main.replace('value="atmos">', 'value="atmos" checked>')
    best = strings["tab_best"].split("{format}")
    main = main.replace(
        '<p id="tab-status" aria-live="polite"></p>',
        f'<p id="tab-status">{best[0]}<strong>Dolby Atmos</strong>{best[1]}</p>',
    )
    video = strings["tab_video"].split("{quality}")
    main = main.replace(
        '<p id="tab-video" hidden></p>',
        f'<p id="tab-video">{video[0]}<strong>2160p \u00b7 HEVC Dolby Vision \u00b7 10.4 Mb/s'
        f"</strong>{video[1]}</p>",
    )
    main = main.replace('<option value="auto" ', '<option value="auto" selected ')
    # Safari's menu: VP9 is Chrome only (popup.js removes it the same way).
    main = re.sub(r'\s*<option [^>]*data-browser="chrome"[^>]*>[^<]*</option>', "", main)
    vrange = strings["tab_video_range"].replace("{min}", "342p").replace("{max}", "2160p")
    main = main.replace(
        '<p id="tab-range" class="note" hidden></p>', f'<p id="tab-range" class="note">{vrange}</p>'
    )
    main = main.replace('<p class="debug" id="debug" hidden>', '<p class="debug" id="debug">')
    main = re.sub(r"<img [^>]*>", icon(28), main, count=1)
    return f'<div class="sf-popup">{xhtml(main)}</div>'


def compose(height: int, version: str = __version__) -> str:
    strings = load_i18n()["strings"]["en"]
    css = "\n".join(
        [
            FRAME_CSS,
            scope_css((TEMPLATES / "app" / "Style.css").read_text(), ".sf-app"),
            scope_css((TEMPLATES / "popup.css").read_text(), ".sf-popup"),
            # The popup sets a fixed body width; the panel width does that here.
            ".sf-popup { margin: 0; } .sf-app .window { margin: 0 auto; }",
        ]
    )
    body = (
        '<div class="sf-frame">'
        '<figure><div class="sf-window"><div class="sf-bar"><span class="sf-lights">'
        "<i></i><i></i><i></i></span>Surroundflix</div>"
        f"{app_markup(strings, version)}</div><figcaption>App window</figcaption></figure>"
        f'<figure><div class="sf-pop"><i class="sf-arrow"></i>{popup_markup(strings)}</div>'
        "<figcaption>Toolbar button in Safari</figcaption></figure>"
        "</div>"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="Surroundflix app window and toolbar popup">\n'
        f"<style>{css}</style>\n"
        f'<foreignObject x="0" y="0" width="{WIDTH}" height="{height}">'
        f'<div xmlns="http://www.w3.org/1999/xhtml">{body}</div>'
        "</foreignObject>\n</svg>\n"
    )


def measure() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": 800})
        page.set_content(compose(2000).replace("<svg", '<svg style="display:block"', 1))
        height = page.evaluate("document.querySelector('.sf-frame').getBoundingClientRect().height")
        browser.close()
    return int(height) + 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--height", type=int, help="skip measuring and use this height")
    args = parser.parse_args()
    OUT.write_text(compose(args.height or measure()), "utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
