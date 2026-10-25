"""
Data models and configurations for Media Conversion Engine.
Typed parameter schemas for video, audio, subtitle and task settings.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any


class HardwareAccel(str, Enum):
    NONE = "none"
    NVENC = "nvenc"
    QSV = "qsv"
    AMF = "amf"
    MEDIA_FOUNDATION = "mf"


class VideoCodec(str, Enum):
    H264 = "h264"
    HEVC = "hevc"
    AV1 = "av1"
    VP9 = "vp9"
    MPEG4 = "mpeg4"
    MPEG2 = "mpeg2video"
    WMV = "wmv2"
    FLV = "flv"
    GIF = "gif"
    COPY = "copy"


class AudioCodec(str, Enum):
    AAC = "aac"
    MP3 = "mp3"
    AC3 = "ac3"
    OPUS = "opus"
    FLAC = "flac"
    VORBIS = "vorbis"
    WMA = "wmav2"
    PCM = "pcm_s16le"
    COPY = "copy"


class AspectRatio(str, Enum):
    AUTO = "auto"
    AR_4_3 = "4:3"
    AR_16_9 = "16:9"
    AR_3_2 = "3:2"
    AR_5_4 = "5:4"
    CUSTOM = "custom"


@dataclass
class SubtitleStyle:
    """Subtitle font and rendering styling."""
    font_name: str = "Arial"
    font_size: int = 24
    primary_color: int = 0x00FFFFFF  # White (&H00FFFFFF)
    outline_color: int = 0x00000000  # Black (&H00000000)
    outline_width: int = 2
    shadow_depth: int = 1
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikeout: bool = False
    char_encoding: Optional[int] = 65001  # UTF-8 cp65001

    def to_force_style_string(self) -> str:
        parts = [
            f"Fontname={self.font_name}",
            f"FontSize={self.font_size}",
            "BorderStyle=1",
            f"PrimaryColour=&H{self.primary_color:08X}",
            f"OutlineColour=&H{self.outline_color:08X}",
            f"Outline={self.outline_width}",
            f"Shadow={self.shadow_depth}",
        ]
        if self.bold:
            parts.append("Bold=-1")
        if self.italic:
            parts.append("Italic=-1")
        if self.underline:
            parts.append("Underline=-1")
        if self.strikeout:
            parts.append("Strikeout=-1")
        return ",".join(parts)


@dataclass
class WatermarkConfig:
    """Watermark overlay configuration."""
    image_path: str
    x: int = 10
    y: int = 10
    width: Optional[int] = None
    height: Optional[int] = None
    enable_start: Optional[float] = None
    enable_end: Optional[float] = None


@dataclass
class DelogoConfig:
    """Delogo bounding box."""
    x: int
    y: int
    width: int
    height: int


@dataclass
class VideoConfig:
    """Video transformation and encoding parameters."""
    codec: VideoCodec = VideoCodec.H264
    hw_accel: HardwareAccel = HardwareAccel.NONE
    bitrate_kbps: Optional[int] = None
    crf: Optional[int] = 23
    cq: Optional[int] = None
    preset: str = "fast"
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: AspectRatio = AspectRatio.AUTO
    custom_aspect_ratio: Optional[float] = None
    pad_color: str = "black"
    deinterlace: bool = False
    transpose: Optional[int] = None  # 1: 90 CW, 2: 90 CCW
    vflip: bool = False
    hflip: bool = False
    crop: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h
    delogo: Optional[DelogoConfig] = None
    watermark: Optional[WatermarkConfig] = None
    anti_shake: bool = False
    two_pass: bool = False
    x264_extra_params: dict = field(default_factory=dict)


@dataclass
class AudioConfig:
    """Audio stream transformation and encoding parameters."""
    codec: AudioCodec = AudioCodec.AAC
    bitrate_kbps: int = 128
    sample_rate: int = 44100
    channels: int = 2
    volume_percent: int = 100
    fade_out_start: Optional[float] = None
    fade_out_duration: Optional[float] = None
    denoise: bool = False
    reverse: bool = False
    echo: bool = False
    disable_audio: bool = False


@dataclass
class MediaAdditionalConfig:
    """Clipping and container timing configuration."""
    start_time: float = 0.0
    end_time: float = 0.0
    is_loop_image: bool = False
    image_duration: float = 5.0


@dataclass
class ConvertTaskItem:
    """Batch convert task representation."""
    src_file: str
    dst_file: str
    video_config: Optional[VideoConfig] = None
    audio_config: Optional[AudioConfig] = None
    additional_config: Optional[MediaAdditionalConfig] = None
    subtitle_file: Optional[str] = None
    subtitle_stream_index: Optional[int] = None
    subtitle_style: Optional[SubtitleStyle] = None
    additional_input_files: List[str] = field(default_factory=list)
    custom_input_prefix: Optional[str] = None
    disable_video: bool = False
    output_arguments: List[str] = field(default_factory=list)
    is_concat: bool = False
    is_mux: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Losslessly serializes the task item to a JSON-compatible dictionary."""
        data: Dict[str, Any] = {
            "src_file": self.src_file,
            "dst_file": self.dst_file,
            "additional_input_files": list(self.additional_input_files),
            "custom_input_prefix": self.custom_input_prefix,
            "disable_video": self.disable_video,
            "output_arguments": list(self.output_arguments),
            "is_concat": self.is_concat,
            "is_mux": self.is_mux,
            "subtitle_file": self.subtitle_file,
            "subtitle_stream_index": self.subtitle_stream_index,
        }
        if self.video_config:
            data["video_config"] = {
                "codec": self.video_config.codec.value,
                "hw_accel": self.video_config.hw_accel.value,
                "bitrate_kbps": self.video_config.bitrate_kbps,
                "crf": self.video_config.crf,
                "cq": self.video_config.cq,
                "preset": self.video_config.preset,
                "fps": self.video_config.fps,
                "width": self.video_config.width,
                "height": self.video_config.height,
                "aspect_ratio": self.video_config.aspect_ratio.value,
                "custom_aspect_ratio": self.video_config.custom_aspect_ratio,
                "pad_color": self.video_config.pad_color,
                "deinterlace": self.video_config.deinterlace,
                "transpose": self.video_config.transpose,
                "vflip": self.video_config.vflip,
                "hflip": self.video_config.hflip,
                "crop": list(self.video_config.crop) if self.video_config.crop else None,
                "anti_shake": self.video_config.anti_shake,
                "two_pass": self.video_config.two_pass,
                "x264_extra_params": dict(self.video_config.x264_extra_params),
            }
            if self.video_config.delogo:
                data["video_config"]["delogo"] = {
                    "x": self.video_config.delogo.x,
                    "y": self.video_config.delogo.y,
                    "width": self.video_config.delogo.width,
                    "height": self.video_config.delogo.height,
                }
            if self.video_config.watermark:
                data["video_config"]["watermark"] = {
                    "image_path": self.video_config.watermark.image_path,
                    "x": self.video_config.watermark.x,
                    "y": self.video_config.watermark.y,
                    "width": self.video_config.watermark.width,
                    "height": self.video_config.watermark.height,
                    "enable_start": self.video_config.watermark.enable_start,
                    "enable_end": self.video_config.watermark.enable_end,
                }
        if self.audio_config:
            data["audio_config"] = {
                "codec": self.audio_config.codec.value,
                "bitrate_kbps": self.audio_config.bitrate_kbps,
                "sample_rate": self.audio_config.sample_rate,
                "channels": self.audio_config.channels,
                "volume_percent": self.audio_config.volume_percent,
                "fade_out_start": self.audio_config.fade_out_start,
                "fade_out_duration": self.audio_config.fade_out_duration,
                "denoise": self.audio_config.denoise,
                "reverse": self.audio_config.reverse,
                "echo": self.audio_config.echo,
                "disable_audio": self.audio_config.disable_audio,
            }
        if self.additional_config:
            data["additional_config"] = {
                "start_time": self.additional_config.start_time,
                "end_time": self.additional_config.end_time,
                "is_loop_image": self.additional_config.is_loop_image,
                "image_duration": self.additional_config.image_duration,
            }
        if self.subtitle_style:
            data["subtitle_style"] = {
                "font_name": self.subtitle_style.font_name,
                "font_size": self.subtitle_style.font_size,
                "primary_color": self.subtitle_style.primary_color,
                "outline_color": self.subtitle_style.outline_color,
                "outline_width": self.subtitle_style.outline_width,
                "shadow_depth": self.subtitle_style.shadow_depth,
                "bold": self.subtitle_style.bold,
                "italic": self.subtitle_style.italic,
                "underline": self.subtitle_style.underline,
                "strikeout": self.subtitle_style.strikeout,
                "char_encoding": self.subtitle_style.char_encoding,
            }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConvertTaskItem":
        """Rebuilds a ConvertTaskItem from a serialized dictionary."""
        v_cfg = None
        if "video_config" in data and data["video_config"]:
            vc_data = data["video_config"]
            delogo = None
            if vc_data.get("delogo"):
                delogo = DelogoConfig(**vc_data["delogo"])
            watermark = None
            if vc_data.get("watermark"):
                watermark = WatermarkConfig(**vc_data["watermark"])

            v_cfg = VideoConfig(
                codec=VideoCodec(vc_data.get("codec", "h264")),
                hw_accel=HardwareAccel(vc_data.get("hw_accel", "none")),
                bitrate_kbps=vc_data.get("bitrate_kbps"),
                crf=vc_data.get("crf"),
                cq=vc_data.get("cq"),
                preset=vc_data.get("preset", "fast"),
                fps=vc_data.get("fps"),
                width=vc_data.get("width"),
                height=vc_data.get("height"),
                aspect_ratio=AspectRatio(vc_data.get("aspect_ratio", "auto")),
                custom_aspect_ratio=vc_data.get("custom_aspect_ratio"),
                pad_color=vc_data.get("pad_color", "black"),
                deinterlace=vc_data.get("deinterlace", False),
                transpose=vc_data.get("transpose"),
                vflip=vc_data.get("vflip", False),
                hflip=vc_data.get("hflip", False),
                crop=tuple(vc_data["crop"]) if vc_data.get("crop") else None,
                delogo=delogo,
                watermark=watermark,
                anti_shake=vc_data.get("anti_shake", False),
                two_pass=vc_data.get("two_pass", False),
                x264_extra_params=vc_data.get("x264_extra_params", {}),
            )

        a_cfg = None
        if "audio_config" in data and data["audio_config"]:
            ac_data = data["audio_config"]
            a_cfg = AudioConfig(
                codec=AudioCodec(ac_data.get("codec", "aac")),
                bitrate_kbps=ac_data.get("bitrate_kbps", 128),
                sample_rate=ac_data.get("sample_rate", 44100),
                channels=ac_data.get("channels", 2),
                volume_percent=ac_data.get("volume_percent", 100),
                fade_out_start=ac_data.get("fade_out_start"),
                fade_out_duration=ac_data.get("fade_out_duration"),
                denoise=ac_data.get("denoise", False),
                reverse=ac_data.get("reverse", False),
                echo=ac_data.get("echo", False),
                disable_audio=ac_data.get("disable_audio", False),
            )

        add_cfg = None
        if "additional_config" in data and data["additional_config"]:
            adc_data = data["additional_config"]
            add_cfg = MediaAdditionalConfig(
                start_time=adc_data.get("start_time", 0.0),
                end_time=adc_data.get("end_time", 0.0),
                is_loop_image=adc_data.get("is_loop_image", False),
                image_duration=adc_data.get("image_duration", 5.0),
            )

        sub_style = None
        if "subtitle_style" in data and data["subtitle_style"]:
            sub_style = SubtitleStyle(**data["subtitle_style"])

        return cls(
            src_file=data["src_file"],
            dst_file=data["dst_file"],
            video_config=v_cfg,
            audio_config=a_cfg,
            additional_config=add_cfg,
            subtitle_file=data.get("subtitle_file"),
            subtitle_stream_index=data.get("subtitle_stream_index"),
            subtitle_style=sub_style,
            additional_input_files=list(data.get("additional_input_files", [])),
            custom_input_prefix=data.get("custom_input_prefix"),
            disable_video=data.get("disable_video", False),
            output_arguments=list(data.get("output_arguments", [])),
            is_concat=data.get("is_concat", False),
            is_mux=data.get("is_mux", False),
        )
