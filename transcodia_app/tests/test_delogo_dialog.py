import pytest
from PySide6 import QtWidgets
from transcodia_app.views.delogo_dialog import DelogoDialog
from transcodia_engine.models import VideoCodec


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_delogo_dialog_task_creation(qapp, tmp_path):
    dummy_video = str(tmp_path / "video_sample.mp4")
    with open(dummy_video, "wb") as f:
        f.write(b"0" * 1024)

    dlg = DelogoDialog(dummy_video, default_output_dir=str(tmp_path))
    dlg.spin_x.setValue(50)
    dlg.spin_y.setValue(60)
    dlg.spin_w.setValue(180)
    dlg.spin_h.setValue(75)

    task = dlg.get_task()
    assert task.src_file == dummy_video
    assert "video_sample_Delogo.mp4" in task.dst_file
    assert task.video_config is not None
    assert task.video_config.codec == VideoCodec.H264
    assert task.video_config.delogo is not None
    assert task.video_config.delogo.x == 50
    assert task.video_config.delogo.y == 60
    assert task.video_config.delogo.width == 180
    assert task.video_config.delogo.height == 75
