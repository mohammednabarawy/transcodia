import pytest
from PySide6 import QtWidgets
from transcodia_app.views.output_settings_dialog import OutputSettingsDialog
from transcodia_engine.models import VideoConfig, AudioConfig, VideoCodec, AudioCodec


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_dialog_supports_all_video_codecs(qapp):
    codecs_to_test = [
        VideoCodec.H264,
        VideoCodec.HEVC,
        VideoCodec.VP9,
        VideoCodec.MPEG4,
        VideoCodec.AV1,
        VideoCodec.MPEG2,
        VideoCodec.WMV,
        VideoCodec.FLV,
        VideoCodec.GIF,
        VideoCodec.COPY,
    ]
    for codec in codecs_to_test:
        v_in = VideoConfig(codec=codec)
        dlg = OutputSettingsDialog(initial_video_config=v_in)
        v_out, _, _, _ = dlg.get_configuration()
        assert v_out.codec == codec, f"Codec {codec} failed roundtrip, got {v_out.codec}"


def test_dialog_supports_all_audio_codecs(qapp):
    codecs_to_test = [
        AudioCodec.AAC,
        AudioCodec.MP3,
        AudioCodec.AC3,
        AudioCodec.OPUS,
        AudioCodec.FLAC,
        AudioCodec.VORBIS,
        AudioCodec.WMA,
        AudioCodec.PCM,
        AudioCodec.COPY,
    ]
    for codec in codecs_to_test:
        a_in = AudioConfig(codec=codec)
        dlg = OutputSettingsDialog(initial_audio_config=a_in)
        _, a_out, _, _ = dlg.get_configuration()
        assert a_out.codec == codec, f"Codec {codec} failed roundtrip, got {a_out.codec}"
