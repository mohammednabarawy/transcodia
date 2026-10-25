import copy
import json
from dataclasses import asdict
from pathlib import Path

import pytest
from PySide6 import QtWidgets

from transcodia_engine.models import (VideoConfig, AudioConfig, ConvertTaskItem, VideoCodec, AudioCodec,
    AspectRatio, HardwareAccel, WatermarkConfig, DelogoConfig)
from transcodia_app.views.output_settings_dialog import OutputSettingsDialog
from transcodia_app.handlers.image_handler import ImageConfig


@pytest.mark.parametrize("config", [
    VideoConfig(fps=25), VideoConfig(aspect_ratio=AspectRatio.AR_16_9), VideoConfig(transpose=2),
    VideoConfig(hflip=True), VideoConfig(vflip=True), VideoConfig(bitrate_kbps=3500, crf=18),
    VideoConfig(width=320, height=240), VideoConfig(crop=(2, 2, 100, 80)),
    VideoConfig(delogo=DelogoConfig(10, 10, 20, 20)),
])
def test_opening_settings_does_not_discard_video_choices(qapp, qtbot, config):
    dialog = OutputSettingsDialog(initial_video_config=config)
    qtbot.addWidget(dialog)
    actual = dialog.get_configuration()[0]
    for key in ("fps", "aspect_ratio", "transpose", "hflip", "vflip", "bitrate_kbps", "crop", "delogo"):
        assert getattr(actual, key) == getattr(config, key), key


def test_opening_settings_preserves_hidden_audio_and_watermark_fields(qapp, qtbot, tmp_path):
    audio = AudioConfig(echo=True, fade_out_start=1, fade_out_duration=2)
    watermark = WatermarkConfig(str(tmp_path / "logo.png"), width=80, height=30, enable_start=1, enable_end=3)
    dialog = OutputSettingsDialog(initial_audio_config=audio, initial_watermark=watermark)
    qtbot.addWidget(dialog)
    _, actual_audio, _, actual_watermark = dialog.get_configuration()
    assert actual_audio.echo and actual_audio.fade_out_duration == 2
    assert asdict(actual_watermark) == asdict(watermark)


def test_every_profile_can_be_selected_and_reset(qapp, qtbot):
    dialog = OutputSettingsDialog()
    qtbot.addWidget(dialog)
    labels = [dialog.combo_preset.itemText(i) for i in range(dialog.combo_preset.count())]
    for label in labels:
        if label == "Custom":
            continue
        dialog.combo_preset.setCurrentText(label)
        assert dialog.get_configuration()[0].codec in VideoCodec
    dialog._reset_to_default()
    assert dialog.get_configuration()[0].codec == VideoCodec.H264


def test_save_and_load_handlers_preserve_custom_destinations_for_all_categories(app_window, tmp_path, media_files, sample_image, sample_pdf, monkeypatch):
    window = app_window
    window._enqueue_media_task("video", "mp4", ConvertTaskItem(media_files["video"], str(tmp_path / "custom-video.mp4"), video_config=VideoConfig(fps=25)))
    window._enqueue_picture_task(sample_image, "jpg", ImageConfig(quality=91, flip_h=True), False, window.output_dir)
    window._enqueue_doc_task(sample_pdf, "pdf2txt", False, window.output_dir)
    window._enqueue_pdf_joiner_task([sample_pdf, sample_pdf], False, window.output_dir)
    for index, task in enumerate(window.all_tasks.values()):
        if task["category"] != "video":
            task["dst"] = str(tmp_path / f"custom-{index}{Path(task['dst']).suffix}")
    expected = [(t["category"], t["dst"]) for t in window.all_tasks.values()]
    saved = str(tmp_path / "queue.tctask")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **kw: (saved, ""))
    window._save_task_list()
    window._clear_all_tasks()
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **kw: (saved, ""))
    window._load_task_list()
    assert [(t["category"], t["dst"]) for t in window.all_tasks.values()] == expected
    assert next(t for t in window.all_tasks.values() if t["category"] == "picture")["img_config"].flip_h
    assert next(t for t in window.all_tasks.values() if t["format"] == "pdf_joiner")["additional_files"] == [sample_pdf]


def test_invalid_import_does_not_partially_modify_the_queue(app_window, tmp_path, sample_pdf, monkeypatch, messages):
    data = [{"category": "doc", "format": "pdf2txt", "src": sample_pdf, "dst": str(tmp_path / "good.txt")},
            {"category": "video", "format": "mp4", "src": sample_pdf, "dst": str(tmp_path / "bad.mp4"),
             "task_item": {"src_file": sample_pdf, "dst_file": "bad.mp4", "video_config": {"codec": "invalid-codec"}}}]
    file = tmp_path / "bad.tctask"
    file.write_text(json.dumps(data))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **kw: (str(file), ""))
    app_window._load_task_list()
    assert not app_window.all_tasks
    assert messages[-1][0] == "critical"


def test_loading_merge_never_silently_drops_a_missing_input(app_window, tmp_path, sample_pdf, monkeypatch, messages):
    file = tmp_path / "merge.tctask"
    file.write_text(json.dumps([{"category": "doc", "format": "pdf_joiner", "src": sample_pdf,
        "dst": str(tmp_path / "joined.pdf"), "additional_files": [str(tmp_path / "missing.pdf")]}]))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **kw: (str(file), ""))
    app_window._load_task_list()
    assert not app_window.all_tasks
    assert messages[-1][0] in ("critical", "warning")
