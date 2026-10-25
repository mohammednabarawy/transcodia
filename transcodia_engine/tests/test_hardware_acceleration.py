import pytest
from transcodia_engine import (
    FFMpegEngine,
    ConvertTaskItem,
    ProfileCatalog,
    VideoConfig,
    AudioConfig,
    VideoCodec,
    HardwareAccel,
)


def test_nvenc_h264_encoder():
    engine = FFMpegEngine()
    v_cfg, a_cfg = ProfileCatalog.get_preset("nvenc_h264_fast")
    task = ConvertTaskItem(
        src_file="in.mp4",
        dst_file="out.mp4",
        video_config=v_cfg,
        audio_config=a_cfg,
    )
    cmd = engine.build_command_line(task)

    assert "-c:v h264_nvenc" in cmd
    assert "-preset slow" in cmd
    assert "-cq:v 18" in cmd


def test_nvenc_hevc_encoder():
    engine = FFMpegEngine()
    task = ConvertTaskItem(
        src_file="raw.mov",
        dst_file="out.mp4",
        video_config=VideoConfig(
            codec=VideoCodec.HEVC,
            hw_accel=HardwareAccel.NVENC,
            cq=20,
            preset="fast",
        )
    )
    cmd = engine.build_command_line(task)

    assert "-c:v hevc_nvenc" in cmd
    assert "-preset fast" in cmd
    assert "-cq:v 20" in cmd


def test_qsv_h264_encoder():
    engine = FFMpegEngine()
    v_cfg, a_cfg = ProfileCatalog.get_preset("qsv_h264_balanced")
    task = ConvertTaskItem(
        src_file="in.mkv",
        dst_file="out.mp4",
        video_config=v_cfg,
        audio_config=a_cfg,
    )
    cmd = engine.build_command_line(task)

    assert "-c:v h264_qsv" in cmd
    assert "-preset slow" in cmd
    assert "-cq:v 24" in cmd


def test_amf_h264_encoder():
    engine = FFMpegEngine()
    v_cfg, a_cfg = ProfileCatalog.get_preset("amf_h264_quality")
    task = ConvertTaskItem(
        src_file="gameplay.mp4",
        dst_file="encoded.mp4",
        video_config=v_cfg,
        audio_config=a_cfg,
    )
    cmd = engine.build_command_line(task)

    assert "-c:v h264_amf" in cmd
    assert "-preset quality" in cmd
    assert "-cq:v 24" in cmd


def test_software_fallback():
    engine = FFMpegEngine()
    task = ConvertTaskItem(
        src_file="sample.mp4",
        dst_file="out.mp4",
        video_config=VideoConfig(
            codec=VideoCodec.H264,
            hw_accel=HardwareAccel.NONE,
            crf=23,
        )
    )
    cmd = engine.build_command_line(task)

    assert "-c:v libx264" in cmd
    assert "-crf 23" in cmd
    assert "nvenc" not in cmd
    assert "qsv" not in cmd
    assert "amf" not in cmd
