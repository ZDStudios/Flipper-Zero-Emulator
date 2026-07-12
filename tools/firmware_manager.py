#!/usr/bin/env python3
"""PyFlipper firmware VM manager (EXPERIMENTAL).

Lists Flipper firmware images you've placed under ``sdcard/firmware/`` and
launches them in the Renode emulator using the hand-written STM32WB55 platform.

    python tools/firmware_manager.py list          # show installed images
    python tools/firmware_manager.py sources       # where to download firmware
    python tools/firmware_manager.py doctor        # is Renode installed?
    python tools/firmware_manager.py run <name>    # boot an image in Renode
    python tools/firmware_manager.py run <name> --dry-run   # just print the cmd

Read RENODE.md first: this boots the real firmware's ARM code, but the radios,
BLE and display controller are NOT emulated yet - it's a bring-up scaffold, not
a finished VM.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FW_DIR = REPO / "sdcard" / "firmware"
RESC = REPO / "renode" / "flipper.resc"
IMAGE_EXTS = {".bin", ".elf", ".hex"}

# Where real firmware images come from. We deliberately do NOT auto-download and
# run third-party binaries for you - grab the release, extract the firmware
# image, and drop it in sdcard/firmware/<name>/.
KNOWN_SOURCES = {
    "official":   "https://github.com/flipperdevices/flipperzero-firmware/releases",
    "momentum":   "https://github.com/Next-Flip/Momentum-Firmware/releases",
    "unleashed":  "https://github.com/DarkFlippers/unleashed-firmware/releases",
    "roguemaster": "https://github.com/RogueMaster/flipperzero-firmware-wPlugins/releases",
}


def find_renode() -> str | None:
    """Locate a Renode executable (PATH, $RENODE, or a local ./renode_bin)."""
    env = os.environ.get("RENODE")
    if env and Path(env).exists():
        return env
    exe_names = ("renode.exe", "Renode.exe", "renode", "Renode", "renode.sh")
    for name in ("renode", "renode.exe", "Renode", "Renode.exe"):
        p = shutil.which(name)
        if p:
            return p
    bin_dir = REPO / "renode_bin"
    if bin_dir.exists():
        for cand in bin_dir.rglob("*"):
            if cand.is_file() and cand.name in exe_names:
                return str(cand)
    return None


def list_images() -> list[Path]:
    if not FW_DIR.exists():
        return []
    return sorted(p for p in FW_DIR.rglob("*") if p.suffix.lower() in IMAGE_EXTS)


def cmd_list(_args):
    imgs = list_images()
    if not imgs:
        print(f"No firmware images in {FW_DIR}")
        print("Run 'firmware_manager.py sources' to see where to get them.")
        return
    print(f"Firmware images in {FW_DIR}:\n")
    for p in imgs:
        size = p.stat().st_size / 1024
        print(f"  {p.relative_to(FW_DIR)}   ({size:.0f} KB)")


def cmd_sources(_args):
    print("Download a release, extract the firmware image (e.g. firmware.bin, or")
    print("the .elf from a source build) and place it in sdcard/firmware/<name>/:\n")
    for name, url in KNOWN_SOURCES.items():
        print(f"  {name:12s} {url}")
    print("\nThe update .tgz packages contain firmware.bin; a .dfu can be converted")
    print("with `dfu-util`/`objcopy`. A .elf (from building the firmware) boots best.")


def cmd_doctor(_args):
    renode = find_renode()
    print("Renode:", renode or "NOT FOUND")
    if not renode:
        print("  Install: https://renode.io/  (or unzip the portable build into ./renode_bin)")
        print("  Windows portable needs .NET 8 (you can check with: dotnet --version)")
    print("Platform:", RESC.parent / "stm32wb55.repl",
          "(exists)" if (RESC.parent / "stm32wb55.repl").exists() else "(MISSING)")
    print("Script:  ", RESC, "(exists)" if RESC.exists() else "(MISSING)")
    imgs = list_images()
    print(f"Images:   {len(imgs)} in {FW_DIR}")


def resolve_image(name: str) -> Path | None:
    p = Path(name)
    if p.is_file():
        return p
    want = name.replace("\\", "/").lower()
    for img in list_images():
        rel = str(img.relative_to(FW_DIR)).replace("\\", "/").lower()
        candidates = {
            img.stem.lower(),                 # firmware
            img.name.lower(),                 # firmware.bin
            img.parent.name.lower(),          # official  (the folder name)
            rel,                              # official/firmware.bin
            rel.rsplit(".", 1)[0],            # official/firmware
        }
        if want in candidates:
            return img
    return None


def cmd_run(args):
    img = resolve_image(args.image)
    if not img:
        print(f"Image '{args.image}' not found. Try: firmware_manager.py list")
        return 1
    renode = find_renode()
    # Build the Renode command. Set $bin BEFORE including the script so its
    # `$bin?=` default keeps our value, then start.
    binpath = str(img).replace("\\", "/")
    cmd = [
        renode or "renode",
        "--console", "--disable-xwt",
        "-e", f'$bin=@{binpath}',
        "-e", f'$name="{img.stem}"',
        "-e", f"include @{str(RESC).replace(chr(92), '/')}",
    ]
    if not args.no_start:
        cmd += ["-e", "start"]

    printable = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    print("Renode command:\n  " + printable + "\n")
    if args.dry_run:
        return 0
    if not renode:
        print("Renode is not installed - see 'firmware_manager.py doctor'. (dry run above)")
        return 1
    print(f"Booting {img.name} ...  (Ctrl-C to stop)\n")
    try:
        # Run from the repo root so the script's @renode/... paths resolve.
        return subprocess.call(cmd, cwd=str(REPO))
    except KeyboardInterrupt:
        return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="PyFlipper firmware VM manager (Renode).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list installed firmware images").set_defaults(fn=cmd_list)
    sub.add_parser("sources", help="where to download firmware").set_defaults(fn=cmd_sources)
    sub.add_parser("doctor", help="check Renode + files").set_defaults(fn=cmd_doctor)
    r = sub.add_parser("run", help="boot an image in Renode")
    r.add_argument("image", help="image name (see 'list') or a path")
    r.add_argument("--dry-run", action="store_true", help="print the command only")
    r.add_argument("--no-start", action="store_true", help="load but don't auto-start")
    r.set_defaults(fn=cmd_run)
    args = ap.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
