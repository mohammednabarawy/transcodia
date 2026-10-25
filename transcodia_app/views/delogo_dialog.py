"""
Delogo Filter Configuration Dialog.
Dialog for removing logos/watermarks from videos.
"""

import os
from typing import Optional
from PySide6 import QtCore, QtGui, QtWidgets

from transcodia_engine.models import (
    ConvertTaskItem,
    VideoConfig,
    AudioConfig,
    DelogoConfig,
    VideoCodec,
    AudioCodec,
)
from transcodia_app.handlers.probe_handler import MediaProbe


class DelogoDialog(QtWidgets.QDialog):
    """Dialog for configuring the delogo filter region and output."""

    def __init__(
        self,
        media_file: str,
        default_output_dir: str,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.media_file = media_file
        self.output_dir = default_output_dir
        self.setWindowTitle(f"Delogo - Remove Logo / Watermark - {os.path.basename(media_file)}")
        self.resize(580, 420)
        self.setModal(True)

        probe = MediaProbe()
        self.info = probe.probe(media_file)
        self.video_w = self.info.width or 1920
        self.video_h = self.info.height or 1080

        self._setup_ui()
        self._on_preset_changed("Top-Right")

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Media summary
        info_box = QtWidgets.QGroupBox("Media Information")
        ib_layout = QtWidgets.QFormLayout(info_box)
        ib_layout.addRow("File:", QtWidgets.QLabel(os.path.basename(self.media_file)))
        ib_layout.addRow("Resolution:", QtWidgets.QLabel(f"{self.video_w} x {self.video_h}"))
        layout.addWidget(info_box)

        # Delogo Bounding Box
        box_delogo = QtWidgets.QGroupBox("Logo Area Coordinates (Pixels)")
        d_layout = QtWidgets.QGridLayout(box_delogo)
        d_layout.setSpacing(10)

        # Preset selector
        d_layout.addWidget(QtWidgets.QLabel("Position Preset:"), 0, 0)
        self.combo_preset = QtWidgets.QComboBox()
        self.combo_preset.addItems(["Custom", "Top-Right", "Top-Left", "Bottom-Right", "Bottom-Left"])
        self.combo_preset.currentTextChanged.connect(self._on_preset_changed)
        d_layout.addWidget(self.combo_preset, 0, 1, 1, 3)

        d_layout.addWidget(QtWidgets.QLabel("X (Left):"), 1, 0)
        self.spin_x = QtWidgets.QSpinBox()
        self.spin_x.setRange(0, self.video_w)
        self.spin_x.setValue(max(0, self.video_w - 220))
        d_layout.addWidget(self.spin_x, 1, 1)

        d_layout.addWidget(QtWidgets.QLabel("Y (Top):"), 1, 2)
        self.spin_y = QtWidgets.QSpinBox()
        self.spin_y.setRange(0, self.video_h)
        self.spin_y.setValue(20)
        d_layout.addWidget(self.spin_y, 1, 3)

        d_layout.addWidget(QtWidgets.QLabel("Width:"), 2, 0)
        self.spin_w = QtWidgets.QSpinBox()
        self.spin_w.setRange(8, self.video_w)
        self.spin_w.setValue(200)
        d_layout.addWidget(self.spin_w, 2, 1)

        d_layout.addWidget(QtWidgets.QLabel("Height:"), 2, 2)
        self.spin_h = QtWidgets.QSpinBox()
        self.spin_h.setRange(8, self.video_h)
        self.spin_h.setValue(80)
        d_layout.addWidget(self.spin_h, 2, 3)

        layout.addWidget(box_delogo)

        # Output folder
        out_box = QtWidgets.QGroupBox("Output Destination")
        ob_layout = QtWidgets.QHBoxLayout(out_box)
        self.txt_out_dir = QtWidgets.QLineEdit(self.output_dir)
        btn_browse = QtWidgets.QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_folder)
        ob_layout.addWidget(QtWidgets.QLabel("Folder:"))
        ob_layout.addWidget(self.txt_out_dir, stretch=1)
        ob_layout.addWidget(btn_browse)
        layout.addWidget(out_box)

        # Dialog Buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_preset_changed(self, text: str):
        if text == "Custom":
            return
        margin = max(1, min(20, min(self.video_w, self.video_h) // 10))
        width = min(200, self.video_w - 2 * margin)
        height = min(80, self.video_h - 2 * margin)
        self.spin_w.setValue(width)
        self.spin_h.setValue(height)
        self.spin_x.setValue(self.video_w - width - margin if "Right" in text else margin)
        self.spin_y.setValue(self.video_h - height - margin if "Bottom" in text else margin)

    def _browse_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory", self.txt_out_dir.text())
        if folder:
            self.txt_out_dir.setText(folder)

    def _on_ok(self):
        if self.spin_w.value() <= 0 or self.spin_h.value() <= 0:
            QtWidgets.QMessageBox.warning(self, "Invalid Area", "Delogo width and height must be positive.")
            return
        if (self.spin_x.value() < 1 or self.spin_y.value() < 1 or
                self.spin_x.value() + self.spin_w.value() >= self.video_w or
                self.spin_y.value() + self.spin_h.value() >= self.video_h):
            QtWidgets.QMessageBox.warning(self, "Invalid Area", "Keep the logo region inside the video, with a one-pixel border.")
            return
        if not self.txt_out_dir.text().strip():
            QtWidgets.QMessageBox.warning(self, "Output Folder", "Choose an output folder.")
            return
        self.accept()

    def get_task(self) -> ConvertTaskItem:
        base = os.path.splitext(os.path.basename(self.media_file))[0]
        dst = os.path.join(self.txt_out_dir.text().strip(), f"{base}_Delogo.mp4")

        delogo_cfg = DelogoConfig(
            x=self.spin_x.value(),
            y=self.spin_y.value(),
            width=self.spin_w.value(),
            height=self.spin_h.value(),
        )

        return ConvertTaskItem(
            src_file=self.media_file,
            dst_file=dst,
            video_config=VideoConfig(
                codec=VideoCodec.H264,
                preset="fast",
                crf=23,
                delogo=delogo_cfg,
            ),
            audio_config=AudioConfig(codec=AudioCodec.COPY),
        )
