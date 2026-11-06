"""Documentation checks: internal links and anchors in every Markdown file,
and one version number everywhere. External links are checked weekly by
.github/workflows/links.yml."""

import re
import sys
import xml.dom.minidom
from pathlib import Path

import pytest

import surroundflix

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted(p for p in ROOT.glob("*.md")) + sorted((ROOT / ".github").glob("*.md"))


def slug(heading: str) -> str:
    """GitHub's anchor for a heading."""
    text = re.sub(r"[`*_\[\]()]", "", heading.strip().lower())
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_internal_links_resolve(doc):
    text = doc.read_text()
    anchors = {slug(h) for h in re.findall(r"^#+ (.+)$", text, re.M)}
    targets = re.findall(r'(?:href|src|srcset)="([^"]+)"|\]\(([^)\s]+)\)', text)
    broken = []
    for a, b in targets:
        target = a or b
        if re.match(r"[a-z]+:", target):
            continue
        path, _, anchor = target.partition("#")
        if path:
            if not (doc.parent / path).exists():
                broken.append(target)
        elif anchor not in anchors:
            broken.append(target)
    assert not broken, broken


def test_the_version_has_a_changelog_section():
    assert f"## [{surroundflix.__version__}]" in (ROOT / "CHANGELOG.md").read_text()


def test_showcase_svg_is_safe_and_up_to_date():
    """design/showcase.svg is drawn from the templates: it must match them,
    and contain nothing GitHub would block or that could run."""
    svg_path = ROOT / "design" / "showcase.svg"
    svg = svg_path.read_text()
    xml.dom.minidom.parseString(svg)  # noqa: S318 (our own generated file)
    for forbidden in ("<script", "<img", "data:", "javascript:", "onload=", "onclick="):
        assert forbidden not in svg.lower(), forbidden
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_showcase

    height = int(re.search(r'height="(\d+)"', svg).group(1))
    assert svg == make_showcase.compose(height), "run: python scripts/make_showcase.py"
