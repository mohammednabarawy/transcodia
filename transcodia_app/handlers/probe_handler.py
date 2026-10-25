"""
Media Metadata Prober.
Extracts container duration, resolution, audio/video stream details via FFmpeg.
"""

import subprocess
import re
from dataclasses import dataclass
from typing import Optional

from transcodia_engine.runtime_paths import find_ffmpeg


@dataclass
class MediaDetails:
    duration_seconds: float = 0.0
    width: Optional[int] = None
    height: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    fps: Optional[float] = None
    bitrate_kbps: Optional[int] = None
    channels: Optional[int] = None
    sample_rate: Optional[int] = None


class MediaProbe:
    """Probes media files using the FFmpeg executable found by the runtime resolver."""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or find_ffmpeg()

    def probe(self, file_path: str) -> MediaDetails:
        info = MediaDetails()
        try:
            cmd = [self.ffmpeg_path, "-hide_banner", "-i", file_path]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False, timeout=10)
            output = res.stderr

            # Duration: 00:01:23.45
            dur_m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
            if dur_m:
                h, m, s = dur_m.groups()
                info.duration_seconds = int(h) * 3600 + int(m) * 60 + float(s)

            # Bitrate: 1542 kb/s
            br_m = re.search(r"bitrate:\s*(\d+)\s*kb/s", output)
            if br_m:
                info.bitrate_kbps = int(br_m.group(1))

            # Video stream: Stream #0:0: Video: h264 (...), 1920x1080 [SAR ...], 25 fps
            v_m = re.search(r"Stream #\d+:\d+.*?: Video:\s*([a-zA-Z0-9_\-]+)", output)
            if v_m:
                info.video_codec = v_m.group(1)

            res_m = re.search(r",\s*(\d{2,5})x(\d{2,5})", output)
            if res_m:
                info.width = int(res_m.group(1))
                info.height = int(res_m.group(2))

            fps_m = re.search(r",\s*([\d\.]+)\s*fps", output)
            if fps_m:
                info.fps = float(fps_m.group(1))

            # Audio stream: Stream #0:1: Audio: aac, 48000 Hz, stereo
            a_m = re.search(r"Stream #\d+:\d+.*?: Audio:\s*([a-zA-Z0-9_\-]+)", output)
            if a_m:
                info.audio_codec = a_m.group(1)

            hz_m = re.search(r"(\d{4,6})\s*Hz", output)
            if hz_m:
                info.sample_rate = int(hz_m.group(1))

            if "stereo" in output:
                info.channels = 2
            elif "mono" in output:
                info.channels = 1
            elif "5.1" in output:
                info.channels = 6

        except Exception:
            pass

        return info
