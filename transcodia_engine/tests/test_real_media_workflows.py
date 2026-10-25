"""Decoded media assertions, beyond checking that a command or output file exists."""
import array
import asyncio
import math
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from transcodia_engine import FFMpegEngine, BatchConversionWorker, TaskStatus
from transcodia_engine.models import (ConvertTaskItem, VideoConfig, AudioConfig, VideoCodec, AudioCodec,
    MediaAdditionalConfig, WatermarkConfig, DelogoConfig, SubtitleStyle)
from transcodia_app.handlers.probe_handler import MediaProbe


def convert(binary, task):
    result = subprocess.run(FFMpegEngine(binary).build_cli_arguments(task), capture_output=True, timeout=25)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")[-3500:]
    return MediaProbe(binary).probe(task.dst_file)


def frame(binary, path, at=0.4):
    output = subprocess.run([binary, "-v", "error", "-ss", str(at), "-i", path, "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True, timeout=15)
    return output.stdout


def pcm(binary, path):
    result = subprocess.run([binary, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "8000",
        "-f", "s16le", "-"], capture_output=True, check=True, timeout=15)
    samples = array.array("h")
    samples.frombytes(result.stdout)
    return samples


def test_clip_duration_matches_selected_range(ffmpeg_bin, media_files, tmp_path):
    task = ConvertTaskItem(media_files["video"], str(tmp_path / "trim.mp4"), additional_config=MediaAdditionalConfig(start_time=0.5, end_time=1.5))
    assert convert(ffmpeg_bin, task).duration_seconds == pytest.approx(1, abs=0.15)


@pytest.mark.parametrize("config,expected", [
    (VideoConfig(width=80, height=60), (80, 60)),
    (VideoConfig(crop=(10, 10, 100, 80)), (100, 80)),
    (VideoConfig(transpose=1), (120, 160)), (VideoConfig(transpose=2), (120, 160)),
])
def test_video_dimensions_match_settings(ffmpeg_bin, media_files, tmp_path, config, expected):
    info = convert(ffmpeg_bin, ConvertTaskItem(media_files["video"], str(tmp_path / "result.mp4"), video_config=config))
    assert (info.width, info.height) == expected


@pytest.mark.parametrize("effect", ["hflip", "vflip", "deinterlace", "delogo"])
def test_video_filters_execute(ffmpeg_bin, media_files, tmp_path, effect):
    config = VideoConfig()
    if effect == "delogo":
        config.delogo = DelogoConfig(10, 10, 30, 20)
    else:
        setattr(config, effect, True)
    info = convert(ffmpeg_bin, ConvertTaskItem(media_files["video"], str(tmp_path / f"{effect}.mp4"), video_config=config))
    assert info.video_codec == "h264"
    assert info.duration_seconds > 1.8


def test_watermark_appears_in_decoded_pixels(ffmpeg_bin, media_files, tmp_path):
    watermark = tmp_path / "logo.png"
    Image.new("RGB", (20, 20), "lime").save(watermark)
    output = str(tmp_path / "watermarked.mp4")
    config = VideoConfig(watermark=WatermarkConfig(str(watermark), x=10, y=10))
    convert(ffmpeg_bin, ConvertTaskItem(media_files["silent"], output, video_config=config))
    pixels = frame(ffmpeg_bin, output)
    offset = (15 * 160 + 15) * 3
    red, green, blue = pixels[offset:offset + 3]
    assert green > 150 and red < 80 and blue < 80


def test_subtitle_burnin_changes_actual_frames(ffmpeg_bin, media_files, tmp_path):
    output = str(tmp_path / "subtitles.mp4")
    convert(ffmpeg_bin, ConvertTaskItem(media_files["silent"], output,
        subtitle_file=media_files["subtitle"], subtitle_style=SubtitleStyle(font_size=32)))
    pixels = frame(ffmpeg_bin, output)
    white_pixels = sum(min(pixels[index:index + 3]) > 200 for index in range(0, len(pixels), 3))
    assert white_pixels > 10, "The solid red source should contain visible white subtitle text."


def test_mux_uses_replacement_audio_and_keeps_subtitles(ffmpeg_bin, media_files, tmp_path):
    output = str(tmp_path / "mux.mkv")
    task = ConvertTaskItem(media_files["video"], output, additional_input_files=[media_files["audio"]],
        is_mux=True, subtitle_file=media_files["subtitle"], video_config=VideoConfig(codec=VideoCodec.COPY),
        audio_config=AudioConfig(codec=AudioCodec.COPY))
    convert(ffmpeg_bin, task)
    samples = pcm(ffmpeg_bin, output)
    crossings = sum(samples[i] <= 0 < samples[i + 1] for i in range(len(samples) - 1))
    frequency = crossings / (len(samples) / 8000)
    assert frequency == pytest.approx(880, abs=15)
    subtitle = subprocess.run([ffmpeg_bin, "-v", "error", "-i", output, "-map", "0:s:0", "-f", "srt", "-"], capture_output=True, check=True, timeout=15)
    assert b"Regression caption" in subtitle.stdout


@pytest.mark.parametrize("audio_only", [True, False])
def test_joiner_contains_both_segments(ffmpeg_bin, media_files, tmp_path, audio_only):
    source = media_files["audio"] if audio_only else media_files["video"]
    task = ConvertTaskItem(source, str(tmp_path / ("joined.wav" if audio_only else "joined.mp4")),
        additional_input_files=[source], is_concat=True, disable_video=audio_only,
        audio_config=AudioConfig(codec=AudioCodec.PCM if audio_only else AudioCodec.AAC))
    assert convert(ffmpeg_bin, task).duration_seconds == pytest.approx(4, abs=0.2)


def test_silent_video_join_does_not_require_an_audio_track(ffmpeg_bin, media_files, tmp_path):
    task = ConvertTaskItem(media_files["silent"], str(tmp_path / "silent_join.mp4"),
        additional_input_files=[media_files["silent"]], is_concat=True,
        audio_config=AudioConfig(disable_audio=True))
    assert convert(ffmpeg_bin, task).duration_seconds == pytest.approx(2, abs=0.2)


@pytest.mark.parametrize("field", ["denoise", "echo", "reverse", "fade", "volume"])
def test_audio_effects_produce_decodable_output(ffmpeg_bin, media_files, tmp_path, field):
    config = AudioConfig(codec=AudioCodec.PCM, channels=1, sample_rate=8000)
    if field == "volume":
        config.volume_percent = 25
    elif field == "fade":
        config.fade_out_start, config.fade_out_duration = 1, 1
    else:
        setattr(config, field, True)
    output = str(tmp_path / f"{field}.wav")
    convert(ffmpeg_bin, ConvertTaskItem(media_files["audio"], output, disable_video=True, audio_config=config))
    samples = pcm(ffmpeg_bin, output)
    assert len(samples) >= 15000
    if field == "volume":
        original = pcm(ffmpeg_bin, media_files["audio"])
        rms = lambda values: math.sqrt(sum(x*x for x in values)/len(values))
        assert rms(samples) / rms(original) == pytest.approx(0.25, abs=0.02)
    if field == "fade":
        assert sum(abs(x) for x in samples[-1000:]) < sum(abs(x) for x in samples[:1000]) / 4


def test_frame_sequence_and_segment_outputs_are_real(ffmpeg_bin, media_files, tmp_path):
    for name, arguments, pattern in [
        ("frames", ["-an", "-c:v", "png", "-vf", "fps=2"], "frame_%03d.png"),
        ("segments", ["-f", "segment", "-segment_time", "0.5", "-reset_timestamps", "1"], "part_%03d.mkv"),
    ]:
        folder = tmp_path / name
        task = ConvertTaskItem(media_files["video"], str(folder / pattern), output_arguments=arguments,
            video_config=VideoConfig(codec=VideoCodec.COPY) if name == "segments" else None)
        worker = BatchConversionWorker(FFMpegEngine(ffmpeg_bin))
        task_id = worker.add_task(task)
        result = asyncio.run(worker.run_all())[task_id]
        assert result.status == TaskStatus.COMPLETED, result.error_message
        files = sorted(folder.iterdir())
        assert len(files) >= 3
        if name == "frames":
            for path in files:
                with Image.open(path) as image:
                    assert image.size == (160, 120)
        else:
            def decoded(path):
                return subprocess.run([ffmpeg_bin, "-v", "error", "-i", str(path), "-map", "0:v:0", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True, timeout=15).stdout
            assert b"".join(decoded(path) for path in files) == decoded(media_files["video"])


def test_still_image_loop_has_requested_duration(ffmpeg_bin, sample_image, tmp_path):
    task = ConvertTaskItem(sample_image, str(tmp_path / "slideshow.mp4"),
        additional_config=MediaAdditionalConfig(is_loop_image=True, image_duration=1), audio_config=AudioConfig(disable_audio=True))
    assert convert(ffmpeg_bin, task).duration_seconds == pytest.approx(1, abs=0.2)


@pytest.mark.parametrize("feature", ["two_pass", "anti_shake"])
def test_analysis_features_run_a_real_prepass(ffmpeg_bin, media_files, tmp_path, monkeypatch, feature):
    commands = []
    real_spawn = asyncio.create_subprocess_exec
    async def capture(*args, **kwargs):
        commands.append(args)
        return await real_spawn(*args, **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture)
    config = VideoConfig(bitrate_kbps=300, crf=None)
    setattr(config, feature, True)
    task = ConvertTaskItem(media_files["video"], str(tmp_path / f"{feature}.mp4"), video_config=config)
    worker = BatchConversionWorker(FFMpegEngine(ffmpeg_bin))
    tid = worker.add_task(task)
    result = asyncio.run(worker.run_all())[tid]
    assert result.status == TaskStatus.COMPLETED, result.error_message
    assert len(commands) == 2
    assert MediaProbe(ffmpeg_bin).probe(task.dst_file).duration_seconds > 1.8
    if feature == "two_pass":
        assert commands[0][commands[0].index("-pass") + 1] == "1"
        assert commands[1][commands[1].index("-pass") + 1] == "2"
    else:
        assert any("vidstabdetect" in argument for argument in commands[0])
        assert any("vidstabtransform" in argument and "input=" in argument for argument in commands[1])
