"""
Core Command Construction Engine for FFmpeg Execution.
Builds FFmpeg command lines from a conversion task and its parameters.
"""

import os
import re
import shlex
from typing import List, Optional, Dict, Any

from .models import (
    ConvertTaskItem,
    VideoConfig,
    AudioConfig,
    VideoCodec,
    AudioCodec,
    HardwareAccel,
    AspectRatio,
)
from .filter_builder import FilterBuilder
from .runtime_paths import find_ffmpeg


class FFMpegEngine:
    """Orchestrates format transformation, parameter calculation, and CLI synthesis."""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or find_ffmpeg()

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """Formats floating seconds to HH:MM:SS.xxx as FFmpeg expects."""
        hrs = int(seconds // 3600)
        rem = seconds % 3600
        mins = int(rem // 60)
        secs = rem % 60
        return f"{hrs:02d}:{mins:02d}:{secs:06.3f}"

    def resolve_video_encoder(self, codec: VideoCodec, hw: HardwareAccel) -> str:
        """Maps logical codec and hardware acceleration engine to exact FFmpeg encoder."""
        if codec == VideoCodec.COPY:
            return "copy"

        if hw == HardwareAccel.NVENC:
            if codec == VideoCodec.H264:
                return "h264_nvenc"
            elif codec == VideoCodec.HEVC:
                return "hevc_nvenc"
        elif hw == HardwareAccel.QSV:
            if codec == VideoCodec.H264:
                return "h264_qsv"
            elif codec == VideoCodec.HEVC:
                return "hevc_qsv"
        elif hw == HardwareAccel.AMF:
            if codec == VideoCodec.H264:
                return "h264_amf"
            elif codec == VideoCodec.HEVC:
                return "hevc_amf"
        elif hw == HardwareAccel.MEDIA_FOUNDATION:
            if codec == VideoCodec.H264:
                return "h264_mf"
            elif codec == VideoCodec.HEVC:
                return "hevc_mf"

        # Software encoder defaults
        mapping = {
            VideoCodec.H264: "libx264",
            VideoCodec.HEVC: "libx265",
            VideoCodec.VP9: "libvpx-vp9",
            VideoCodec.MPEG4: "mpeg4",
            VideoCodec.AV1: "libsvtav1",
            VideoCodec.MPEG2: "mpeg2video",
            VideoCodec.WMV: "wmv2",
            VideoCodec.FLV: "flv",
            VideoCodec.GIF: "gif",
        }
        return mapping.get(codec, "libx264")

    def resolve_audio_encoder(self, codec: AudioCodec) -> str:
        """Maps logical audio codec to standard FFmpeg encoder."""
        if codec == AudioCodec.COPY:
            return "copy"
        mapping = {
            AudioCodec.AAC: "aac",
            AudioCodec.MP3: "libmp3lame",
            AudioCodec.AC3: "ac3",
            AudioCodec.OPUS: "libopus",
            AudioCodec.FLAC: "flac",
            AudioCodec.VORBIS: "libvorbis",
            AudioCodec.WMA: "wmav2",
            AudioCodec.PCM: "pcm_s16le",
        }
        return mapping.get(codec, "aac")

    def build_cli_arguments(self, task: ConvertTaskItem) -> List[str]:
        """
        Builds the argument list for FFmpeg execution.
        Builds the full FFmpeg command line for a task.
        """
        args: List[str] = [self.ffmpeg_path]

        # 1. Concat file fast-path
        if task.src_file.lower().endswith(".txt"):
            args.extend(["-safe", "0", "-y", "-f", "concat", "-i", task.src_file, "-c", "copy", task.dst_file])
            return args

        # 2. Timing and Trimming Options
        if task.additional_config:
            cfg = task.additional_config
            if cfg.is_loop_image:
                args.extend(["-t", f"{cfg.image_duration:.2f}", "-loop", "1"])
            else:
                if cfg.start_time > 0.0:
                    args.extend(["-ss", self.format_timestamp(cfg.start_time)])
                if cfg.end_time > 0.0:
                    args.extend(["-to", self.format_timestamp(cfg.end_time)])

        # 3. Always overwrite (-y)
        args.append("-y")

        # 4. Custom input prefix if provided (task + 0x368)
        if task.custom_input_prefix:
            args.extend(shlex.split(task.custom_input_prefix))

        # 5. Input files & Concat / Mux Processing
        if task.is_concat and task.additional_input_files:
            all_inputs = [task.src_file] + list(task.additional_input_files)
            n = len(all_inputs)
            for inp in all_inputs:
                args.extend(["-i", inp])

            if task.disable_video:
                concat_filter = "".join(f"[{i}:a:0]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
                args.extend(["-filter_complex", concat_filter, "-map", "[a]", "-vn"])
                a_cfg = task.audio_config or AudioConfig()
                a_codec = a_cfg.codec if a_cfg.codec != AudioCodec.COPY else AudioCodec.AAC
                a_encoder = self.resolve_audio_encoder(a_codec)
                args.extend(["-c:a", a_encoder])
                if a_codec != AudioCodec.COPY:
                    args.extend(["-b:a", f"{a_cfg.bitrate_kbps}k", "-ar", str(a_cfg.sample_rate), "-ac", str(a_cfg.channels)])
            else:
                silent = bool(task.audio_config and task.audio_config.disable_audio)
                concat_filter = ("".join(f"[{i}:v:0]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]") if silent else ("".join(f"[{i}:v:0][{i}:a:0]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
                args.extend(["-filter_complex", concat_filter, "-map", "[v]"])
                if not silent:
                    args.extend(["-map", "[a]"])
                v_cfg = task.video_config or VideoConfig()
                v_codec = v_cfg.codec if v_cfg.codec != VideoCodec.COPY else VideoCodec.H264
                v_encoder = self.resolve_video_encoder(v_codec, v_cfg.hw_accel)
                args.extend(["-c:v", v_encoder])
                if v_cfg.preset and v_encoder in ("libx264", "libx265", "libsvtav1", "h264_nvenc", "hevc_nvenc", "h264_qsv", "hevc_qsv", "h264_amf", "hevc_amf"):
                    args.extend(["-preset", v_cfg.preset])
                if v_cfg.crf is not None and not v_cfg.bitrate_kbps:
                    args.extend(["-crf", str(v_cfg.crf)])
                elif v_cfg.bitrate_kbps:
                    args.extend(["-b:v", f"{v_cfg.bitrate_kbps}k"])
                if v_cfg.fps is not None:
                    args.extend(["-r", f"{v_cfg.fps:g}"])

                a_cfg = task.audio_config or AudioConfig()
                if a_cfg.disable_audio:
                    args.append("-an")
                else:
                    a_codec = a_cfg.codec if a_cfg.codec != AudioCodec.COPY else AudioCodec.AAC
                    a_encoder = self.resolve_audio_encoder(a_codec)
                    args.extend(["-c:a", a_encoder])
                    if a_codec != AudioCodec.COPY:
                        args.extend(["-b:a", f"{a_cfg.bitrate_kbps}k", "-ar", str(a_cfg.sample_rate), "-ac", str(a_cfg.channels)])

            args.extend(["-strict", "-2", "-max_muxing_queue_size", "1024"])
            args.extend(task.output_arguments)
            args.append(task.dst_file)
            return args

        elif task.is_mux:
            args.extend(["-i", task.src_file])
            if task.additional_input_files:
                args.extend(["-i", task.additional_input_files[0]])
            if task.subtitle_file:
                args.extend(["-i", task.subtitle_file])

            args.extend(["-map", "0:v:0"])
            if task.additional_input_files:
                args.extend(["-map", "1:a:0"])
            if task.subtitle_file:
                sub_idx = 2 if task.additional_input_files else 1
                args.extend(["-map", f"{sub_idx}:s:0"])

            v_cfg = task.video_config or VideoConfig(codec=VideoCodec.COPY)
            v_encoder = self.resolve_video_encoder(v_cfg.codec, v_cfg.hw_accel)
            args.extend(["-c:v", v_encoder])

            a_cfg = task.audio_config or AudioConfig(codec=AudioCodec.COPY)
            a_encoder = self.resolve_audio_encoder(a_cfg.codec)
            args.extend(["-c:a", a_encoder])

            if task.subtitle_file:
                dst_ext = os.path.splitext(task.dst_file)[1].lower()
                if dst_ext in (".mp4", ".mov", ".m4v"):
                    args.extend(["-c:s", "mov_text"])
                else:
                    args.extend(["-c:s", "srt"])

            args.extend(["-strict", "-2", "-max_muxing_queue_size", "1024"])
            args.extend(task.output_arguments)
            args.append(task.dst_file)
            return args

        # Standard single file conversion
        args.extend(["-i", task.src_file])
        for extra in task.additional_input_files:
            args.extend(["-i", extra])
        watermark = task.video_config.watermark if task.video_config else None
        if watermark:
            args.extend(["-i", watermark.image_path])

        # 6. Video Options
        v_cfg = task.video_config or VideoConfig()
        v_encoder = self.resolve_video_encoder(v_cfg.codec, v_cfg.hw_accel)
        args.extend(["-c:v", v_encoder])

        if v_cfg.codec != VideoCodec.COPY:
            # Preset
            if v_cfg.preset and v_encoder in ("libx264", "libx265", "libsvtav1", "h264_nvenc", "hevc_nvenc", "h264_qsv", "hevc_qsv", "h264_amf", "hevc_amf"):
                args.extend(["-preset", v_cfg.preset])

            # Rate control: CRF vs Bitrate vs CQ (Hardware Accel)
            if v_cfg.hw_accel != HardwareAccel.NONE and v_cfg.cq is not None:
                args.extend(["-cq:v", str(v_cfg.cq)])
                if v_cfg.bitrate_kbps:
                    args.extend(["-b:v", f"{v_cfg.bitrate_kbps}k"])
            elif v_cfg.crf is not None and not v_cfg.bitrate_kbps:
                args.extend(["-crf", str(v_cfg.crf)])
            elif v_cfg.bitrate_kbps:
                args.extend(["-b:v", f"{v_cfg.bitrate_kbps}k"])

            # Framerate
            if v_cfg.fps is not None:
                args.extend(["-r", f"{v_cfg.fps:g}"])

            # Aspect ratio flag
            if v_cfg.aspect_ratio == AspectRatio.AR_4_3:
                args.extend(["-aspect", "4:3"])
            elif v_cfg.aspect_ratio == AspectRatio.AR_16_9:
                args.extend(["-aspect", "16:9"])
            elif v_cfg.aspect_ratio == AspectRatio.AR_3_2:
                args.extend(["-aspect", "3:2"])
            elif v_cfg.aspect_ratio == AspectRatio.AR_5_4:
                args.extend(["-aspect", "5:4"])
            elif v_cfg.aspect_ratio == AspectRatio.CUSTOM and v_cfg.custom_aspect_ratio:
                args.extend(["-aspect", f"{v_cfg.custom_aspect_ratio:.3f}"])

            # Video Filters (-vf)
            filters = FilterBuilder.build_video_filters(
                v_cfg,
                subtitle_file=task.subtitle_file,
                subtitle_style=task.subtitle_style,
                subtitle_stream_index=task.subtitle_stream_index,
                # An external FFmpeg build may parse Windows drive colons itself.
                escape_drive_colon=True,
            )
            if watermark:
                index = 1 + len(task.additional_input_files)
                base = ",".join(filters) if filters else "null"
                scale = f"scale={watermark.width or -1}:{watermark.height or -1}" if watermark.width or watermark.height else "null"
                overlay = f"overlay={watermark.x}:{watermark.y}"
                if watermark.enable_start is not None or watermark.enable_end is not None:
                    start = watermark.enable_start or 0
                    end = watermark.enable_end if watermark.enable_end is not None else "inf"
                    overlay += f":enable='between(t,{start},{end})'"
                args.extend(["-filter_complex", f"[0:v]{base}[base];[{index}:v]{scale}[logo];[base][logo]{overlay}[watermarked]", "-map", "[watermarked]", "-map", "0:a?"])
            elif filters:
                args.extend(["-vf", ",".join(filters)])

            # x264 custom parameters
            if v_cfg.x264_extra_params and v_encoder == "libx264":
                param_str = ":".join(f"{k}={v}" for k, v in v_cfg.x264_extra_params.items())
                args.extend(["-x264-params", param_str])

        # 7. Audio Options
        a_cfg = task.audio_config or AudioConfig()
        if a_cfg.disable_audio:
            args.append("-an")
        else:
            a_encoder = self.resolve_audio_encoder(a_cfg.codec)
            args.extend(["-c:a", a_encoder])

            if a_cfg.codec != AudioCodec.COPY:
                args.extend(["-b:a", f"{a_cfg.bitrate_kbps}k"])
                args.extend(["-ar", str(a_cfg.sample_rate)])
                args.extend(["-ac", str(a_cfg.channels)])

                # Audio Filters (-af)
                a_filters = FilterBuilder.build_audio_filters(a_cfg)
                if a_filters:
                    args.extend(["-af", ",".join(a_filters)])

        # 8. Muxing safety flags
        args.extend(["-strict", "-2", "-max_muxing_queue_size", "1024"])

        # 9. Output File
        if task.disable_video:
            args.append("-vn")
        args.extend(task.output_arguments)
        args.append(task.dst_file)

        return args

    def build_command_line(self, task: ConvertTaskItem) -> str:
        """Constructs an executable CLI string with quotes for filenames containing spaces."""
        raw_args = self.build_cli_arguments(task)
        quoted_args = []
        for arg in raw_args:
            if " " in arg or '"' in arg:
                quoted_args.append(f'"{arg}"')
            else:
                quoted_args.append(arg)
        return " ".join(quoted_args)

    @staticmethod
    def parse_progress(log_line: str, total_duration_seconds: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Parses FFmpeg stdout/stderr progress updates.
        Parses FFmpeg progress output.
        """
        # Look for time=00:00:10.50 or time=00:00:10
        time_match = re.search(r"time=(-?\d+):(\d+):(\d+(?:\.\d+)?)", log_line)
        if not time_match:
            return None

        h, m, s = time_match.groups()
        current_sec = abs(int(h)) * 3600 + int(m) * 60 + float(s)

        frame_match = re.search(r"frame=\s*(\d+)", log_line)
        fps_match = re.search(r"fps=\s*([\d\.]+)", log_line)
        bitrate_match = re.search(r"bitrate=\s*([\d\.]+[kKmM]bits/s)", log_line)
        speed_match = re.search(r"speed=\s*([\d\.]+)x", log_line)

        progress_pct = None
        if total_duration_seconds and total_duration_seconds > 0:
            progress_pct = min(100.0, max(0.0, (current_sec / total_duration_seconds) * 100.0))

        return {
            "current_seconds": current_sec,
            "progress_percent": progress_pct,
            "frame": int(frame_match.group(1)) if frame_match else None,
            "fps": float(fps_match.group(1)) if fps_match else None,
            "bitrate": bitrate_match.group(1) if bitrate_match else None,
            "speed": float(speed_match.group(1)) if speed_match else None,
        }
