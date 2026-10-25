import pytest
from transcodia_engine import (
    FFMpegEngine,
    ConvertTaskItem,
    VideoConfig,
    AudioConfig,
    VideoCodec,
    AudioCodec,
    SubtitleStyle,
    WatermarkConfig,
    DelogoConfig,
    MediaAdditionalConfig,
)


def test_video_concat_command_generation():
    engine = FFMpegEngine()
    task = ConvertTaskItem(
        src_file="C:/Media/part1.mp4",
        dst_file="C:/Media/joined.mp4",
        additional_input_files=["C:/Media/part2.mp4", "C:/Media/part3.mp4"],
        video_config=VideoConfig(codec=VideoCodec.H264, preset="fast", crf=23),
        audio_config=AudioConfig(codec=AudioCodec.AAC, bitrate_kbps=192),
        is_concat=True,
    )
    cmd = engine.build_command_line(task)

    assert "-i C:/Media/part1.mp4" in cmd
    assert "-i C:/Media/part2.mp4" in cmd
    assert "-i C:/Media/part3.mp4" in cmd
    assert "-filter_complex [0:v:0][0:a:0][1:v:0][1:a:0][2:v:0][2:a:0]concat=n=3:v=1:a=1[v][a]" in cmd
    assert "-map [v]" in cmd
    assert "-map [a]" in cmd
    assert "-c:v libx264" in cmd
    assert "-c:a aac" in cmd
    assert "C:/Media/joined.mp4" in cmd


def test_audio_concat_command_generation():
    engine = FFMpegEngine()
    task = ConvertTaskItem(
        src_file="C:/Media/track1.mp3",
        dst_file="C:/Media/joined.mp3",
        additional_input_files=["C:/Media/track2.mp3"],
        audio_config=AudioConfig(codec=AudioCodec.MP3, bitrate_kbps=320),
        disable_video=True,
        is_concat=True,
    )
    cmd = engine.build_command_line(task)

    assert "-i C:/Media/track1.mp3" in cmd
    assert "-i C:/Media/track2.mp3" in cmd
    assert "-filter_complex [0:a:0][1:a:0]concat=n=2:v=0:a=1[a]" in cmd
    assert "-map [a]" in cmd
    assert "-vn" in cmd
    assert "-c:a libmp3lame" in cmd
    assert "C:/Media/joined.mp3" in cmd


def test_mux_stream_mapping_command_generation():
    engine = FFMpegEngine()
    task = ConvertTaskItem(
        src_file="C:/Media/video_raw.mp4",
        dst_file="C:/Media/final_muxed.mp4",
        additional_input_files=["C:/Media/dub_audio.aac"],
        subtitle_file="C:/Media/subs.srt",
        video_config=VideoConfig(codec=VideoCodec.COPY),
        audio_config=AudioConfig(codec=AudioCodec.COPY),
        is_mux=True,
    )
    cmd = engine.build_command_line(task)

    assert "-i C:/Media/video_raw.mp4" in cmd
    assert "-i C:/Media/dub_audio.aac" in cmd
    assert "-i C:/Media/subs.srt" in cmd
    assert "-map 0:v:0" in cmd
    assert "-map 1:a:0" in cmd
    assert "-map 2:s:0" in cmd
    assert "-c:v copy" in cmd
    assert "-c:a copy" in cmd
    assert "-c:s mov_text" in cmd
    assert "C:/Media/final_muxed.mp4" in cmd


def test_task_item_lossless_serialization_roundtrip():
    original = ConvertTaskItem(
        src_file="C:/Media/source.mkv",
        dst_file="C:/Media/dest.mp4",
        additional_input_files=["C:/Media/extra1.mp4", "C:/Media/extra2.mp4"],
        custom_input_prefix="-threads 4",
        disable_video=False,
        output_arguments=["-movflags", "+faststart"],
        is_concat=True,
        is_mux=False,
        subtitle_file="C:/Media/subs.ass",
        subtitle_stream_index=1,
        video_config=VideoConfig(
            codec=VideoCodec.HEVC,
            bitrate_kbps=4000,
            crf=20,
            preset="slow",
            fps=60.0,
            width=1920,
            height=1080,
            delogo=DelogoConfig(x=10, y=10, width=100, height=50),
            watermark=WatermarkConfig(image_path="C:/Media/logo.png", x=50, y=50, width=200, height=80),
        ),
        audio_config=AudioConfig(
            codec=AudioCodec.OPUS,
            bitrate_kbps=160,
            sample_rate=48000,
            channels=2,
            volume_percent=120,
            denoise=True,
        ),
        additional_config=MediaAdditionalConfig(
            start_time=12.5,
            end_time=85.0,
        ),
        subtitle_style=SubtitleStyle(
            font_name="Arial",
            font_size=28,
            primary_color="#FFFF00",
            bold=True,
            outline_width=2.5,
        ),
    )

    data = original.to_dict()
    restored = ConvertTaskItem.from_dict(data)

    assert restored.src_file == original.src_file
    assert restored.dst_file == original.dst_file
    assert restored.additional_input_files == original.additional_input_files
    assert restored.is_concat == original.is_concat
    assert restored.is_mux == original.is_mux
    assert restored.subtitle_file == original.subtitle_file
    assert restored.subtitle_stream_index == original.subtitle_stream_index
    assert restored.video_config.codec == VideoCodec.HEVC
    assert restored.video_config.bitrate_kbps == 4000
    assert restored.video_config.delogo.width == 100
    assert restored.video_config.watermark.image_path == "C:/Media/logo.png"
    assert restored.audio_config.codec == AudioCodec.OPUS
    assert restored.audio_config.sample_rate == 48000
    assert restored.additional_config.start_time == 12.5
    assert restored.subtitle_style.font_name == "Arial"
    assert restored.subtitle_style.primary_color == "#FFFF00"
