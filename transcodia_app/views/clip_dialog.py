"""
Fast Clip and Range Selector Dialog.
Dialog for precise media trimming,
Start/End timestamp selection (Mark In / Mark Out), and crop bounds.
"""

import os
from typing import Optional, Tuple
from PySide6 import QtCore, QtGui, QtWidgets

from transcodia_app.handlers.probe_handler import MediaProbe, MediaDetails


class ClipDialog(QtWidgets.QDialog):
    """Media clipping and range selection modal dialog."""

    def __init__(
        self,
        media_file: str,
        initial_start: float = 0.0,
        initial_end: float = 0.0,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.media_file = media_file
        self.setWindowTitle(f"Fast Clip / Set Range - {os.path.basename(media_file)}")
        self.resize(640, 380)
        self.setModal(True)

        # Probe duration
        probe = MediaProbe()
        self.info = probe.probe(media_file)
        self.duration = self.info.duration_seconds if self.info.duration_seconds > 0 else 60.0

        self.start_sec = max(0.0, initial_start)
        self.end_sec = initial_end if (initial_end > 0.0 and initial_end <= self.duration) else self.duration

        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # File Summary
        summary_group = QtWidgets.QGroupBox("Media Information")
        sg_layout = QtWidgets.QFormLayout(summary_group)
        sg_layout.addRow("File:", QtWidgets.QLabel(os.path.basename(self.media_file)))
        dur_str = self._format_time(self.duration)
        res_str = f"{self.info.width}x{self.info.height}" if self.info.width else "--"
        codec_str = f"{self.info.video_codec or 'Audio only'}"
        sg_layout.addRow("Total Duration:", QtWidgets.QLabel(f"{dur_str} ({codec_str}, {res_str})"))
        layout.addWidget(summary_group)

        # Scrubber / Timeline Slider
        time_group = QtWidgets.QGroupBox("Timeline Scrubber")
        tg_layout = QtWidgets.QVBoxLayout(time_group)
        tg_layout.setSpacing(8)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(0, int(self.duration * 100))
        self.slider.setValue(int(self.start_sec * 100))
        self.slider.valueChanged.connect(self._on_slider_changed)
        tg_layout.addWidget(self.slider)

        self.lbl_current_pos = QtWidgets.QLabel(f"Current Position: {self._format_time(self.start_sec)}")
        self.lbl_current_pos.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_current_pos.setStyleSheet("font-weight: 700; color: #2563eb; font-size: 14px;")
        tg_layout.addWidget(self.lbl_current_pos)

        btn_row = QtWidgets.QHBoxLayout()
        btn_mark_in = QtWidgets.QPushButton("🚩 Set Start Time [Mark In]")
        btn_mark_in.clicked.connect(self._mark_start)
        btn_row.addWidget(btn_mark_in)

        btn_mark_out = QtWidgets.QPushButton("🏁 Set End Time [Mark Out]")
        btn_mark_out.clicked.connect(self._mark_end)
        btn_row.addWidget(btn_mark_out)

        tg_layout.addLayout(btn_row)
        layout.addWidget(time_group)

        # Range Control Inputs
        range_group = QtWidgets.QGroupBox("Clipping Range")
        rg_layout = QtWidgets.QGridLayout(range_group)

        rg_layout.addWidget(QtWidgets.QLabel("Start Time (s):"), 0, 0)
        self.spin_start = QtWidgets.QDoubleSpinBox()
        self.spin_start.setRange(0.0, self.duration)
        self.spin_start.setDecimals(3)
        self.spin_start.setSingleStep(0.5)
        self.spin_start.setValue(self.start_sec)
        self.spin_start.valueChanged.connect(self._on_spin_start_changed)
        rg_layout.addWidget(self.spin_start, 0, 1)

        rg_layout.addWidget(QtWidgets.QLabel("End Time (s):"), 0, 2)
        self.spin_end = QtWidgets.QDoubleSpinBox()
        self.spin_end.setRange(0.0, self.duration)
        self.spin_end.setDecimals(3)
        self.spin_end.setSingleStep(0.5)
        self.spin_end.setValue(self.end_sec)
        self.spin_end.valueChanged.connect(self._on_spin_end_changed)
        rg_layout.addWidget(self.spin_end, 0, 3)

        self.lbl_clipped_duration = QtWidgets.QLabel(f"Clipped Duration: {self._format_time(self.end_sec - self.start_sec)}")
        self.lbl_clipped_duration.setStyleSheet("font-weight: 600; color: #059669;")
        rg_layout.addWidget(self.lbl_clipped_duration, 1, 0, 1, 4)

        layout.addWidget(range_group)

        # Action Buttons
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _format_time(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}"

    def _on_slider_changed(self, val: int):
        cur = val / 100.0
        self.lbl_current_pos.setText(f"Current Position: {self._format_time(cur)}")

    def _mark_start(self):
        pos = self.slider.value() / 100.0
        if pos <= self.spin_end.value():
            self.spin_start.setValue(pos)

    def _mark_end(self):
        pos = self.slider.value() / 100.0
        if pos >= self.spin_start.value():
            self.spin_end.setValue(pos)

    def _on_spin_start_changed(self, val: float):
        self.start_sec = val
        if val > self.spin_end.value():
            self.spin_end.setValue(val)
        self._update_clipped_label()

    def _on_spin_end_changed(self, val: float):
        self.end_sec = val
        if val < self.spin_start.value():
            self.spin_start.setValue(val)
        self._update_clipped_label()

    def _update_clipped_label(self):
        clip_dur = max(0.0, self.spin_end.value() - self.spin_start.value())
        self.lbl_clipped_duration.setText(f"Clipped Duration: {self._format_time(clip_dur)}")

    def get_range(self) -> Tuple[float, float]:
        """Returns (start_time, end_time) in seconds."""
        return self.spin_start.value(), self.spin_end.value()
