"""
Options / Preferences Dialog.
Configures default output folder, thread concurrency, hardware acceleration priority,
and post-conversion notifications in one settings dialog.
"""

import os
from PySide6 import QtCore, QtGui, QtWidgets


class OptionsDialog(QtWidgets.QDialog):
    """Preferences and configuration dialog."""

    def __init__(
        self,
        default_output_dir: str,
        max_concurrency: int = 2,
        hw_accel: str = "auto",
        play_sound: bool = True,
        parent: QtWidgets.QWidget = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Transcodia - Options")
        self.resize(520, 360)
        self.setModal(True)

        self.output_dir = default_output_dir
        self.max_concurrency = max_concurrency
        self.hw_accel = hw_accel
        self.play_sound = play_sound

        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Tab Widget
        tabs = QtWidgets.QTabWidget()

        # Tab 1: General
        tab_gen = QtWidgets.QWidget()
        gen_layout = QtWidgets.QFormLayout(tab_gen)
        gen_layout.setSpacing(12)

        # Output Folder
        w_folder = QtWidgets.QWidget()
        wf_layout = QtWidgets.QHBoxLayout(w_folder)
        wf_layout.setContentsMargins(0, 0, 0, 0)
        self.txt_folder = QtWidgets.QLineEdit(self.output_dir)
        btn_browse = QtWidgets.QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_folder)
        wf_layout.addWidget(self.txt_folder)
        wf_layout.addWidget(btn_browse)
        gen_layout.addRow("Default Output Folder:", w_folder)

        # Max Concurrency / Threads
        self.spin_concurrency = QtWidgets.QSpinBox()
        self.spin_concurrency.setRange(1, 16)
        self.spin_concurrency.setValue(self.max_concurrency)
        self.spin_concurrency.setSuffix(" concurrent tasks")
        gen_layout.addRow("Task Concurrency:", self.spin_concurrency)

        # Sound
        self.chk_sound = QtWidgets.QCheckBox("Play sound when conversion finishes")
        self.chk_sound.setChecked(self.play_sound)
        gen_layout.addRow("", self.chk_sound)

        tabs.addTab(tab_gen, "General")

        # Tab 2: Hardware Acceleration
        tab_hw = QtWidgets.QWidget()
        hw_layout = QtWidgets.QFormLayout(tab_hw)
        hw_layout.setSpacing(12)

        self.combo_hw = QtWidgets.QComboBox()
        self.combo_hw.addItems([
            "Auto (Best Available GPU)",
            "NVIDIA NVENC (CUDA)",
            "Intel QuickSync (QSV)",
            "AMD AMF",
            "Windows Media Foundation (D3D11)",
            "Disable (CPU Only)",
        ])
        hw_map_rev = {
            "auto": 0,
            "nvenc": 1,
            "qsv": 2,
            "amf": 3,
            "mf": 4,
            "none": 5,
        }
        self.combo_hw.setCurrentIndex(hw_map_rev.get(self.hw_accel, 0))
        hw_layout.addRow("Preferred GPU Acceleration:", self.combo_hw)

        lbl_note = QtWidgets.QLabel(
            "Hardware acceleration utilizes your dedicated or integrated GPU\n"
            "for dramatically faster video encoding with reduced CPU load."
        )
        lbl_note.setStyleSheet("color: #64748b; font-size: 11px;")
        hw_layout.addRow("", lbl_note)

        tabs.addTab(tab_hw, "Hardware Acceleration")
        layout.addWidget(tabs, stretch=1)

        # Dialog Buttons
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Default Output Folder", self.txt_folder.text())
        if folder:
            self.txt_folder.setText(folder)

    def _on_ok(self):
        if not self.txt_folder.text().strip():
            QtWidgets.QMessageBox.warning(self, "Output Folder", "Choose an output folder.")
            return
        self.output_dir = self.txt_folder.text().strip()
        self.max_concurrency = self.spin_concurrency.value()
        self.play_sound = self.chk_sound.isChecked()

        idx = self.combo_hw.currentIndex()
        hw_list = ["auto", "nvenc", "qsv", "amf", "mf", "none"]
        self.hw_accel = hw_list[idx] if idx < len(hw_list) else "auto"

        self.accept()
