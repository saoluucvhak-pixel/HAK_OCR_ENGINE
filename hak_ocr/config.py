from __future__ import annotations
import os
from pathlib import Path
import sys


def data_home() -> Path:
    configured = os.getenv("HAK_OCR_DATA_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base / "HAK" / "SmartOCRAI"
    return Path.home() / ".local" / "share" / "HAKSmartOCRAI"


def resource_root() -> Path:
    # PyInstaller one-folder: bundled files under _MEIPASS; source: project root.
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def ensure_dirs(base: Path | None = None) -> Path:
    root = base or data_home()
    for name in ("originals", "exports", "logs", "models", "cache", "backups"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root
