"""
Media Information Inspector Dialog.
Built-in media file information viewer.
"""

import os
import subprocess
from PySide6 import QtCore, QtGui, QtWidgets

from transcodia_app.handlers.probe_handler import MediaProbe
from transcodia_engine.runtime_paths import find_ffmpeg


class MediaDetailsDialog(QtWidgets.QDialog):
    """Displays detailed container and codec metadata for a selected media file."""

    def __init__(self, file_path: str, ffmpeg_path=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.ffmpeg_path = ffmpeg_path or find_ffmpeg()
        self.setWindowTitle(f"Media Information - {os.path.basename(file_path)}")
        self.resize(680, 500)

        self._setup_ui()
        self._load_metadata()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        self.tabs = QtWidgets.QTabWidget()

        # Tab 1: Structured Summary
        tab_summary = QtWidgets.QWidget()
        self.form_layout = QtWidgets.QFormLayout(tab_summary)
        self.form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.form_layout.setSpacing(10)
        self.tabs.addTab(tab_summary, "Summary")

        # Tab 2: Raw FFprobe / FFmpeg Output
        tab_raw = QtWidgets.QWidget()
        raw_layout = QtWidgets.QVBoxLayout(tab_raw)
        self.txt_raw = QtWidgets.QPlainTextEdit()
        self.txt_raw.setReadOnly(True)
        self.txt_raw.setFont(QtGui.QFont("Consolas", 10))
        raw_layout.addWidget(self.txt_raw)
        self.tabs.addTab(tab_raw, "Raw FFmpeg Stream Details")

        layout.addWidget(self.tabs, stretch=1)

        # Close button
        btn_close = QtWidgets.QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

    def _load_metadata(self):
        # 1. Probed data
        probe = MediaProbe(self.ffmpeg_path)
        info = probe.probe(self.file_path)

        size_bytes = os.path.getsize(self.file_path) if os.path.exists(self.file_path) else 0
        if size_bytes >= 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB ({size_bytes:,} bytes)"
        else:
            size_str = f"{size_bytes / 1024:.1f} KB ({size_bytes:,} bytes)"

        h = int(info.duration_seconds // 3600)
        m = int((info.duration_seconds % 3600) // 60)
        s = info.duration_seconds % 60
        dur_str = f"{h:02d}:{m:02d}:{s:06.3f} ({info.duration_seconds:.2f} s)"

        self.form_layout.addRow("<b>File Name:</b>", QtWidgets.QLabel(os.path.basename(self.file_path)))
        self.form_layout.addRow("<b>Full Path:</b>", QtWidgets.QLabel(self.file_path))
        self.form_layout.addRow("<b>File Size:</b>", QtWidgets.QLabel(size_str))
        self.form_layout.addRow("<b>Duration:</b>", QtWidgets.QLabel(dur_str))

        if info.video_codec:
            res_str = f"{info.width} x {info.height}" if info.width and info.height else "Unknown"
            fps_str = f"{info.fps:.2f} fps" if info.fps else "Unknown"
            self.form_layout.addRow("<b>Video Format:</b>", QtWidgets.QLabel(info.video_codec.upper()))
            self.form_layout.addRow("<b>Resolution:</b>", QtWidgets.QLabel(res_str))
            self.form_layout.addRow("<b>Frame Rate:</b>", QtWidgets.QLabel(fps_str))

        if info.audio_codec:
            ch_str = f"{info.channels} channels (Stereo)" if info.channels == 2 else f"{info.channels} channels"
            sr_str = f"{info.sample_rate} Hz" if info.sample_rate else "Unknown"
            self.form_layout.addRow("<b>Audio Format:</b>", QtWidgets.QLabel(info.audio_codec.upper()))
            self.form_layout.addRow("<b>Channels:</b>", QtWidgets.QLabel(ch_str))
            self.form_layout.addRow("<b>Sampling Rate:</b>", QtWidgets.QLabel(sr_str))

        if info.bitrate_kbps:
            self.form_layout.addRow("<b>Overall Bitrate:</b>", QtWidgets.QLabel(f"{info.bitrate_kbps} kbps"))

        # 2. Raw execution output
        try:
            cmd = [self.ffmpeg_path, "-hide_banner", "-i", self.file_path]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=10)
            self.txt_raw.setPlainText(res.stderr)
        except Exception as e:
            self.txt_raw.setPlainText(f"Could not retrieve raw stream details: {e}")
