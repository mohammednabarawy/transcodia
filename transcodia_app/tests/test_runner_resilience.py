from pathlib import Path

from PySide6 import QtWidgets

from transcodia_app.handlers.image_handler import ImageConfig
from transcodia_app.views.main_window import ConversionRunnerThread
from transcodia_engine.models import ConvertTaskItem


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
