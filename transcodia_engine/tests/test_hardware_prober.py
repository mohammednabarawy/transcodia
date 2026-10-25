import pytest
from unittest.mock import patch, MagicMock
from transcodia_engine import HardwareProber, HardwareCapabilities, HardwareAccel, VideoCodec


def test_compiled_encoder_parsing():
    prober = HardwareProber(ffmpeg_path="fake_ffmpeg")
    fake_output = """
Encoders:
 V..... libx264              (codec h264)
 V....D h264_nvenc           (codec h264)
 V..... h264_qsv             (codec h264)
 V....D h264_amf             (codec h264)
 V....D h264_mf              (codec h264)
 A....D aac                  (codec aac)
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=fake_output, returncode=0)
        encoders = prober.probe_compiled_encoders()

    assert "libx264" in encoders
    assert "h264_nvenc" in encoders
    assert "h264_qsv" in encoders
    assert "h264_amf" in encoders
    assert "h264_mf" in encoders
    assert "aac" not in encoders  # audio encoder, not V (video)


def test_resolve_best_encoder_with_fallback():
    prober = HardwareProber(ffmpeg_path="fake_ffmpeg")
    # Simulate host with NO NVENC, but libx264 is available
    mock_caps = HardwareCapabilities(
        compiled_encoders={"libx264", "h264_nvenc"},
        nvenc_h264=False,
    )
    with patch.object(prober, "probe", return_value=mock_caps):
        # 1. Fallback allowed -> should return software
        enc, hw = prober.resolve_best_encoder(
            codec=VideoCodec.H264,
            preferred_hw=HardwareAccel.NVENC,
            allow_fallback=True,
        )
        assert enc == "libx264"
        assert hw == HardwareAccel.NONE

        # 2. Fallback disallowed -> should raise RuntimeError
        with pytest.raises(RuntimeError, match="NVENC requested"):
            prober.resolve_best_encoder(
                codec=VideoCodec.H264,
                preferred_hw=HardwareAccel.NVENC,
                allow_fallback=False,
            )


def test_resolve_best_encoder_success():
    prober = HardwareProber(ffmpeg_path="fake_ffmpeg")
    # Simulate host WITH working Media Foundation h264_mf
    mock_caps = HardwareCapabilities(
        compiled_encoders={"libx264", "h264_mf"},
        mf_h264=True,
    )
    with patch.object(prober, "probe", return_value=mock_caps):
        enc, hw = prober.resolve_best_encoder(
            codec=VideoCodec.H264,
            preferred_hw=HardwareAccel.MEDIA_FOUNDATION,
            allow_fallback=False,
        )
        assert enc == "h264_mf"
        assert hw == HardwareAccel.MEDIA_FOUNDATION


def test_copy_codec_resolution():
    prober = HardwareProber(ffmpeg_path="fake_ffmpeg")
    enc, hw = prober.resolve_best_encoder(codec=VideoCodec.COPY)
    assert enc == "copy"
    assert hw == HardwareAccel.NONE
