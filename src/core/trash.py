"""Safe operations on the current user's freedesktop.org trash directory."""
from __future__ import annotations

import os
from pathlib import Path
import shutil


def trash_root() -> Path:
    return Path.home() / ".local" / "share" / "Trash"


def get_trash_stats() -> dict[str, int]:
    root = trash_root() / "files"
    count = 0
    size = 0
    if not root.exists():
        return {"count": 0, "size": 0}
    for current_root, _, filenames in os.walk(root, followlinks=False):
        for filename in filenames:
            try:
                stat = (Path(current_root) / filename).lstat()
                size += stat.st_size
                count += 1
            except OSError:
                continue
    return {"count": count, "size": size}


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.0f} {unit}" if unit == "Б" else f"{value:.1f} {unit}"
        value /= 1024
    return "0 Б"


def empty_trash() -> dict[str, int]:
    """Empty only ~/.local/share/Trash/{files,info}; never follows symlinks."""
    stats = get_trash_stats()
    root = trash_root()
    for directory_name in ("files", "info"):
        directory = root / directory_name
        if not directory.exists():
            continue
        for item in directory.iterdir():
            try:
                if item.is_symlink() or item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except OSError:
                continue
    return stats
