import pytest
from transcodia_engine import (
    FFMpegEngine,
    ConvertTaskItem,
    ProfileCatalog,
    MediaAdditionalConfig,
    VideoCodec,
    AudioCodec,
)


def test_optimal_mp4_preset_generation():
    engine = FFMpegEngine()
    v_cfg, a_cfg = ProfileCatalog.get_preset("mp4_optimal")
    task = ConvertTaskItem(
        src_file="C:/Media/input.avi",
        dst_file="C:/Media/output.mp4",
        video_config=v_cfg,
        audio_config=a_cfg,
    )
    cmd = engine.build_command_line(task)

    assert engine.ffmpeg_path in engine.build_cli_arguments(task)
    assert "-y" in cmd
    assert "-i C:/Media/input.avi" in cmd
    assert "-c:v libx264" in cmd
    assert "-preset fast" in cmd
    assert "-crf 23" in cmd
    assert "-c:a aac" in cmd
    assert "-b:a 128k" in cmd
    assert "-ar 44100" in cmd
    assert "-ac 2" in cmd
    assert "C:/Media/output.mp4" in cmd


def test_1080p_high_preset():
    engine = FFMpegEngine()
    v_cfg, a_cfg = ProfileCatalog.get_preset("mp4_1080p_high")
    task = ConvertTaskItem(
        src_file="C:/Media/test 1080.mkv",
        dst_file="C:/Media/final output.mp4",
        video_config=v_cfg,
        audio_config=a_cfg,
    )
    cmd = engine.build_command_line(task)

    assert '-i "C:/Media/test 1080.mkv"' in cmd
    assert "-c:v libx264" in cmd
    assert "-preset slow" in cmd
    assert "-crf 20" in cmd
    assert "-vf scale=1920:1080" in cmd
    assert "-c:a aac" in cmd
    assert "-b:a 192k" in cmd
    assert '"C:/Media/final output.mp4"' in cmd


def test_audio_mp3_320k_preset():
    engine = FFMpegEngine()
    v_cfg, a_cfg = ProfileCatalog.get_preset("mp3_high_320k")
    task = ConvertTaskItem(
        src_file="song.wav",
        dst_file="song.mp3",
        video_config=v_cfg,
        audio_config=a_cfg,
    )
    cmd = engine.build_command_line(task)

    assert "-c:v copy" in cmd
    assert "-c:a libmp3lame" in cmd
    assert "-b:a 320k" in cmd
    assert "-ar 44100" in cmd
    assert "-ac 2" in cmd


def test_flac_lossless_preset():
    engine = FFMpegEngine()
    v_cfg, a_cfg = ProfileCatalog.get_preset("flac_lossless")
    task = ConvertTaskItem(
        src_file="audio.flac",
        dst_file="converted.flac",
        video_config=v_cfg,
        audio_config=a_cfg,
    )
    cmd = engine.build_command_line(task)

    assert "-c:a flac" in cmd
    assert "-ar 48000" in cmd


def test_concat_txt_fastpath():
    """A .txt concat file is detected and uses -f concat -c copy directly."""
    engine = FFMpegEngine()
    task = ConvertTaskItem(
        src_file="file_list.txt",
        dst_file="merged.mp4",
    )
    args = engine.build_cli_arguments(task)

    assert args == [
        engine.ffmpeg_path,
        "-safe", "0",
        "-y",
        "-f", "concat",
        "-i", "file_list.txt",
        "-c", "copy",
        "merged.mp4"
    ]


def test_clipping_and_timing():
    engine = FFMpegEngine()
    v_cfg, a_cfg = ProfileCatalog.get_preset("mp4_optimal")
    task = ConvertTaskItem(
        src_file="movie.mp4",
        dst_file="clip.mp4",
        video_config=v_cfg,
        audio_config=a_cfg,
        additional_config=MediaAdditionalConfig(
            start_time=65.5,  # 00:01:05.500
            end_time=125.0,   # 00:02:05.000
        )
    )
    cmd = engine.build_command_line(task)

    assert "-ss 00:01:05.500" in cmd
    assert "-to 00:02:05.000" in cmd


def test_image_loop_mode():
    engine = FFMpegEngine()
    task = ConvertTaskItem(
        src_file="cover.jpg",
        dst_file="cover_video.mp4",
        additional_config=MediaAdditionalConfig(
            is_loop_image=True,
            image_duration=10.0,
        )
    )
    cmd = engine.build_command_line(task)

    assert "-t 10.00" in cmd
    assert "-loop 1" in cmd
