from pathlib import Path
import os
from types import SimpleNamespace

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

import transcodia_app.views.main_window as main_module
from transcodia_app.views.add_files_dialog import AddFilesDialog
from transcodia_app.views.category_panel import CATEGORIES, FormatTile
from transcodia_app.views.options_dialog import OptionsDialog
from transcodia_app.views.clip_dialog import ClipDialog
from transcodia_app.views.mux_dialog import MuxDialog
from transcodia_app.views.delogo_dialog import DelogoDialog
from transcodia_app.views.media_details_dialog import MediaDetailsDialog
from transcodia_app.views.output_settings_dialog import OutputSettingsDialog
from transcodia_app.views.pdf_joiner_dialog import PdfJoinerDialog
from transcodia_app.handlers.image_handler import ImageConfig


ALL_TILES = [(index, entry[0]) for index, (_, _, entries) in enumerate(CATEGORIES) for entry in entries]


@pytest.mark.parametrize("category,label", ALL_TILES)
def test_every_sidebar_tile_has_a_safe_cancel_path(app_window, qtbot, monkeypatch, category, label):
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **kw: ("", ""))
    monkeypatch.setattr(QtWidgets.QInputDialog, "getItem", lambda *a, **kw: ("", False))
    monkeypatch.setattr(QtWidgets.QDialog, "exec", lambda self: QtWidgets.QDialog.DialogCode.Rejected)
    launches = []
    monkeypatch.setattr(main_module.subprocess, "Popen", lambda *a, **kw: launches.append(a))
    app_window.show()
    app_window.category_panel.toolbox.setCurrentIndex(category)
    page = app_window.category_panel.toolbox.widget(category)
    button = next(b for b in page.findChildren(FormatTile) if b.property("sourceText") == label)
    button.click()
    assert not app_window.all_tasks
    assert not app_window.grab().isNull()


def test_file_dialog_add_remove_clear_and_save_source(qapp, qtbot, sample_image, tmp_path, messages, monkeypatch):
    dialog = AddFilesDialog("picture", "png", str(tmp_path / "out"))
    qtbot.addWidget(dialog)
    dialog._on_ok_clicked()
    assert messages[-1][0] == "warning"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **kw: ([sample_image, sample_image], ""))
    dialog._add_files()
    assert len(dialog.file_items) == 1
    dialog.chk_save_source.setChecked(True)
    assert not dialog.txt_output_dir.isEnabled()
    assert Path(dialog.get_tasks()[0].dst_file).parent == Path(sample_image).parent
    dialog.tbl_files.selectRow(0)
    dialog._remove_selected()
    assert not dialog.file_items and dialog.tbl_files.rowCount() == 0
    dialog._append_file_item(sample_image)
    dialog._clear_all()
    assert not dialog.file_items


def test_add_folder_filters_extensions_recursively(qapp, qtbot, sample_image, tmp_path, monkeypatch):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "ignored.txt").write_text("ignore")
    dialog = AddFilesDialog("picture", "webp", str(tmp_path / "out"))
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **kw: str(tmp_path))
    dialog._add_folder()
    assert [item["path"] for item in dialog.file_items] == [sample_image]


def test_invalid_range_and_missing_destination_cannot_be_accepted(qapp, qtbot, media_files, tmp_path, messages):
    dialog = AddFilesDialog("video", "mp4", str(tmp_path))
    qtbot.addWidget(dialog)
    dialog._append_file_item(media_files["video"])
    dialog.file_items[0]["start_time"] = 1.5
    dialog.file_items[0]["end_time"] = 0.5
    dialog._on_ok_clicked()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted
    dialog.file_items[0]["start_time"] = 0
    dialog.file_items[0]["end_time"] = 1
    dialog.txt_output_dir.setText("")
    dialog._on_ok_clicked()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted


def test_selected_pdfs_can_be_removed_and_empty_state_returns(qapp, qtbot, sample_pdf, tmp_path, messages):
    dialog = PdfJoinerDialog(str(tmp_path))
    qtbot.addWidget(dialog)
    dialog.add_paths([sample_pdf])
    dialog.table.selectRow(0)
    dialog.remove_selected()
    assert not dialog.paths
    assert not dialog.table.empty_button.isHidden()
    dialog._accept_files()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted
    bad = tmp_path / "invalid.pdf"
    bad.write_bytes(b"not a pdf")
    dialog.add_paths([str(bad)])
    assert not dialog.paths and messages[-1][0] == "warning"


def test_clip_marks_and_reversed_spin_edits_stay_consistent(qapp, qtbot, media_files):
    dialog = ClipDialog(media_files["video"])
    qtbot.addWidget(dialog)
    dialog.slider.setValue(50)
    dialog._mark_start()
    dialog.slider.setValue(150)
    dialog._mark_end()
    assert dialog.get_range() == (0.5, 1.5)
    dialog.spin_start.setValue(1.8)
    assert dialog.spin_end.value() >= dialog.spin_start.value()
    dialog.spin_end.setValue(0.2)
    assert dialog.spin_start.value() <= dialog.spin_end.value()


def test_delogo_outside_video_is_rejected(qapp, qtbot, media_files, tmp_path, messages):
    dialog = DelogoDialog(media_files["video"], str(tmp_path))
    qtbot.addWidget(dialog)
    dialog.spin_x.setValue(dialog.video_w - 2)
    dialog.spin_w.setValue(50)
    dialog._on_ok()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted


@pytest.mark.parametrize("position", ["Top-Right", "Top-Left", "Bottom-Right", "Bottom-Left"])
def test_delogo_presets_stay_inside_small_videos(qapp, qtbot, media_files, tmp_path, position):
    dialog = DelogoDialog(media_files["video"], str(tmp_path))
    qtbot.addWidget(dialog)
    dialog.combo_preset.setCurrentText(position)
    region = dialog.get_task().video_config.delogo
    assert region.x > 0 and region.y > 0
    assert region.x + region.width < dialog.video_w
    assert region.y + region.height < dialog.video_h


def test_mux_rejects_nonexistent_selected_paths(qapp, qtbot, tmp_path, messages):
    dialog = MuxDialog(str(tmp_path))
    qtbot.addWidget(dialog)
    dialog.txt_video.setText(str(tmp_path / "missing.mp4"))
    dialog.txt_audio.setText(str(tmp_path / "missing.wav"))
    dialog._on_ok()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted


def test_options_reject_empty_output_and_preserve_cancelled_values(qapp, qtbot, tmp_path, messages):
    dialog = OptionsDialog(str(tmp_path), max_concurrency=2, hw_accel="none")
    qtbot.addWidget(dialog)
    dialog.txt_folder.setText("")
    dialog._on_ok()
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted
    assert dialog.output_dir == str(tmp_path)


def test_media_inspector_shows_real_metadata(qapp, qtbot, ffmpeg_bin, media_files):
    dialog = MediaDetailsDialog(media_files["video"], ffmpeg_path=ffmpeg_bin)
    qtbot.addWidget(dialog)
    text = " ".join(label.text() for label in dialog.findChildren(QtWidgets.QLabel))
    text += " ".join(edit.toPlainText() for edit in dialog.findChildren(QtWidgets.QTextEdit))
    assert "160" in text and "120" in text


def test_running_jobs_cannot_be_reset_or_removed(app_window, sample_image):
    window = app_window
    window._enqueue_picture_task(sample_image, "png", ImageConfig(), False, window.output_dir)
    tid = next(iter(window.all_tasks))
    window.all_tasks[tid]["status"] = "running"
    window.task_table.selectRow(0)
    window.runner_thread = SimpleNamespace(isRunning=lambda: True)
    try:
        window._reset_selected_tasks()
        window._delete_selected_tasks()
        window._clear_all_tasks()
        assert window.all_tasks[tid]["status"] == "running"
    finally:
        window.runner_thread = None


def test_completed_output_and_sequence_open_the_right_target(app_window, sample_image, tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(main_module.QtGui.QDesktopServices, "openUrl", lambda url: opened.append(os.path.normpath(url.toLocalFile())))
    app_window._enqueue_picture_task(sample_image, "png", ImageConfig(), False, app_window.output_dir)
    task = next(iter(app_window.all_tasks.values()))
    Path(task["dst"]).write_bytes(b"result")
    task["status"] = "completed"
    app_window._on_task_double_clicked(task["id"])
    assert opened[-1] == task["dst"]
    task["dst"] = str(tmp_path / "frame_%06d.png")
    app_window._on_task_double_clicked(task["id"])
    assert opened[-1] == str(tmp_path)


def test_shutdown_never_runs_after_declined_confirmation(app_window, messages, monkeypatch):
    launched = []
    monkeypatch.setattr(main_module.subprocess, "Popen", lambda *a, **kw: launched.append(a))
    app_window.chk_shutdown.setChecked(True)
    app_window._on_batch_finished()
    assert any(kind == "question" for kind, _ in messages)
    assert launched == []
