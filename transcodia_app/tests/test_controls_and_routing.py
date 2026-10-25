import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

import transcodia_app.views.main_window as main_module
from transcodia_app.handlers.image_handler import ImageConfig
from transcodia_app.views.add_files_dialog import AddFilesDialog
from transcodia_app.views.pdf_joiner_dialog import PdfJoinerDialog
from transcodia_app.views.options_dialog import OptionsDialog
from transcodia_app.views.output_settings_dialog import OutputSettingsDialog
from transcodia_app.views.clip_dialog import ClipDialog
from transcodia_app.views.delogo_dialog import DelogoDialog
from transcodia_engine.models import VideoConfig, AudioConfig


@pytest.mark.parametrize("category,format_name", [("video", "mp4"), ("audio", "mp3"), ("picture", "png"), ("doc", "pdf2txt")])
def test_accepting_standard_dialog_queues_the_correct_job(app_window, sample_image, sample_pdf, media_files, monkeypatch, category, format_name):
    source = sample_image if category == "picture" else sample_pdf if category == "doc" else media_files["video"]
    def accept(dialog):
        dialog._append_file_item(source)
        return QtWidgets.QDialog.DialogCode.Accepted
    monkeypatch.setattr(AddFilesDialog, "exec", accept)
    app_window._on_format_tile_clicked(category, format_name)
    task = next(iter(app_window.all_tasks.values()))
    assert task["category"] == category and task["format"] == format_name
    assert task["src"] == source


def test_accepting_pdf_dialog_queues_one_ordered_merge(app_window, sample_pdf, monkeypatch):
    def accept(dialog):
        dialog.add_paths([sample_pdf])
        dialog.chk_append_name.setChecked(True)
        return QtWidgets.QDialog.DialogCode.Accepted
    monkeypatch.setattr(PdfJoinerDialog, "exec", accept)
    app_window._on_format_tile_clicked("doc", "pdf_joiner")
    assert len(app_window.all_tasks) == 1
    task = next(iter(app_window.all_tasks.values()))
    assert task["format"] == "pdf_joiner" and "_PDF Joiner" in task["dst"]


@pytest.mark.parametrize("name", ["frames", "split"])
def test_utility_dialog_routes_keep_the_requested_output_pattern(app_window, media_files, monkeypatch, name):
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **kw: (media_files["video"], ""))
    monkeypatch.setattr(QtWidgets.QInputDialog, "getDouble", lambda *a, **kw: (2.0, True))
    monkeypatch.setattr(QtWidgets.QInputDialog, "getInt", lambda *a, **kw: (1, True))
    app_window._open_media_utility(name)
    task = next(iter(app_window.all_tasks.values()))
    assert "%" in task["dst"] and task["task_item"].output_arguments


@pytest.mark.parametrize("name,dialog_type", [("clip", ClipDialog), ("delogo", DelogoDialog)])
def test_specialized_video_dialogs_queue_a_media_task(app_window, media_files, monkeypatch, name, dialog_type):
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **kw: (media_files["video"], ""))
    monkeypatch.setattr(dialog_type, "exec", lambda self: QtWidgets.QDialog.DialogCode.Accepted)
    app_window._on_format_tile_clicked("tool", name)
    assert len(app_window.all_tasks) == 1
    assert next(iter(app_window.all_tasks.values()))["task_item"]


def test_options_apply_to_window_and_folder_picker(app_window, tmp_path, monkeypatch):
    folder = str(tmp_path / "changed")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **kw: folder)
    app_window._change_output_folder()
    assert app_window.output_dir == folder
    def accept(dialog):
        dialog.txt_folder.setText(folder)
        dialog.spin_concurrency.setValue(3)
        dialog.combo_hw.setCurrentIndex(5)
        dialog.chk_sound.setChecked(False)
        dialog._on_ok()
        return dialog.result()
    monkeypatch.setattr(OptionsDialog, "exec", accept)
    app_window._open_options()
    assert app_window.max_concurrency == 3 and app_window.preferred_hw == "none"


def test_pause_resume_actions_control_the_active_runner(app_window, sample_image):
    window = app_window
    window._enqueue_picture_task(sample_image, "png", ImageConfig(), False, window.output_dir)
    tid = next(iter(window.all_tasks))
    window.all_tasks[tid]["status"] = "running"
    paused = [False]
    runner = SimpleNamespace(isRunning=lambda: True, is_paused=lambda: paused[0],
        pause=lambda: paused.__setitem__(0, True), resume=lambda: paused.__setitem__(0, False))
    window.runner_thread = runner
    try:
        window._pause_conversion()
        assert paused[0] and "Paused" in window.task_table._progress_bars[tid].format()
        window._start_conversion()
        assert not paused[0]
    finally:
        window.runner_thread = None


@pytest.mark.parametrize("index", [0, 1, 2, 3, 5, 6, 8])
def test_task_context_menu_actions_do_not_crash_or_launch_real_apps(app_window, sample_image, monkeypatch, index):
    window = app_window
    window._enqueue_picture_task(sample_image, "png", ImageConfig(), False, window.output_dir)
    window.task_table.selectRow(0)
    original_menu = QtWidgets.QMenu
    def create_menu(parent):
        menu = original_menu(parent)
        menu.exec = lambda *args: menu.actions()[index]
        return menu
    monkeypatch.setattr(QtWidgets, "QMenu", create_menu)
    monkeypatch.setattr(QtWidgets.QDialog, "exec", lambda self: QtWidgets.QDialog.DialogCode.Rejected)
    opened = []
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    window._show_table_context_menu(QtCore.QPoint(0, 0))


def test_open_output_folder_uses_platform_file_handler(app_window, monkeypatch):
    opened = []
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    app_window._open_output_folder()
    assert os.path.normpath(opened[0]) == os.path.normpath(app_window.output_dir)


def test_style_and_language_changes_keep_task_identity(app_window, sample_image):
    window = app_window
    window._enqueue_picture_task(sample_image, "jpg", ImageConfig(), False, window.output_dir)
    identities = set(window.all_tasks)
    for theme in ("Transcodia Light", "Ocean", "Slate", "Paper", "Midnight"):
        window._change_skin(theme)
        window._change_language("en")
        window._change_language("ar")
        assert set(window.all_tasks) == identities
    window.category_panel.toolbox.setCurrentIndex(3)
    window._show_home()
    assert window.category_panel.toolbox.currentIndex() == 0


def test_new_tasks_do_not_share_mutable_encoding_settings(qapp, qtbot, media_files, tmp_path):
    dialog = AddFilesDialog("video", "mp4", str(tmp_path))
    qtbot.addWidget(dialog)
    dialog._append_file_item(media_files["video"])
    dialog._append_file_item(media_files["silent"])
    tasks = dialog.get_tasks()
    tasks[0].video_config.width = 80
    tasks[0].audio_config.volume_percent = 50
    assert tasks[1].video_config.width is None
    assert tasks[1].audio_config.volume_percent == 100


def test_setting_dialog_accept_and_cancel_do_not_lose_current_profile(qapp, qtbot, tmp_path, monkeypatch):
    dialog = AddFilesDialog("video", "mp4", str(tmp_path))
    qtbot.addWidget(dialog)
    monkeypatch.setattr(OutputSettingsDialog, "exec", lambda self: QtWidgets.QDialog.DialogCode.Rejected)
    original = dialog.video_config
    dialog._open_output_setting()
    assert dialog.video_config is original
    def accept(settings):
        settings.combo_preset.setCurrentText("1080p High Quality")
        return QtWidgets.QDialog.DialogCode.Accepted
    monkeypatch.setattr(OutputSettingsDialog, "exec", accept)
    dialog._open_output_setting()
    assert dialog.video_config.width == 1920


def test_application_entry_point_starts_and_exits_cleanly():
    script = """
from PySide6 import QtCore, QtWidgets
import transcodia_app.main as entry
original_window = entry.MainWindow
entry.MainWindow = lambda: original_window(probe_hardware=False)
original_exec = QtWidgets.QApplication.exec
def bounded_exec():
    QtCore.QTimer.singleShot(100, QtWidgets.QApplication.instance().quit)
    return original_exec()
QtWidgets.QApplication.exec = staticmethod(bounded_exec)
assert entry.main() == 0
print('startup-ok')
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert b"startup-ok" in result.stdout
