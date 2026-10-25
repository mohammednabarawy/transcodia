"""
Hardware Acceleration Probing Engine.
Detects which hardware encoders FFmpeg can actually use on this machine.
"""

import subprocess
import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Set

from .models import HardwareAccel, VideoCodec


@dataclass
class HardwareCapabilities:
    """Snapshot of hardware acceleration support on the host machine."""
    compiled_encoders: Set[str] = field(default_factory=set)
    supported_hardware_encoders: Set[str] = field(default_factory=set)
    nvenc_h264: bool = False
    nvenc_hevc: bool = False
    qsv_h264: bool = False
    qsv_hevc: bool = False
    amf_h264: bool = False
    amf_hevc: bool = False
    mf_h264: bool = False
    mf_hevc: bool = False


class HardwareProber:
    """Probes and verifies GPU-accelerated encoder functionality."""

    def __init__(self, ffmpeg_path: str = "ffmpeg.exe"):
        self.ffmpeg_path = ffmpeg_path
        self._cached_caps: Optional[HardwareCapabilities] = None

    def probe_compiled_encoders(self) -> Set[str]:
        """Queries FFmpeg -encoders output to determine compiled-in encoder support."""
        encoders = set()
        try:
            res = subprocess.run(
                [self.ffmpeg_path, "-encoders"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            for line in res.stdout.splitlines():
                line = line.strip()
                # Lines format: V..... encoder_name (codec description)
                m = re.match(r"^V[\.F][\.S][\.X][\.B][\.D]\s+([a-zA-Z0-9_\-]+)", line)
                if m:
                    encoders.add(m.group(1).lower())
        except Exception:
            pass
        return encoders

    def test_encoder(self, encoder: str, timeout_seconds: float = 5.0) -> bool:
        """
        Actively verifies if an encoder initializes and completes a dummy encode.
        Tries a short test encode to confirm the encoder works.
        """
        cmd = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel", "error",
            "-f", "lavfi",
            "-i", "color=c=black:s=64x64:d=0.05",
            "-c:v", encoder,
            "-f", "null",
            "-",
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    def probe(self, force_recheck: bool = False, test_runtime: bool = True) -> HardwareCapabilities:
        """Runs the full hardware acceleration probing suite."""
        if self._cached_caps and not force_recheck:
            return self._cached_caps

        compiled = self.probe_compiled_encoders()
        caps = HardwareCapabilities(compiled_encoders=compiled)

        if not test_runtime:
            self._cached_caps = caps
            return caps

        candidate_encoders = [
            ("h264_nvenc", "nvenc_h264"),
            ("hevc_nvenc", "nvenc_hevc"),
            ("h264_qsv", "qsv_h264"),
            ("hevc_qsv", "qsv_hevc"),
            ("h264_amf", "amf_h264"),
            ("hevc_amf", "amf_hevc"),
            ("h264_mf", "mf_h264"),
            ("hevc_mf", "mf_hevc"),
        ]

        for enc_name, attr_name in candidate_encoders:
            if enc_name in compiled:
                ok = self.test_encoder(enc_name)
                setattr(caps, attr_name, ok)
                if ok:
                    caps.supported_hardware_encoders.add(enc_name)

        self._cached_caps = caps
        return caps

    def resolve_best_encoder(
        self,
        codec: VideoCodec,
        preferred_hw: HardwareAccel = HardwareAccel.NONE,
        allow_fallback: bool = True,
    ) -> Tuple[str, HardwareAccel]:
        """
        Determines the optimal encoder name and hardware acceleration mode.
        If preferred_hw is requested but unavailable and allow_fallback is True,
        falls back gracefully to software or Media Foundation.
        """
        if codec == VideoCodec.COPY:
            return ("copy", HardwareAccel.NONE)

        caps = self.probe(test_runtime=True)

        if preferred_hw == HardwareAccel.NVENC:
            if codec == VideoCodec.H264 and caps.nvenc_h264:
                return ("h264_nvenc", HardwareAccel.NVENC)
            elif codec == VideoCodec.HEVC and caps.nvenc_hevc:
                return ("hevc_nvenc", HardwareAccel.NVENC)
            elif not allow_fallback:
                raise RuntimeError(f"NVENC requested for {codec.value} but not supported by host GPU.")

        elif preferred_hw == HardwareAccel.QSV:
            if codec == VideoCodec.H264 and caps.qsv_h264:
                return ("h264_qsv", HardwareAccel.QSV)
            elif codec == VideoCodec.HEVC and caps.qsv_hevc:
                return ("hevc_qsv", HardwareAccel.QSV)
            elif not allow_fallback:
                raise RuntimeError(f"Intel QSV requested for {codec.value} but not supported by host CPU/GPU.")

        elif preferred_hw == HardwareAccel.AMF:
            if codec == VideoCodec.H264 and caps.amf_h264:
                return ("h264_amf", HardwareAccel.AMF)
            elif codec == VideoCodec.HEVC and caps.amf_hevc:
                return ("hevc_amf", HardwareAccel.AMF)
            elif not allow_fallback:
                raise RuntimeError(f"AMD AMF requested for {codec.value} but not supported by host GPU.")

        elif preferred_hw == HardwareAccel.MEDIA_FOUNDATION:
            if codec == VideoCodec.H264 and caps.mf_h264:
                return ("h264_mf", HardwareAccel.MEDIA_FOUNDATION)
            elif codec == VideoCodec.HEVC and caps.mf_hevc:
                return ("hevc_mf", HardwareAccel.MEDIA_FOUNDATION)
            elif not allow_fallback:
                raise RuntimeError(f"Media Foundation requested for {codec.value} but not supported by host.")

        # Software defaults
        sw_map = {
            VideoCodec.H264: "libx264",
            VideoCodec.HEVC: "libx265",
            VideoCodec.VP9: "libvpx-vp9",
            VideoCodec.AV1: "libsvtav1",
            VideoCodec.MPEG4: "mpeg4",
        }
        return (sw_map.get(codec, "libx264"), HardwareAccel.NONE)
