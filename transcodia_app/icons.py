"""Load Transcodia's generated PNG artwork; no external application resources."""
from functools import lru_cache
from pathlib import Path

from PySide6 import QtGui

ASSETS = Path(__file__).with_name("assets")
VIDEO_FORMATS = {"mp4", "mkv", "gif", "webm"}
AUDIO_FORMATS = {"mp3", "wma", "flac", "aac", "wav", "m4a", "ogg", "m4r", "ac3"}
IMAGE_FORMATS = {"webp", "jpg", "png", "ico", "bmp", "tiff", "tga"}
ALIASES = {"play": "start", "player": "start", "join_video": "join", "audio_join": "join",
           "other_video": "video", "fast_clip": "clip", "dvd2video": "disc", "cd2audio": "disc",
           "disc2iso": "disc", "iso2cso": "disc", "batch_resize": "picture"}


def asset_path(name):
    if name == "app":
        return ASSETS / "app-mark.png"
    if name in VIDEO_FORMATS:
        name = "video"
    elif name in AUDIO_FORMATS:
        name = "audio"
    elif name in IMAGE_FORMATS:
        name = "picture"
    elif "pdf" in name or name == "markitdown":
        name = "document"
    name = ALIASES.get(name, name)
    target = ASSETS / "icons" / (name + ".png")
    return target if target.is_file() else ASSETS / "icons" / "document.png"


@lru_cache(maxsize=128)
def icon(name):
    return QtGui.QIcon(str(asset_path(name)))
