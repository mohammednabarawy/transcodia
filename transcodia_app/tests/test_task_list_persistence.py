import os
import json
import tempfile
import pytest
from PySide6 import QtWidgets

from transcodia_app.views.main_window import MainWindow
from transcodia_app.handlers.image_handler import ImageConfig
from transcodia_engine.models import (
    ConvertTaskItem,
    VideoConfig,
    AudioConfig,
    VideoCodec,
    AudioCodec,
    HardwareAccel,
)


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_main_window_task_save_load_lossless(qapp, tmp_path):
    win = MainWindow(probe_hardware=False)

    # 1. Add media task with rich config
    dummy_src = str(tmp_path / "dummy_video.mp4")
    with open(dummy_src, "wb") as f:
        f.write(b"0" * 1024)

    task_item = ConvertTaskItem(
        src_file=dummy_src,
        dst_file=str(tmp_path / "converted.mkv"),
        video_config=VideoConfig(codec=VideoCodec.HEVC, bitrate_kbps=3500, crf=18),
        audio_config=AudioConfig(codec=AudioCodec.FLAC),
        is_concat=False,
    )
    win._enqueue_media_task("video", "mkv", task_item)

    # 2. Add picture task
    dummy_pic = str(tmp_path / "dummy_pic.jpg")
    with open(dummy_pic, "wb") as f:
        f.write(b"0" * 512)
    img_cfg = ImageConfig(quality=92, rotate_angle=90)
    win._enqueue_picture_task(dummy_pic, "png", img_cfg, False, str(tmp_path))

    # 3. Add doc task
    dummy_doc = str(tmp_path / "sample.pdf")
    with open(dummy_doc, "wb") as f:
        f.write(b"%PDF-1.4\n")
    win._enqueue_doc_task(dummy_doc, "pdf2docx", False, str(tmp_path))

    assert len(win.all_tasks) == 3

    # Export to json file directly using internal serialization
    save_file = str(tmp_path / "test_tasks.json")
    export_data = []
    for tid, t in win.all_tasks.items():
        cat = t.get("category", "video")
        entry = {
            "id": tid,
            "category": cat,
            "format": t["format"],
            "src": t["src"],
            "dst": t["dst"],
        }
        if "task_item" in t and t["task_item"]:
            entry["task_item"] = t["task_item"].to_dict()
        elif cat == "picture" and "img_config" in t:
            cfg = t["img_config"]
            entry["img_config"] = {
                "width": getattr(cfg, "width", None),
                "height": getattr(cfg, "height", None),
                "quality": getattr(cfg, "quality", 85),
                "keep_aspect_ratio": getattr(cfg, "keep_aspect_ratio", True),
                "rotate_angle": getattr(cfg, "rotate_angle", 0),
                "flip_h": getattr(cfg, "flip_h", False),
                "flip_v": getattr(cfg, "flip_v", False),
            }
        export_data.append(entry)

    with open(save_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f)

    # Clear tasks
    win._clear_all_tasks()
    assert len(win.all_tasks) == 0

    # Load tasks back from save_file
    with open(save_file, "r", encoding="utf-8") as f:
        import_data = json.load(f)

    for item in import_data:
        cat = item.get("category", "video")
        fmt = item.get("format", "mp4")
        src = item["src"]
        dst = item["dst"]
        if "task_item" in item and item["task_item"]:
            t_item = ConvertTaskItem.from_dict(item["task_item"])
            win._enqueue_media_task(cat, fmt, t_item)
        elif cat == "picture":
            c = item.get("img_config", {})
            cfg = ImageConfig(**c)
            win._enqueue_picture_task(src, fmt, cfg, False, os.path.dirname(dst))
        elif cat == "doc":
            win._enqueue_doc_task(src, fmt, False, os.path.dirname(dst))

    assert len(win.all_tasks) == 3

    # Verify restored attributes
    tasks_list = list(win.all_tasks.values())
    media_task = next(t for t in tasks_list if t["category"] == "video")
    assert media_task["task_item"].video_config.codec == VideoCodec.HEVC
    assert media_task["task_item"].video_config.bitrate_kbps == 3500
    assert media_task["task_item"].audio_config.codec == AudioCodec.FLAC

    pic_task = next(t for t in tasks_list if t["category"] == "picture")
    assert pic_task["img_config"].quality == 92
    assert pic_task["img_config"].rotate_angle == 90


def test_main_window_gpu_preference_propagation(qapp, tmp_path):
    win = MainWindow(probe_hardware=False)
    win.preferred_hw = "nvenc"

    dummy_src = str(tmp_path / "sample_video.mp4")
    with open(dummy_src, "wb") as f:
        f.write(b"0" * 1024)

    task_item = ConvertTaskItem(
        src_file=dummy_src,
        dst_file=str(tmp_path / "sample_out.mp4"),
        video_config=VideoConfig(codec=VideoCodec.H264, hw_accel=HardwareAccel.NONE),
    )
    win._enqueue_media_task("video", "mp4", task_item)

    enqueued = list(win.all_tasks.values())[0]["task_item"]
    assert enqueued.video_config.hw_accel == HardwareAccel.NVENC
