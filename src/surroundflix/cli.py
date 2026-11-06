"""Build and maintenance tool for Surroundflix."""

from __future__ import annotations

import argparse
import http.client
import json
import sys
from pathlib import Path

from . import __version__, playercore
from . import build as builder
from .profiles import (
    DEFAULT_PRESET,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_MODE,
    PRESETS,
    VIDEO_CODECS,
    VIDEO_MODES,
)


def _cmd_presets(args: argparse.Namespace) -> int:
    for name, profiles in PRESETS.items():
        tag = " (default)" if name == DEFAULT_PRESET else ""
        print(f"{name}{tag}: {', '.join(profiles)}")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    result = builder.build(
        Path(args.out),
        preset=args.preset,
        debug=args.debug,
        video_quality=args.video_quality,
        video_codec=args.video_codec,
    )
    print(f"Userscript:          {result.userscript}")
    print(f"Safari WebExtension: {result.webextension}")
    print(f"Chrome extension:    {result.chrome}")
    print(f"App window preview:  {result.app / 'Main.html'}")
    return 0


def _cmd_xcode(args: argparse.Namespace) -> int:
    result = builder.build(Path(args.out), preset=args.preset, debug=args.debug)
    cmd = builder.make_xcode_project(
        result.webextension, Path(args.project), args.bundle_id, dry_run=args.dry_run
    )
    if args.dry_run:
        print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
    else:
        print(f"Xcode project created in {args.project}. Open it, then press Run.")
    return 0


def _cmd_dmg(args: argparse.Namespace) -> int:
    from . import package

    work = Path(args.work)
    app = package.build_app(work, preset=args.preset, bundle_id=args.bundle_id)
    userscript = work / "dist" / "userscript" / "surroundflix.user.js"
    dmg = package.make_dmg(app, userscript, Path(args.output), builder.HOMEPAGE)
    print(f"Disk image: {dmg}")
    return 0


# Exit codes of `check`: 0 everything found, 1 something Surroundflix relies
# on is missing, 2 the playercore couldn't be found or fetched (inconclusive).
def _cmd_check(args: argparse.Namespace) -> int:
    url = args.url
    try:
        if args.file is None and url is None:
            url = playercore.discover_url()
            if url is None:
                print(
                    "Could not find the playercore URL on netflix.com. Pass --url or --file.",
                    file=sys.stderr,
                )
                return 2
        report = playercore.load(url=url, file=Path(args.file) if args.file else None)
    # Network failures (OSError covers HTTP 403), a connection cut mid-answer
    # (HTTPException) or a refused URL (ValueError): nothing was checked.
    except (ValueError, OSError, http.client.HTTPException) as err:
        print(f"playercore not checked: {err!r}", file=sys.stderr)
        return 2
    out = report.to_dict()

    if args.state:
        state_file = Path(args.state)
        out["comparison"] = playercore.compare_with_state(report, state_file)
        if args.update_state:
            playercore.save_state(report, state_file)

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Playercore: {report.version or 'unknown version'} ({report.size} bytes)")
        for needle, ok in report.found.items():
            print(f"  {'found  ' if ok else 'MISSING'}  {needle}")
        if "comparison" in out:
            c = out["comparison"]
            print(f"  changed since last check: {'yes' if c['changed'] else 'no'}")
        print(
            "OK, Surroundflix should keep working."
            if report.ok
            else "Something Surroundflix relies on is gone."
        )
    return 0 if report.ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="surroundflix", description=__doc__)
    p.add_argument("--version", action="version", version=f"surroundflix {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("presets", help="list the audio presets")
    sp.set_defaults(func=_cmd_presets)

    def add_build_opts(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--preset", default=DEFAULT_PRESET, choices=sorted(PRESETS))
        sp.add_argument("--debug", action="store_true", help="log to the Safari console")
        sp.add_argument(
            "--video-quality",
            default=DEFAULT_VIDEO_MODE,
            choices=VIDEO_MODES,
            help="userscript only: video mode (the extensions have a menu in their popup)",
        )
        sp.add_argument(
            "--video-codec",
            default=DEFAULT_VIDEO_CODEC,
            choices=VIDEO_CODECS,
            help="userscript only: preferred video codec, when Netflix offers it",
        )
        sp.add_argument("--out", default="dist", help="output folder (default: dist)")

    sp = sub.add_parser(
        "build", help="build the userscript, the Safari and Chrome extensions and the app window"
    )
    add_build_opts(sp)
    sp.set_defaults(func=_cmd_build)

    sp = sub.add_parser(
        "xcode", help="build, then wrap the extension in an Xcode project (macOS + Xcode)"
    )
    add_build_opts(sp)
    sp.add_argument("--project", default="build/xcode")
    sp.add_argument("--bundle-id", default="io.github.anzouk.Surroundflix")
    sp.add_argument("--dry-run", action="store_true", help="only print the xcrun command")
    sp.set_defaults(func=_cmd_xcode)

    sp = sub.add_parser("dmg", help="build Surroundflix.app and a .dmg (macOS + Xcode)")
    sp.add_argument("--preset", default=DEFAULT_PRESET, choices=sorted(PRESETS))
    sp.add_argument("--bundle-id", default="io.github.anzouk.Surroundflix")
    sp.add_argument("--work", default="build", help="scratch folder (default: build)")
    sp.add_argument("--output", default=f"release/Surroundflix-{__version__}.dmg")
    sp.set_defaults(func=_cmd_dmg)

    sp = sub.add_parser("check", help="check Netflix's current playercore for breaking changes")
    sp.add_argument("--url", help="playercore URL (copy it from Safari's Network tab)")
    sp.add_argument("--file", help="local copy of the playercore .js")
    sp.add_argument("--state", help="JSON file holding the last known report")
    sp.add_argument("--update-state", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_cmd_check)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as err:
        # Setup problems (no Xcode, wrong xcode-select...): the message says
        # what to do, a traceback would only hide it.
        print(f"surroundflix: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
