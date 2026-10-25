import pytest
from transcodia_engine import (
    FFMpegEngine,
    ConvertTaskItem,
    VideoConfig,
    AudioConfig,
    AspectRatio,
    DelogoConfig,
    SubtitleStyle,
)


def test_video_filters_yadif_delogo_crop():
    engine = FFMpegEngine()
    v_cfg = VideoConfig(
        deinterlace=True,
        crop=(10, 20, 640, 480),
        delogo=DelogoConfig(x=100, y=50, width=80, height=40),
        width=1280,
        height=720,
        aspect_ratio=AspectRatio.AR_16_9,
        pad_color="black",
        transpose=1,  # 90 CW
        hflip=True,
    )
    task = ConvertTaskItem(
        src_file="in.ts",
        dst_file="out.mp4",
        video_config=v_cfg,
    )
    cmd = engine.build_command_line(task)

    assert "yadif" in cmd
    assert "delogo=x=100:y=50:w=80:h=40" in cmd
    assert "crop=640:480:10:20" in cmd
    assert "scale=1280:720,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black" in cmd
    assert "transpose=1" in cmd
    assert "hflip" in cmd
    assert "-aspect 16:9" in cmd


def test_audio_filters_denoise_echo_reverse():
    engine = FFMpegEngine()
    a_cfg = AudioConfig(
        denoise=True,
        echo=True,
        reverse=True,
        volume_percent=150,
        fade_out_start=55.0,
        fade_out_duration=3.5,
    )
    task = ConvertTaskItem(
        src_file="in.mp3",
        dst_file="out.mp3",
        audio_config=a_cfg,
    )
    cmd = engine.build_command_line(task)

    assert "volume=1.50" in cmd
    assert "highpass=200,lowpass=3000,afftdn" in cmd
    assert "aecho=0.8:0.9:1000:0.3" in cmd
    assert "areverse" in cmd
    assert "afade=t=out:st=55.00:d=3.50" in cmd


def test_subtitle_burnin_filter():
    engine = FFMpegEngine("ffmpeg")
    style = SubtitleStyle(
        font_name="Microsoft YaHei",
        font_size=28,
        primary_color=0x00FFFF00,  # Yellow
        outline_color=0x00000000,
        bold=True,
        italic=False,
        char_encoding=65001,
    )
    task = ConvertTaskItem(
        src_file="movie.mkv",
        dst_file="movie_sub.mp4",
        subtitle_file="D:/Subs/eng.srt",
        subtitle_style=style,
        subtitle_stream_index=0,
    )
    cmd = engine.build_command_line(task)

    assert "subtitles='D\\:/Subs/eng.srt':si=0:charenc=UTF-8" in cmd
    assert "Fontname=Microsoft YaHei" in cmd
    assert "FontSize=28" in cmd
    assert "PrimaryColour=&H00FFFF00" in cmd
    assert "Bold=-1" in cmd


def test_progress_parser():
    sample_log = "frame=  250 fps= 65.4 q=23.0 size=    1536kB time=00:00:10.50 bitrate=1198.8kbits/s speed=2.75x"
    info = FFMpegEngine.parse_progress(sample_log, total_duration_seconds=100.0)

    assert info is not None
    assert info["current_seconds"] == 10.5
    assert info["progress_percent"] == 10.5
    assert info["frame"] == 250
    assert info["fps"] == 65.4
    assert info["bitrate"] == "1198.8kbits/s"
    assert info["speed"] == 2.75
