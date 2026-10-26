from pathlib import Path
import pytest

from PySide6 import QtWidgets

from transcodia_app.handlers.image_handler import ImageConfig
from transcodia_app.views.main_window import ConversionRunnerThread
from transcodia_engine.models import ConvertTaskItem, VideoConfig, VideoCodec, HardwareAccel
from transcodia_engine.worker import TaskResult, TaskStatus


def test_bad_image_does_not_abort_later_images_documents_or_media(qapp, tmp_path, sample_image, sample_pdf, media_files, ffmpeg_bin):
    corrupt = tmp_path / "broken.png"
    corrupt.write_bytes(b"not an image")
    tasks = [
        {"id": "bad", "category": "picture", "src": str(corrupt), "dst": str(tmp_path / "bad.jpg")},
        {"id": "image", "category": "picture", "src": sample_image, "dst": str(tmp_path / "good.jpg")},
        {"id": "document", "category": "doc", "format": "pdf2txt", "src": sample_pdf, "dst": str(tmp_path / "good.txt")},
        {"id": "media", "category": "video", "task_item": ConvertTaskItem(media_files["video"], str(tmp_path / "good.mp4"))},
    ]
    runner = ConversionRunnerThread(tasks, ffmpeg_path=ffmpeg_bin)
    completed, finished = [], []
    runner.task_completed.connect(lambda *args: completed.append(args))
    runner.batch_finished.connect(lambda: finished.append(True))
    runner.run()
    assert [(t[0], t[1]) for t in completed] == [("bad", False), ("image", True), ("document", True), ("media", True)]
    assert finished == [True]
    assert "Invoice 123" in (tmp_path / "good.txt").read_text(encoding="utf-8")


def test_start_stop_before_execution_prevents_all_outputs(qapp, tmp_path, sample_image):
    target = tmp_path / "never.png"
    runner = ConversionRunnerThread([{"id": "one", "category": "picture", "src": sample_image, "dst": str(target)}])
    runner.stop()
    finished = []
    runner.batch_finished.connect(lambda: finished.append(True))
    runner.run()
    assert not target.exists()
    assert finished == [True]


def test_real_start_button_runs_queue_and_restores_controls(app_window, qtbot, sample_image, sample_pdf):
    window = app_window
    window._enqueue_picture_task(sample_image, "jpg", ImageConfig(), False, window.output_dir)
    window._enqueue_doc_task(sample_pdf, "pdf2txt", False, window.output_dir)
    qtbot.mouseClick(window.btn_start, __import__('PySide6').QtCore.Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.runner_thread is not None and not window.runner_thread.isRunning(), timeout=15000)
    qtbot.waitUntil(lambda: all(t["status"] == "completed" for t in window.all_tasks.values()), timeout=2000)
    assert not window.btn_start.isEnabled()
    assert not window.act_start.isEnabled()
    assert not window.btn_stop.isEnabled()
    assert window.btn_clear.isEnabled()
    assert all(Path(t["dst"]).is_file() for t in window.all_tasks.values())


def test_paused_image_batch_waits_until_resume(qapp, qtbot, sample_image, tmp_path):
    target = tmp_path / "paused.png"
    runner = ConversionRunnerThread([{"id": "one", "category": "picture", "src": sample_image, "dst": str(target)}])
    runner.pause()
    runner.start()
    try:
        qtbot.wait(100)
        assert not target.exists()
    finally:
        runner.resume()
        assert runner.wait(5000)
    assert target.exists()


def test_stop_in_gui_reports_cancellation_and_allows_retry(app_window, qtbot, ffmpeg_bin, media_files):
    window = app_window
    task = ConvertTaskItem(media_files["video"], str(Path(window.output_dir) / "stopped.mp4"), custom_input_prefix="-re")
    window.ffmpeg_path = ffmpeg_bin
    window._enqueue_media_task("video", "mp4", task)
    tid = next(iter(window.all_tasks))
    window._start_conversion()
    qtbot.waitUntil(lambda: window.runner_thread._async_worker is not None and bool(window.runner_thread._async_worker._processes), timeout=5000)
    window._stop_conversion()
    qtbot.waitUntil(lambda: window.all_tasks[tid]["status"] != "running", timeout=3000)
    assert window.all_tasks[tid]["status"] == "cancelled"
    assert window.btn_start.isEnabled()


def test_large_completed_output_keeps_full_size_across_qt_signal(qapp, qtbot, tmp_path):
    task = ConvertTaskItem("input.mp4", str(tmp_path / "large.mp4"))
    runner = ConversionRunnerThread([])
    received = []
    runner.task_completed.connect(lambda *args: received.append(args))
    size = 4 * 1024 ** 3 + 17
    runner._on_worker_complete("large", TaskResult("large", task, TaskStatus.COMPLETED, output_size_bytes=size))
    assert received == [("large", True, size, "")]


def test_failed_task_shows_cause_and_opens_complete_error(app_window, monkeypatch):
    window = app_window
    task = ConvertTaskItem("missing.mp4", str(Path(window.output_dir) / "failed.mp4"))
    window._enqueue_media_task("video", "mp4", task)
    tid = next(iter(window.all_tasks))
    error = "[h264_mf] could not initialize encoder\nTask finished with error code: -22\nConversion failed!"
    window._on_task_completed(tid, False, 0, error)
    cell = window.task_table.cellWidget(0, window.task_table.COL_PROGRESS)
    assert cell.findChild(QtWidgets.QLabel, "taskDetails").text() == error.splitlines()[0]
    shown = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda box: shown.append(box.detailedText()))
    window._on_task_double_clicked(tid)
    assert shown == [error]


@pytest.mark.parametrize("codec", [VideoCodec.H264, VideoCodec.HEVC])
def test_real_start_button_converts_media_through_qthread(app_window, qtbot, media_files, ffmpeg_bin, codec):
    window = app_window
    window.ffmpeg_path = ffmpeg_bin
    window._hardware_caps_dict = {"mf": True, "mf_hevc": False} if codec == VideoCodec.HEVC else {}
    window._enqueue_media_task("video", "mp4", ConvertTaskItem(media_files["video"], str(Path(window.output_dir) / "converted.mp4"), video_config=VideoConfig(codec=codec)))
    window._start_conversion()
    qtbot.waitUntil(lambda: not window.runner_thread.isRunning(), timeout=15000)
    qtbot.waitUntil(lambda: next(iter(window.all_tasks.values()))["status"] == "completed", timeout=2000)
    assert Path(next(iter(window.all_tasks.values()))["dst"]).stat().st_size > 0


@pytest.mark.parametrize("hardware", ["nvenc", "qsv", "amf", "mf"])
def test_auto_hardware_requires_support_for_selected_codec(app_window, hardware):
    window = app_window
    window._hardware_caps_dict = {hardware: True, hardware + "_hevc": False}
    task = ConvertTaskItem("source.mp4", str(Path(window.output_dir) / "hevc.mp4"), video_config=VideoConfig(codec=VideoCodec.HEVC))
    window._enqueue_media_task("video", "mp4", task)
    assert task.video_config.hw_accel == HardwareAccel.NONE
    window._hardware_caps_dict[hardware + "_hevc"] = True
    window._enqueue_media_task("video", "mp4", task)
    assert task.video_config.hw_accel.value == hardware


def test_software_fallback_notice_is_visible_in_completed_gui_task(app_window):
    window = app_window
    task = ConvertTaskItem("source.mp4", str(Path(window.output_dir) / "out.mp4"))
    window._enqueue_media_task("video", "mp4", task)
    tid = next(iter(window.all_tasks))
    runner = ConversionRunnerThread([])
    runner.task_completed.connect(window._on_task_completed)
    warning = "HEVC hardware encoding (nvenc) failed; completed using software encoding."
    runner._on_worker_complete(tid, TaskResult(tid, task, TaskStatus.COMPLETED,
                                             output_size_bytes=100, warning_message=warning))
    assert window.all_tasks[tid]["status"] == "completed"
    cell = window.task_table.cellWidget(0, window.task_table.COL_PROGRESS)
    assert cell.findChild(QtWidgets.QLabel, "taskDetails").text() == warning
