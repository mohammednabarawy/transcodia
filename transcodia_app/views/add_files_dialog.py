"""
Add Files Dialog.
Modal dialog for choosing the files to convert.
Supports adding multiple files, folders, setting clipping ranges (Start/End times),
configuring output folder, and launching the OutputSettingsDialog.
"""

import os
from copy import deepcopy
from typing import List, Optional, Tuple, Dict, Any
from PySide6 import QtCore, QtGui, QtWidgets

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from transcodia_engine.models import (
    VideoConfig,
    AudioConfig,
    SubtitleStyle,
    WatermarkConfig,
    MediaAdditionalConfig,
    ConvertTaskItem,
    VideoCodec,
    AudioCodec,
)
from transcodia_engine.presets import ProfileCatalog
from transcodia_app.handlers.probe_handler import MediaProbe, MediaDetails
from transcodia_app.handlers.image_handler import ImageConfig
from transcodia_app.views.output_settings_dialog import OutputSettingsDialog


class AddFilesDialog(QtWidgets.QDialog):
    """File selection and task preparation modal dialog."""

    COL_FILENAME = 0
    COL_SIZE = 1
    COL_INFO = 2
    COL_START = 3
    COL_END = 4
    COL_SOURCE_PATH = 5

    def __init__(
        self,
        category: str = "video",
        target_format: str = "mp4",
        default_output_dir: Optional[str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.category = category.lower()
        self.target_format = target_format.lower()
        self.output_dir = default_output_dir or os.path.join(os.path.expanduser("~"), "Documents", "TranscodiaOutput")
        os.makedirs(self.output_dir, exist_ok=True)

        self.setWindowTitle(f"Add Files -> {self.target_format.upper()}")
        self.resize(820, 520)
        self.setModal(True)

        self.probe = MediaProbe()
        self.file_items: List[Dict[str, Any]] = []

        # Default configs
        if self.category == "audio":
            self.video_config = None
            _, self.audio_config = ProfileCatalog.get_preset("mp3_standard_192k")
        else:
            self.video_config, self.audio_config = ProfileCatalog.get_preset("mp4_optimal")

        if self.category == "audio":
            audio_codecs = {"mp3": AudioCodec.MP3, "aac": AudioCodec.AAC, "flac": AudioCodec.FLAC,
                            "wav": AudioCodec.PCM, "wma": AudioCodec.WMA, "m4a": AudioCodec.AAC,
                            "ogg": AudioCodec.VORBIS, "ac3": AudioCodec.AC3, "m4r": AudioCodec.AAC}
            self.audio_config.codec = audio_codecs.get(self.target_format, AudioCodec.MP3)
        elif self.target_format in ("webm", "avi", "wmv", "mpg", "vob", "flv", "gif"):
            video_codecs = {"webm": VideoCodec.VP9, "avi": VideoCodec.MPEG4, "wmv": VideoCodec.WMV,
                            "mpg": VideoCodec.MPEG2, "vob": VideoCodec.MPEG2, "flv": VideoCodec.FLV, "gif": VideoCodec.GIF}
            self.video_config.codec = video_codecs[self.target_format]
            if self.target_format == "webm":
                self.audio_config.codec = AudioCodec.OPUS
                self.audio_config.sample_rate = 48000
            elif self.target_format == "gif":
                self.audio_config.disable_audio = True
            elif self.target_format in ("mpg", "vob"):
                self.audio_config.codec = AudioCodec.AC3

        self.sub_style: Optional[SubtitleStyle] = None
        self.watermark: Optional[WatermarkConfig] = None
        self.image_config = ImageConfig()

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # 1. Top Bar: Output Setting Button & Profile Label
        top_bar = QtWidgets.QFrame()
        top_bar.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px;")
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(6, 4, 6, 4)

        self.btn_output_setting = QtWidgets.QPushButton("⚙ Output Setting")
        self.btn_output_setting.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_output_setting.clicked.connect(self._open_output_setting)
        top_layout.addWidget(self.btn_output_setting)

        self.lbl_profile_summary = QtWidgets.QLabel(f"Target: {self.target_format.upper()} | Profile: Optimal Quality")
        self.lbl_profile_summary.setStyleSheet("font-weight: 600; color: #334155; margin-left: 8px;")
        top_layout.addWidget(self.lbl_profile_summary, stretch=1)

        main_layout.addWidget(top_bar)

        # 2. Center: File Table & Side Action Buttons
        center_layout = QtWidgets.QHBoxLayout()
        center_layout.setSpacing(10)

        # File List Table
        self.tbl_files = QtWidgets.QTableWidget()
        self.tbl_files.setColumnCount(6)
        self.tbl_files.setHorizontalHeaderLabels([
            "File Name",
            "File Size",
            "Media Info",
            "Start Time",
            "End Time",
            "Source Path",
        ])
        self.tbl_files.horizontalHeader().setSectionResizeMode(self.COL_FILENAME, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_files.horizontalHeader().setSectionResizeMode(self.COL_SIZE, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_files.horizontalHeader().setSectionResizeMode(self.COL_INFO, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_files.horizontalHeader().setSectionResizeMode(self.COL_START, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_files.horizontalHeader().setSectionResizeMode(self.COL_END, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_files.horizontalHeader().setSectionResizeMode(self.COL_SOURCE_PATH, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tbl_files.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_files.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_files.setAlternatingRowColors(True)
        self.tbl_files.verticalHeader().setVisible(False)
        center_layout.addWidget(self.tbl_files, stretch=1)

        # Side Action Buttons
        btn_side_layout = QtWidgets.QVBoxLayout()
        btn_side_layout.setSpacing(8)

        btn_add_file = QtWidgets.QPushButton("➕ Add File")
        btn_add_file.setMinimumWidth(110)
        btn_add_file.clicked.connect(self._add_files)
        btn_side_layout.addWidget(btn_add_file)

        btn_add_folder = QtWidgets.QPushButton("📁 Add Folder")
        btn_add_folder.clicked.connect(self._add_folder)
        btn_side_layout.addWidget(btn_add_folder)

        btn_clip = QtWidgets.QPushButton("✂ Set Range")
        btn_clip.clicked.connect(self._set_range_dialog)
        btn_side_layout.addWidget(btn_clip)

        btn_remove = QtWidgets.QPushButton("❌ Remove")
        btn_remove.clicked.connect(self._remove_selected)
        btn_side_layout.addWidget(btn_remove)

        btn_clear = QtWidgets.QPushButton("🗑 Clear All")
        btn_clear.clicked.connect(self._clear_all)
        btn_side_layout.addWidget(btn_clear)

        btn_side_layout.addStretch()
        center_layout.addLayout(btn_side_layout)

        main_layout.addLayout(center_layout, stretch=1)

        # 3. Bottom Destination Directory Picker & Controls
        dst_box = QtWidgets.QGroupBox("Output Destination")
        dst_layout = QtWidgets.QHBoxLayout(dst_box)
        dst_layout.setSpacing(8)

        self.chk_save_source = QtWidgets.QCheckBox("Save to source directory")
        self.chk_save_source.toggled.connect(self._on_save_source_toggled)
        dst_layout.addWidget(self.chk_save_source)

        dst_layout.addWidget(QtWidgets.QLabel("Folder:"))
        self.txt_output_dir = QtWidgets.QLineEdit(self.output_dir)
        dst_layout.addWidget(self.txt_output_dir, stretch=1)

        self.btn_browse_dst = QtWidgets.QPushButton("Browse...")
        self.btn_browse_dst.clicked.connect(self._browse_destination)
        dst_layout.addWidget(self.btn_browse_dst)

        main_layout.addWidget(dst_box)

        # 4. Dialog Bottom Buttons (OK / Cancel)
        bottom_box = QtWidgets.QHBoxLayout()
        self.lbl_count = QtWidgets.QLabel("Total Files: 0")
        self.lbl_count.setStyleSheet("color: #64748b; font-weight: 500;")
        bottom_box.addWidget(self.lbl_count)
        bottom_box.addStretch()

        self.btn_ok = QtWidgets.QPushButton("OK")
        self.btn_ok.setStyleSheet("background-color: #409eff; color: white; font-weight: 600; padding: 6px 20px;")
        self.btn_ok.clicked.connect(self._on_ok_clicked)
        bottom_box.addWidget(self.btn_ok)

        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bottom_box.addWidget(btn_cancel)

        main_layout.addLayout(bottom_box)

    def _open_output_setting(self):
        if self.category in ("video", "audio", "tool"):
            dlg = OutputSettingsDialog(
                target_format=self.target_format,
                parent=self,
                initial_video_config=self.video_config,
                initial_audio_config=self.audio_config,
                initial_sub_style=self.sub_style,
                initial_watermark=self.watermark,
            )
            if dlg.exec():
                self.video_config, self.audio_config, self.sub_style, self.watermark = dlg.get_configuration()
                v_desc = f"{self.video_config.codec.value.upper()}" if self.video_config else "None"
                a_desc = f"{self.audio_config.codec.value.upper()}" if self.audio_config else "None"
                self.lbl_profile_summary.setText(f"Target: {self.target_format.upper()} | V: {v_desc} | A: {a_desc}")
        elif self.category == "picture":
            # Image settings prompt (Quality / Resize)
            qual, ok = QtWidgets.QInputDialog.getInt(self, "Picture Output Quality", "Quality (1-100):", self.image_config.quality, 1, 100)
            if ok:
                self.image_config.quality = qual
                self.lbl_profile_summary.setText(f"Target: {self.target_format.upper()} | Quality: {qual}%")

    def _add_files(self):
        filters = "All Files (*.*)"
        if self.category == "video":
            filters = "Video Files (*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.webm *.m4v *.ts *.mpg *.mpeg);;All Files (*.*)"
        elif self.category == "audio":
            filters = "Audio Files (*.mp3 *.aac *.wav *.flac *.wma *.ogg *.m4a *.opus);;All Files (*.*)"
        elif self.category == "picture":
            filters = "Image Files (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.ico *.tiff);;All Files (*.*)"
        elif self.category in ("doc", "document"):
            filters = "Document Files (*.pdf *.docx *.doc *.xlsx *.xls *.txt *.md *.epub);;All Files (*.*)"

        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Files to Convert", "", filters)
        for p in paths:
            self._append_file_item(p)

    def _add_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder to Add")
        if not folder:
            return

        valid_exts = set()
        if self.category == "video":
            valid_exts = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v", ".ts", ".mpg"}
        elif self.category == "audio":
            valid_exts = {".mp3", ".aac", ".wav", ".flac", ".wma", ".ogg", ".m4a", ".opus"}
        elif self.category == "picture":
            valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".ico", ".tiff"}
        elif self.category == "doc":
            valid_exts = {".pdf", ".docx", ".doc", ".txt", ".md"}

        for root, _, files in os.walk(folder):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if not valid_exts or ext in valid_exts:
                    self._append_file_item(os.path.join(root, f))

    def _append_file_item(self, path: str):
        if not os.path.isfile(path):
            return

        # Check duplicate
        for item in self.file_items:
            if item["path"] == path:
                return

        size_bytes = os.path.getsize(path)
        if size_bytes >= 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            size_str = f"{size_bytes / 1024:.1f} KB"

        # Media probe info
        info_str = "--"
        duration_sec = 0.0
        if self.category in ("video", "audio", "tool"):
            media_info = self.probe.probe(path)
            duration_sec = media_info.duration_seconds
            parts = []
            if duration_sec > 0:
                h = int(duration_sec // 3600)
                m = int((duration_sec % 3600) // 60)
                s = int(duration_sec % 60)
                parts.append(f"{h:02d}:{m:02d}:{s:02d}")
            if media_info.width and media_info.height:
                parts.append(f"{media_info.width}x{media_info.height}")
            if media_info.video_codec:
                parts.append(media_info.video_codec)
            if parts:
                info_str = " | ".join(parts)

        item_data = {
            "path": path,
            "filename": os.path.basename(path),
            "size_str": size_str,
            "info_str": info_str,
            "duration": duration_sec,
            "start_time": 0.0,
            "end_time": duration_sec,
        }
        self.file_items.append(item_data)

        # Add to QTableWidget
        row = self.tbl_files.rowCount()
        self.tbl_files.insertRow(row)
        self.tbl_files.setItem(row, self.COL_FILENAME, QtWidgets.QTableWidgetItem(item_data["filename"]))
        self.tbl_files.setItem(row, self.COL_SIZE, QtWidgets.QTableWidgetItem(size_str))
        self.tbl_files.setItem(row, self.COL_INFO, QtWidgets.QTableWidgetItem(info_str))
        self.tbl_files.setItem(row, self.COL_START, QtWidgets.QTableWidgetItem("00:00:00"))
        end_time_str = self._format_seconds(duration_sec) if duration_sec > 0 else "End"
        self.tbl_files.setItem(row, self.COL_END, QtWidgets.QTableWidgetItem(end_time_str))
        self.tbl_files.setItem(row, self.COL_SOURCE_PATH, QtWidgets.QTableWidgetItem(path))

        self.lbl_count.setText(f"Total Files: {len(self.file_items)}")

    def _format_seconds(self, sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _set_range_dialog(self):
        row = self.tbl_files.currentRow()
        if row < 0 or row >= len(self.file_items):
            QtWidgets.QMessageBox.information(self, "Set Range", "Please select a file to set range.")
            return

        item = self.file_items[row]
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Set Range - {item['filename']}")
        dlg.resize(320, 160)
        l = QtWidgets.QFormLayout(dlg)

        spin_start = QtWidgets.QDoubleSpinBox()
        spin_start.setRange(0, 999999)
        spin_start.setValue(item["start_time"])
        spin_start.setSuffix(" sec")
        l.addRow("Start Time:", spin_start)

        spin_end = QtWidgets.QDoubleSpinBox()
        spin_end.setRange(0, 999999)
        spin_end.setValue(item["end_time"])
        spin_end.setSuffix(" sec")
        l.addRow("End Time (0=End):", spin_end)

        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        l.addRow(bb)

        if dlg.exec():
            item["start_time"] = spin_start.value()
            item["end_time"] = spin_end.value()
            self.tbl_files.setItem(row, self.COL_START, QtWidgets.QTableWidgetItem(self._format_seconds(item["start_time"])))
            self.tbl_files.setItem(row, self.COL_END, QtWidgets.QTableWidgetItem(self._format_seconds(item["end_time"])))

    def _remove_selected(self):
        selected_rows = sorted(set(idx.row() for idx in self.tbl_files.selectedIndexes()), reverse=True)
        for r in selected_rows:
            self.tbl_files.removeRow(r)
            if r < len(self.file_items):
                del self.file_items[r]
        self.lbl_count.setText(f"Total Files: {len(self.file_items)}")

    def _clear_all(self):
        self.tbl_files.setRowCount(0)
        self.file_items.clear()
        self.lbl_count.setText("Total Files: 0")

    def _on_save_source_toggled(self, checked: bool):
        self.txt_output_dir.setEnabled(not checked)
        self.btn_browse_dst.setEnabled(not checked)

    def _browse_destination(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Destination Folder", self.txt_output_dir.text())
        if folder:
            self.txt_output_dir.setText(folder)

    def _on_ok_clicked(self):
        if not self.file_items:
            QtWidgets.QMessageBox.warning(self, "No Files Added", "Please add at least one file to convert.")
            return
        if not self.chk_save_source.isChecked() and not self.txt_output_dir.text().strip():
            QtWidgets.QMessageBox.warning(self, "Output Folder", "Choose an output folder.")
            return
        for item in self.file_items:
            if not os.path.isfile(item["path"]):
                QtWidgets.QMessageBox.warning(self, "Missing File", "An input file is no longer available.")
                return
            start, end, duration = item["start_time"], item["end_time"], item["duration"]
            if start < 0 or (end > 0 and end <= start) or (duration > 0 and start >= duration):
                QtWidgets.QMessageBox.warning(self, "Invalid Range", "The end must follow the start and the range must be within the source.")
                return
        self.accept()

    def get_tasks(self) -> List[ConvertTaskItem]:
        """Builds strong ConvertTaskItem representations ready to enqueue."""
        tasks = []
        is_save_source = self.chk_save_source.isChecked()
        dst_dir = self.txt_output_dir.text().strip()

        # Handle tool: Joiner (all files combined into single target output)
        if self.target_format in ("video_joiner", "audio_joiner", "pdf_joiner"):
            if not self.file_items:
                return []
            first_path = self.file_items[0]["path"]
            out_folder = os.path.dirname(first_path) if is_save_source else dst_dir
            if self.target_format == "pdf_joiner":
                ext = ".pdf"
            elif self.target_format == "video_joiner":
                ext = ".mp4"
            else:
                ext = ".mp3"
            dst_name = "Joined_" + os.path.splitext(os.path.basename(first_path))[0] + ext
            out_path = os.path.join(out_folder, dst_name)

            all_inputs = [item["path"] for item in self.file_items]
            is_audio_only = (self.target_format == "audio_joiner")
            task = ConvertTaskItem(
                src_file=all_inputs[0],
                dst_file=out_path,
                video_config=None if is_audio_only else self.video_config,
                audio_config=self.audio_config,
                additional_input_files=all_inputs[1:],
                disable_video=is_audio_only,
                is_concat=(self.target_format in ("video_joiner", "audio_joiner")),
            )
            tasks.append(task)
            return tasks

        ext_map = {
            "pdf2docx": "docx",
            "docx2pdf": "pdf",
            "pdf2xlsx": "xlsx",
            "pdf2txt": "txt",
            "pdf2html": "html",
            "markitdown": "md",
        }
        out_ext = ext_map.get(self.target_format, self.target_format)

        for item in self.file_items:
            src = item["path"]
            base_name = os.path.splitext(os.path.basename(src))[0]
            out_folder = os.path.dirname(src) if is_save_source else dst_dir
            out_path = os.path.join(out_folder, f"{base_name}.{out_ext}")

            add_cfg = None
            if item["start_time"] > 0 or (item["end_time"] > 0 and item["end_time"] < item["duration"]):
                add_cfg = MediaAdditionalConfig(
                    start_time=item["start_time"],
                    end_time=item["end_time"],
                )

            task = ConvertTaskItem(
                src_file=src,
                dst_file=out_path,
                video_config=deepcopy(self.video_config),
                audio_config=deepcopy(self.audio_config),
                additional_config=add_cfg,
                subtitle_style=deepcopy(self.sub_style),
                disable_video=self.category == "audio",
                output_arguments=["-f", "ipod"] if self.target_format == "m4r" else [],
            )
            if self.watermark:
                if task.video_config:
                    task.video_config.watermark = deepcopy(self.watermark)
            tasks.append(task)

        return tasks
