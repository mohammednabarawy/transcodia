"""
Filter Graph Builder for Video and Audio filters.
Turns video and audio settings into FFmpeg filter expressions.
"""

from typing import List, Optional
from .models import VideoConfig, AudioConfig, AspectRatio, SubtitleStyle


class FilterBuilder:
    """Constructs FFmpeg -vf, -af, and -filter_complex strings from a conversion's settings."""

    @staticmethod
    def build_video_filters(config: VideoConfig, subtitle_file: Optional[str] = None,
                            subtitle_style: Optional[SubtitleStyle] = None,
                            subtitle_stream_index: Optional[int] = None,
                            escape_drive_colon: bool = True) -> List[str]:
        filters: List[str] = []

        # 1. Anti-shake / Stabilization (vidstabtransform)
        if config.anti_shake:
            filters.append("vidstabtransform=smoothing=10")

        # 2. Deinterlace
        if config.deinterlace:
            filters.append("yadif")

        # 3. Delogo
        if config.delogo:
            d = config.delogo
            filters.append(f"delogo=x={d.x}:y={d.y}:w={d.width}:h={d.height}")

        # 4. Crop
        if config.crop:
            x, y, w, h = config.crop
            filters.append(f"crop={w}:{h}:{x}:{y}")

        # 5. Scaling and Aspect Ratio Padding
        if config.width is not None and config.height is not None:
            w, h = config.width, config.height
            if config.aspect_ratio != AspectRatio.AUTO:
                # Calculate pad dimensions
                color = config.pad_color or "black"
                filters.append(f"scale={w}:{h},pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:{color}")
            else:
                filters.append(f"scale={w}:{h}")

        # 6. Rotation & Flip
        if config.transpose == 1:
            filters.append("transpose=1")
        elif config.transpose == 2:
            filters.append("transpose=2")

        if config.vflip:
            filters.append("vflip")
        if config.hflip:
            filters.append("hflip")

        # 7. Subtitles burn-in filter
        if subtitle_file:
            clean_sub_path = subtitle_file.replace("\\", "/")
            if escape_drive_colon:
                clean_sub_path = clean_sub_path.replace(":", "\\:")
            sub_filter = f"subtitles='{clean_sub_path}'"
            if subtitle_stream_index is not None:
                sub_filter += f":si={subtitle_stream_index}"
            if subtitle_style:
                if subtitle_style.char_encoding:
                    encoding = "UTF-8" if subtitle_style.char_encoding == 65001 else f"cp{subtitle_style.char_encoding}"
                    sub_filter += f":charenc={encoding}"
                style_str = subtitle_style.to_force_style_string()
                sub_filter += f":force_style='{style_str}'"
            filters.append(sub_filter)

        return filters

    @staticmethod
    def build_audio_filters(config: AudioConfig) -> List[str]:
        filters: List[str] = []

        # 1. Volume adjustment
        if config.volume_percent != 100:
            vol = max(0.0, config.volume_percent / 100.0)
            filters.append(f"volume={vol:.2f}")

        # 2. Audio Denoise (preset: highpass=200,lowpass=3000,afftdn)
        if config.denoise:
            filters.append("highpass=200,lowpass=3000,afftdn")

        # 3. Echo effect (preset: aecho=0.8:0.9:1000:0.3)
        if config.echo:
            filters.append("aecho=0.8:0.9:1000:0.3")

        # 4. Reverse audio
        if config.reverse:
            filters.append("areverse")

        # 5. Audio Fade Out
        if config.fade_out_start is not None and config.fade_out_duration is not None:
            filters.append(f"afade=t=out:st={config.fade_out_start:.2f}:d={config.fade_out_duration:.2f}")

        return filters
