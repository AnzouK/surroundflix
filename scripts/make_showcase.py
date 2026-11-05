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
  --frame-line: #d1d9e0; --frame-muted: #59636e; }
@media (prefers-color-scheme: dark) { .sf-frame { --frame-line: #3d444d; --frame-muted: #9198a1; } }
.sf-frame figure { margin: 0; }
.sf-panel { border: 1px solid var(--frame-line); border-radius: 6px; overflow: hidden; }
.sf-frame figcaption { color: var(--frame-muted); text-align: center; margin-top: 8px; }
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
    svg = re.sub(r"<title>.*?</title>", "", svg)
    return re.sub(
        r'width="\d+" height="\d+"',
        f'width="{size}" height="{size}" aria-hidden="true"',
        svg,
        count=1,
    ).strip()


def app_markup(strings: dict) -> str:
    html = (TEMPLATES / "app" / "Main.html").read_text()
    main = re.search(r'<main class="window">.*?</main>', html, re.S).group(0)
    main = re.sub(r'\s*<p id="all-set"[^>]*></p>', "", main)
    main = main.replace('data-i18n="status_checking"', 'data-i18n="status_off"')
    main = fill(main, strings)
    main = main.replace('class="status" id="status"', 'class="status off" id="status"')
    main = main.replace('id="version"></div>', f'id="version">{__version__}</div>')
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
    main = fill(main, strings)
    main = main.replace('value="atmos">', 'value="atmos" checked>')
    best = strings["tab_best"].split("{format}")
    main = main.replace(
        '<p id="tab-status" aria-live="polite"></p>',
        f'<p id="tab-status">{best[0]}<strong>Dolby Atmos</strong>{best[1]}</p>',
    )
    main = re.sub(r"<img [^>]*>", icon(28), main, count=1)
    return f'<div class="sf-popup">{xhtml(main)}</div>'


def compose(height: int) -> str:
    strings = load_i18n()["strings"]["en"]
    css = "\n".join(
        [
            FRAME_CSS,
            scope_css((TEMPLATES / "app" / "Style.css").read_text(), ".sf-app"),
            scope_css((TEMPLATES / "popup.css").read_text(), ".sf-popup"),
            # The popup sets a fixed body width; the panel width does that here.
            ".sf-popup { margin: 0; } .sf-app .window { margin: 0; }",
        ]
    )
    body = (
        '<div class="sf-frame">'
        f'<figure><div class="sf-panel">{app_markup(strings)}</div><figcaption>App window</figcaption></figure>'
        f'<figure><div class="sf-panel">{popup_markup(strings)}</div><figcaption>Toolbar button</figcaption></figure>'
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
