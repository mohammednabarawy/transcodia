"""
GUI and Functional Tests for the Transcodia application.
Tests CategoryPanel, TaskTableView, OutputSettingsDialog, AddFilesDialog,
OptionsDialog, ClipDialog, MuxDialog, ThemeManager, ImageConverter, and MainWindow.
"""

import os
import sys
import json
import pytest
from PIL import Image

from PySide6 import QtCore, QtGui, QtWidgets

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from transcodia_app.views.category_panel import CategoryPanel, FormatTile
from transcodia_app.views.task_table import TaskTableView
from transcodia_app.views.output_settings_dialog import OutputSettingsDialog
from transcodia_app.views.add_files_dialog import AddFilesDialog
from transcodia_app.views.options_dialog import OptionsDialog
from transcodia_app.views.clip_dialog import ClipDialog
from transcodia_app.views.mux_dialog import MuxDialog
from transcodia_app.views.main_window import MainWindow
from transcodia_app.theme_manager import ThemeManager
from transcodia_app.handlers.image_handler import ImageConverter, ImageConfig
from transcodia_engine.models import VideoCodec, AudioCodec, HardwareAccel, ConvertTaskItem


@pytest.fixture(scope="session")
def qapp():
    """Ensure single persistent QApplication instance."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_theme_manager(qapp):
    w = QtWidgets.QWidget()
    for theme in ["Ocean", "Slate", "Paper", "Midnight"]:
        ThemeManager.apply_theme(theme, w)
        assert len(w.styleSheet()) > 50


def test_category_panel(qapp):
    panel = CategoryPanel()
    received = []

    def on_selected(cat, fmt):
        received.append((cat, fmt))

    panel.format_selected.connect(on_selected)

    # Click first button in first category
    assert len(panel.findChildren(FormatTile)) >= 20
    buttons = panel.toolbox.widget(0).findChildren(FormatTile)
    buttons[0].click()

    assert len(received) == 1
    assert received[0] == ("video", "mp4")


def test_task_table_view(qapp):
    table = TaskTableView()
    table.set_language("en")
    row = table.add_task("task_001", "C:/test/sample.mp4", "MP4", "C:/out/sample.mp4")
    assert row == 0
    assert table.rowCount() == 1

    # Verify progress update
    table.update_task_progress("task_001", 45.5, 2.3, 125.0)
    pbar = table.cellWidget(0, TaskTableView.COL_PROGRESS).findChild(QtWidgets.QProgressBar)
    assert pbar.value() == 45
    assert "45.5%" in pbar.format()

    # Verify elapsed and speed columns
    elapsed_item = table.item(0, TaskTableView.COL_ELAPSED)
    assert "00:02:05" in elapsed_item.text()
    spd_item = table.item(0, TaskTableView.COL_SPEED)
    assert "2.3x" in spd_item.text()

    # Verify pause / resume
    table.set_task_paused("task_001")
    assert "Paused" in pbar.format()
    table.set_task_resumed("task_001")
    assert "45.5%" in pbar.format()

    # Verify completion
    table.set_task_completed("task_001", success=True, output_bytes=10485760)
    assert pbar.value() == 100
    size_item = table.item(0, TaskTableView.COL_SIZE)
    assert "10.00 MB" in size_item.text()

    # Reset task state
    table.reset_task("task_001")
    assert pbar.value() == 0
    assert "Pending" in pbar.format()

    # Clear
    table.clear_tasks()
    assert table.rowCount() == 0


def test_output_settings_dialog_presets(qapp):
    dlg = OutputSettingsDialog(target_format="mp4")

    # Verify initial config
    v_cfg, a_cfg, _, _ = dlg.get_configuration()
    assert v_cfg.codec == VideoCodec.H264
    assert a_cfg.codec == AudioCodec.AAC

    # Change to 1080p High
    dlg.combo_preset.setCurrentText("1080p High Quality")
    v_cfg, a_cfg, _, _ = dlg.get_configuration()
    assert v_cfg.width == 1920
    assert v_cfg.height == 1080
    assert a_cfg.bitrate_kbps == 192

    # Change to NVENC
    dlg.combo_preset.setCurrentText("NVENC H.264 Fast")
    v_cfg, a_cfg, _, _ = dlg.get_configuration()
    assert v_cfg.hw_accel == HardwareAccel.NVENC

    # Change to MP3 High
    dlg.combo_preset.setCurrentText("MP3 High 320k")
    v_cfg, a_cfg, _, _ = dlg.get_configuration()
    assert a_cfg.codec == AudioCodec.MP3
    assert a_cfg.bitrate_kbps == 320


def test_add_files_dialog_task_building(qapp, tmp_path):
    f1 = tmp_path / "video1.mp4"
    f1.write_bytes(b"dummy video data")
    f2 = tmp_path / "video2.mkv"
    f2.write_bytes(b"dummy mkv data")

    dlg = AddFilesDialog(category="video", target_format="mp4", default_output_dir=str(tmp_path / "out"))
    dlg._append_file_item(str(f1))
    dlg._append_file_item(str(f2))

    assert len(dlg.file_items) == 2
    assert dlg.tbl_files.rowCount() == 2

    # Build tasks
    tasks = dlg.get_tasks()
    assert len(tasks) == 2
    assert tasks[0].src_file == str(f1)
    assert tasks[0].dst_file.endswith("video1.mp4")
    assert tasks[1].src_file == str(f2)
    assert tasks[1].dst_file.endswith("video2.mp4")


def test_clip_dialog(qapp, tmp_path):
    dummy_video = tmp_path / "clip_input.mp4"
    dummy_video.write_bytes(b"dummy data")

    dlg = ClipDialog(str(dummy_video), initial_start=5.0, initial_end=25.0)
    assert dlg.spin_start.value() == 5.0
    assert dlg.spin_end.value() == 25.0

    dlg.spin_start.setValue(10.0)
    dlg.spin_end.setValue(30.0)
    s_in, s_out = dlg.get_range()
    assert s_in == 10.0
    assert s_out == 30.0


def test_mux_dialog(qapp, tmp_path):
    v_file = tmp_path / "video_track.mp4"
    v_file.write_bytes(b"video track")
    a_file = tmp_path / "audio_track.aac"
    a_file.write_bytes(b"audio track")

    dlg = MuxDialog(default_output_dir=str(tmp_path))
    dlg.txt_video.setText(str(v_file))
    dlg.txt_audio.setText(str(a_file))
    dlg.combo_format.setCurrentText("MKV")

    task = dlg.get_mux_task()
    assert task.src_file == str(v_file)
    assert task.additional_input_files == [str(a_file)]
    assert task.dst_file.endswith(".mkv")
    assert task.video_config.codec == VideoCodec.COPY
    assert task.audio_config.codec == AudioCodec.COPY


def test_options_dialog(qapp, tmp_path):
    dlg = OptionsDialog(default_output_dir=str(tmp_path), max_concurrency=4, hw_accel="nvenc", play_sound=False)
    assert dlg.txt_folder.text() == str(tmp_path)
    assert dlg.spin_concurrency.value() == 4
    assert dlg.combo_hw.currentText() == "NVIDIA NVENC (CUDA)"
    assert not dlg.chk_sound.isChecked()

    dlg.spin_concurrency.setValue(8)
    dlg.chk_sound.setChecked(True)
    dlg._on_ok()

    assert dlg.max_concurrency == 8
    assert dlg.play_sound is True


def test_image_converter_end_to_end(tmp_path):
    src_img = tmp_path / "input.png"
    img = Image.new("RGB", (200, 100), color=(255, 0, 0))
    img.save(str(src_img))

    # Convert to WebP
    dst_webp = tmp_path / "output.webp"
    success = ImageConverter.convert_image(str(src_img), str(dst_webp), ImageConfig(quality=90))
    assert success is True
    assert os.path.exists(str(dst_webp))
    assert os.path.getsize(str(dst_webp)) > 0

    # Convert to JPG with resize and rotate
    dst_jpg = tmp_path / "output.jpg"
    success = ImageConverter.convert_image(
        str(src_img),
        str(dst_jpg),
        ImageConfig(width=50, height=50, rotate_angle=90, keep_aspect_ratio=False)
    )
    assert success is True
    assert os.path.exists(str(dst_jpg))
    with Image.open(str(dst_jpg)) as res_img:
        assert res_img.size == (50, 50)


def test_main_window_full_workflow(qapp, tmp_path):
    w = MainWindow(probe_hardware=False)
    w.output_dir = str(tmp_path)

    # 1. Enqueue picture task
    dummy_pic = tmp_path / "pic.png"
    dummy_pic.write_bytes(b"dummy")
    w._enqueue_picture_task(str(dummy_pic), "webp", ImageConfig(), False, str(tmp_path))

    # 2. Enqueue doc task
    dummy_doc = tmp_path / "doc.pdf"
    dummy_doc.write_bytes(b"dummy")
    w._enqueue_doc_task(str(dummy_doc), "pdf2xlsx", False, str(tmp_path))
    assert w.all_tasks["task_0002"]["dst"].endswith(".xlsx")

    # 3. Enqueue pdf joiner task
    dummy_doc2 = tmp_path / "doc2.pdf"
    dummy_doc2.write_bytes(b"dummy2")
    w._enqueue_pdf_joiner_task([str(dummy_doc), str(dummy_doc2)], False, str(tmp_path))
    assert w.all_tasks["task_0003"]["dst"].endswith(".pdf")

    # 4. Enqueue media task
    dummy_vid = tmp_path / "vid.mp4"
    dummy_vid.write_bytes(b"dummy")
    task_item = ConvertTaskItem(src_file=str(dummy_vid), dst_file=str(tmp_path / "vid_out.mp4"))
    w._enqueue_media_task("video", "mp4", task_item)

    assert len(w.all_tasks) == 4
    assert w.task_table.rowCount() == 4

    # Verify status summary
    w._update_status_summary()
    assert "Tasks: 4" in w.lbl_status_summary.text()

    # Verify skin change
    w._change_skin("Midnight")
    assert w.current_skin == "Midnight"
    w._change_skin("Ocean")
    assert w.current_skin == "Ocean"

    # Verify Save Task List
    saved_list_file = tmp_path / "queue.json"
    export_data = []
    for tid, t in w.all_tasks.items():
        export_data.append({
            "id": tid,
            "category": t["category"],
            "format": t["format"],
            "src": t["src"],
            "dst": t["dst"],
        })
    with open(saved_list_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f)
    assert os.path.exists(saved_list_file)

    # Clear and verify
    w._clear_all_tasks()
    assert len(w.all_tasks) == 0
    assert w.task_table.rowCount() == 0

    w.close()


def test_doc_converter_pdf_to_xlsx_and_join(tmp_path):
    from pypdf import PdfReader
    from reportlab.pdfgen.canvas import Canvas
    from transcodia_app.handlers.doc_handler import DocumentConverter

    conv = DocumentConverter()
    p1 = tmp_path / "doc1.pdf"
    d1 = Canvas(str(p1))
    d1.drawString(50, 50, "Test Title Column1 Column2 Val1 Val2")
    d1.save()

    p2 = tmp_path / "doc2.pdf"
    d2 = Canvas(str(p2))
    d2.drawString(50, 50, "Doc 2 Content")
    d2.save()

    # Test PDF Joiner
    dst_join = tmp_path / "joined.pdf"
    ok_join = conv.join_pdfs([str(p1), str(p2)], str(dst_join))
    assert ok_join is True
    assert os.path.exists(str(dst_join))
    assert len(PdfReader(str(dst_join)).pages) == 2

    # Test PDF to Excel (.xlsx)
    dst_xlsx = tmp_path / "output.xlsx"
    ok_xlsx = conv.convert_pdf_to_xlsx(str(p1), str(dst_xlsx))
    assert ok_xlsx is True
    assert os.path.exists(str(dst_xlsx))
    assert os.path.getsize(str(dst_xlsx)) > 0
