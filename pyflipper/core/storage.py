"""SD-card filesystem + the Flipper File Format (FFF).

The ``sdcard/`` folder mirrors a real Flipper's SD layout, and FFF read/write is
byte-compatible with real ``.sub`` / ``.nfc`` / ``.ir`` / ``.rfid`` files, so
you can copy dumps straight to/from a physical Flipper.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from .. import config

# Standard Flipper SD directories (created on first run).
STD_DIRS = [
    "subghz", "subghz/assets",
    "nfc", "nfc/assets",
    "infrared", "infrared/assets",
    "lfrfid",
    "ibutton",
    "badusb",
    "u2f",
    "apps", "apps_data", "apps_assets",
    "dolphin",
    "update",
]


class FlipperFile:
    """A parsed Flipper File Format document (ordered key/value lines)."""

    def __init__(self):
        self.lines: List[Tuple[str, str]] = []   # (key, value); comments key=""

    # -- construction ---------------------------------------------------------
    @classmethod
    def parse(cls, text: str) -> "FlipperFile":
        ff = cls()
        for raw in text.splitlines():
            line = raw.rstrip("\r")
            if not line.strip():
                continue
            if line.lstrip().startswith("#"):
                ff.lines.append(("", line))
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                ff.lines.append((key.strip(), val.strip()))
            else:
                ff.lines.append(("", line))
        return ff

    @classmethod
    def read(cls, path: Path) -> "FlipperFile":
        return cls.parse(Path(path).read_text(encoding="utf-8", errors="replace"))

    # -- access ---------------------------------------------------------------
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        for k, v in self.lines:
            if k == key:
                return v
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        v = self.get(key)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def get_all(self, key: str) -> List[str]:
        return [v for k, v in self.lines if k == key]

    def get_hex_bytes(self, key: str) -> bytes:
        v = self.get(key, "") or ""
        try:
            return bytes(int(b, 16) for b in v.split())
        except ValueError:
            return b""

    # -- building -------------------------------------------------------------
    def set(self, key: str, value) -> "FlipperFile":
        self.lines.append((key, str(value)))
        return self

    def set_hex_bytes(self, key: str, data: bytes) -> "FlipperFile":
        return self.set(key, " ".join(f"{b:02X}" for b in data))

    def comment(self, text: str) -> "FlipperFile":
        self.lines.append(("", f"# {text}"))
        return self

    def header(self, filetype: str, version: int = 1) -> "FlipperFile":
        # header lines must come first
        self.lines.insert(0, ("Version", str(version)))
        self.lines.insert(0, ("Filetype", filetype))
        return self

    def to_text(self) -> str:
        out = []
        for k, v in self.lines:
            out.append(v if k == "" else f"{k}: {v}")
        return "\n".join(out) + "\n"

    def write(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.to_text(), encoding="utf-8")


class Storage:
    """Thin wrapper over the SD directory tree."""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or config.SDCARD_DIR)
        self.ensure_tree()

    def ensure_tree(self):
        self.root.mkdir(parents=True, exist_ok=True)
        for d in STD_DIRS:
            (self.root / d).mkdir(parents=True, exist_ok=True)

    def path(self, *parts) -> Path:
        return self.root.joinpath(*parts)

    def list(self, subdir: str, ext: Optional[str] = None) -> List[Path]:
        d = self.root / subdir
        if not d.exists():
            return []
        items = sorted(p for p in d.iterdir() if p.is_file())
        if ext:
            items = [p for p in items if p.suffix.lower() == ext.lower()]
        return items

    def list_dirs(self, subdir: str) -> List[Path]:
        d = self.root / subdir
        if not d.exists():
            return []
        return sorted(p for p in d.iterdir() if p.is_dir())

    def read_text(self, path) -> str:
        return Path(path).read_text(encoding="utf-8", errors="replace")

    def write_text(self, path, text: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def delete(self, path):
        try:
            Path(path).unlink()
            return True
        except OSError:
            return False

    def unique_path(self, subdir: str, base: str, ext: str) -> Path:
        """Return sdcard/<subdir>/<base><ext>, adding _NN if it already exists."""
        d = self.root / subdir
        d.mkdir(parents=True, exist_ok=True)
        cand = d / f"{base}{ext}"
        i = 1
        while cand.exists():
            cand = d / f"{base}_{i:02d}{ext}"
            i += 1
        return cand
