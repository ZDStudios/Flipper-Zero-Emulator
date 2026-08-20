"""Command line: run or inspect a Flipper .fap on the desktop.

    python -m fapemu run apps/snake.fap
    python -m fapemu info apps/snake.fap
    python -m fapemu list
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _default_app_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "apps"


def cmd_info(args) -> int:
    from .runner import Runner
    runner = Runner(args.file, headless=True)
    print(runner.report())
    if args.imports:
        print("  all imports:")
        for name in sorted(runner.app.imports):
            mark = " " if name in runner.machine.handlers else "!"
            print(f"    {mark} {name}")
        for addr, name in sorted(runner.app.data_symbols.items()):
            print(f"    d {name}")
    return 0


def cmd_run(args) -> int:
    from .runner import Runner
    runner = Runner(args.file,
                    sd_root=Path(args.sd) if args.sd else None,
                    headless=args.headless,
                    verbose=args.verbose,
                    trace=args.trace)
    print(runner.report())
    missing = runner.missing_api
    if missing:
        print(f"\nNote: {len(missing)} imported function(s) are not implemented; "
              "they return 0 if called.")
    print(f"\nRunning {runner.app.name} ... (Esc/Back in-app, or close the window)")
    try:
        code = runner.run(max_seconds=args.seconds)
    except Exception as exc:
        print(f"\nApp stopped with an error: {type(exc).__name__}: {exc}")
        if args.screenshot and runner.display:
            runner.display.save(args.screenshot)
        return 1
    print(f"\nApp exited with code {code} after {runner.frames} frames.")
    if runner.env.unsupported:
        print("  unsupported calls seen: " + ", ".join(
            f"{k} x{v}" for k, v in runner.env.unsupported.items()))
    if args.screenshot and runner.display:
        runner.display.save(args.screenshot)
        print(f"  screenshot written to {args.screenshot}")
    return 0


def cmd_list(args) -> int:
    from . import fapfile
    directory = Path(args.dir) if args.dir else _default_app_dir()
    files = sorted(directory.glob("*.fap")) if directory.exists() else []
    if not files:
        print(f"No .fap files in {directory}")
        return 1
    print(f"{'file':24s} {'name':20s} {'api':>7s} {'imports':>8s}")
    for path in files:
        try:
            fap = fapfile.load(path)
            print(f"{path.name:24s} {fap.manifest.name[:19]:20s} "
                  f"{fap.manifest.api_version:>7s} {len(fap.imports()):8d}")
        except Exception as exc:
            print(f"{path.name:24s} <unreadable: {type(exc).__name__}>")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="fapemu",
        description="Run Flipper Zero .fap applications on your computer.")
    parser.add_argument("--version", action="version", version=f"fapemu {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run a .fap")
    p_run.add_argument("file")
    p_run.add_argument("--sd", help="folder to expose as the Flipper SD card")
    p_run.add_argument("--headless", action="store_true", help="no window (testing)")
    p_run.add_argument("--seconds", type=float, help="stop after N seconds")
    p_run.add_argument("--screenshot", help="save a PNG of the final frame")
    p_run.add_argument("-v", "--verbose", action="store_true", help="show app logs")
    p_run.add_argument("--trace", action="store_true", help="log every API call")
    p_run.set_defaults(func=cmd_run)

    p_info = sub.add_parser("info", help="show a .fap's manifest and imports")
    p_info.add_argument("file")
    p_info.add_argument("--imports", action="store_true", help="list every import")
    p_info.set_defaults(func=cmd_info)

    p_list = sub.add_parser("list", help="list .fap files in a folder")
    p_list.add_argument("dir", nargs="?")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
