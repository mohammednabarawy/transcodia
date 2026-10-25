"""Resolve bundled and independently installed FFmpeg executables."""
import json
import os
from functools import lru_cache
from pathlib import Path
import shutil
import sys

LOCAL_SETTINGS_NAME = "transcodia.local.json"
EXECUTABLE_SUFFIX = ".exe" if os.name == "nt" else ""


def app_root():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def local_settings():
    folders = [app_root(), Path.cwd()]
    if getattr(sys, "frozen", False):
        folders.append(Path(sys.executable).parent)
    for folder in folders:
        try:
            data = json.loads((folder / LOCAL_SETTINGS_NAME).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            continue
    return {}


def find_ffmpeg():
    name = "ffmpeg" + EXECUTABLE_SUFFIX
    explicit = os.environ.get("FFMPEG_PATH")
    if explicit and Path(explicit).is_file():
        return explicit
    roots = [app_root()]
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).parent)
    for root in roots:
        for candidate in (root / "ffmpeg" / name, root / name, root / "bin" / name):
            if candidate.is_file():
                return str(candidate)
    configured = local_settings().get("ffmpeg_path")
    if isinstance(configured, str) and Path(configured).is_file():
        return configured
    return shutil.which("ffmpeg") or "ffmpeg"
