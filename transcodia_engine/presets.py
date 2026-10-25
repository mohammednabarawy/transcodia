"""
Predefined Profiles and Presets for the output profile catalog.
"""

from typing import Dict, Tuple
from .models import VideoConfig, AudioConfig, VideoCodec, AudioCodec, HardwareAccel


class ProfileCatalog:
    """Catalog of industry-standard conversion profiles for common targets."""

    @staticmethod
    def get_preset(name: str) -> Tuple[VideoConfig, AudioConfig]:
        presets: Dict[str, Tuple[VideoConfig, AudioConfig]] = {
            # === Video Presets ===
            "mp4_optimal": (
                VideoConfig(codec=VideoCodec.H264, crf=23, preset="fast"),
                AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=128, sample_rate=44100, channels=2),
            ),
            "mp4_1080p_high": (
                VideoConfig(codec=VideoCodec.H264, width=1920, height=1080, crf=20, preset="slow"),
                AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=192, sample_rate=48000, channels=2),
            ),
            "mp4_720p_medium": (
                VideoConfig(codec=VideoCodec.H264, width=1280, height=720, crf=24, preset="fast"),
                AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=128, sample_rate=44100, channels=2),
            ),
            "mp4_480p_economy": (
                VideoConfig(codec=VideoCodec.H264, width=854, height=480, crf=28, preset="faster"),
                AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=96, sample_rate=44100, channels=2),
            ),
            "hevc_high_quality": (
                VideoConfig(codec=VideoCodec.HEVC, crf=26, preset="fast"),
                AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=128, sample_rate=48000, channels=2),
            ),
            "webm_vp9": (
                VideoConfig(codec=VideoCodec.VP9, crf=30, bitrate_kbps=1500),
                AudioConfig(codec=AudioCodec.OPUS, bitrate_kbps=128, sample_rate=48000, channels=2),
            ),
            "nvenc_h264_fast": (
                VideoConfig(codec=VideoCodec.H264, hw_accel=HardwareAccel.NVENC, preset="slow", cq=18),
                AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=192, sample_rate=44100, channels=2),
            ),
            "qsv_h264_balanced": (
                VideoConfig(codec=VideoCodec.H264, hw_accel=HardwareAccel.QSV, preset="slow", cq=24),
                AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=128, sample_rate=44100, channels=2),
            ),
            "amf_h264_quality": (
                VideoConfig(codec=VideoCodec.H264, hw_accel=HardwareAccel.AMF, preset="quality", cq=24),
                AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=128, sample_rate=44100, channels=2),
            ),

            # === Audio Only Presets ===
            "mp3_high_320k": (
                VideoConfig(codec=VideoCodec.COPY),
                AudioConfig(codec=AudioCodec.MP3, bitrate_kbps=320, sample_rate=44100, channels=2),
            ),
            "mp3_standard_192k": (
                VideoConfig(codec=VideoCodec.COPY),
                AudioConfig(codec=AudioCodec.MP3, bitrate_kbps=192, sample_rate=44100, channels=2),
            ),
            "aac_high_256k": (
                VideoConfig(codec=VideoCodec.COPY),
                AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=256, sample_rate=48000, channels=2),
            ),
            "flac_lossless": (
                VideoConfig(codec=VideoCodec.COPY),
                AudioConfig(codec=AudioCodec.FLAC, sample_rate=48000, channels=2),
            ),
        }

        key = name.lower()
        if key not in presets:
            raise KeyError(f"Unknown preset '{name}'. Available: {list(presets.keys())}")
        return presets[key]
