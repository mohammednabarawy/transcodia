"""
Video and Audio Muxer Dialog.
Dialog for combining separate video, audio,
and subtitle tracks into a single container without quality loss.
"""

import os
from typing import Optional, Tuple
from PySide6 import QtCore, QtGui, QtWidgets

from transcodia_engine.models import ConvertTaskItem, VideoConfig, AudioConfig, VideoCodec, AudioCodec


class MuxDialog(QtWidgets.QDialog):
    """Multiplexer dialog combining video and audio streams."""

    def __init__(self, default_output_dir: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.output_dir = default_output_dir
        self.setWindowTitle("Mux - Combine Video & Audio Streams")
        self.resize(620, 360)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        form_box = QtWidgets.QGroupBox("Stream Sources")
        f_layout = QtWidgets.QFormLayout(form_box)
        f_layout.setSpacing(10)

        # Video File
        w_video = QtWidgets.QWidget()
        wv_layout = QtWidgets.QHBoxLayout(w_video)
        wv_layout.setContentsMargins(0, 0, 0, 0)
        self.txt_video = QtWidgets.QLineEdit()
        self.txt_video.setPlaceholderText("Select video file source...")
        btn_browse_vid = QtWidgets.QPushButton("Browse...")
        btn_browse_vid.clicked.connect(self._browse_video)
        wv_layout.addWidget(self.txt_video)
        wv_layout.addWidget(btn_browse_vid)
        f_layout.addRow("Video Stream:", w_video)

        # Audio File
        w_audio = QtWidgets.QWidget()
        wa_layout = QtWidgets.QHBoxLayout(w_audio)
        wa_layout.setContentsMargins(0, 0, 0, 0)
        self.txt_audio = QtWidgets.QLineEdit()
        self.txt_audio.setPlaceholderText("Select audio file source...")
        btn_browse_aud = QtWidgets.QPushButton("Browse...")
        btn_browse_aud.clicked.connect(self._browse_audio)
        wa_layout.addWidget(self.txt_audio)
        wa_layout.addWidget(btn_browse_aud)
        f_layout.addRow("Audio Stream:", w_audio)

        # Subtitle File (Optional)
        w_sub = QtWidgets.QWidget()
        ws_layout = QtWidgets.QHBoxLayout(w_sub)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        self.txt_sub = QtWidgets.QLineEdit()
        self.txt_sub.setPlaceholderText("(Optional) Select subtitle file (.srt, .ass)...")
        btn_browse_sub = QtWidgets.QPushButton("Browse...")
        btn_browse_sub.clicked.connect(self._browse_subtitle)
        ws_layout.addWidget(self.txt_sub)
        ws_layout.addWidget(btn_browse_sub)
        f_layout.addRow("Subtitle Track:", w_sub)

        # Output Container
        self.combo_format = QtWidgets.QComboBox()
        self.combo_format.addItems(["MP4", "MKV", "MOV", "AVI"])
        f_layout.addRow("Output Container:", self.combo_format)

        layout.addWidget(form_box)

        # Destination Box
        dst_box = QtWidgets.QGroupBox("Output Destination")
        d_layout = QtWidgets.QHBoxLayout(dst_box)
        self.txt_dst_dir = QtWidgets.QLineEdit(self.output_dir)
        btn_browse_dst = QtWidgets.QPushButton("Browse...")
        btn_browse_dst.clicked.connect(self._browse_destination)
        d_layout.addWidget(QtWidgets.QLabel("Folder:"))
        d_layout.addWidget(self.txt_dst_dir, stretch=1)
        d_layout.addWidget(btn_browse_dst)
        layout.addWidget(dst_box)

        # Buttons
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _browse_video(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Video File", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.flv *.webm);;All Files (*.*)")
        if path:
            self.txt_video.setText(path)

    def _browse_audio(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.mp3 *.aac *.wav *.flac *.m4a *.ogg);;All Files (*.*)")
        if path:
            self.txt_audio.setText(path)

    def _browse_subtitle(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Subtitle File", "", "Subtitle Files (*.srt *.ass *.ssa *.vtt);;All Files (*.*)")
        if path:
            self.txt_sub.setText(path)

    def _browse_destination(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.txt_dst_dir.text())
        if folder:
            self.txt_dst_dir.setText(folder)

    def _on_ok(self):
        if not self.txt_video.text().strip():
            QtWidgets.QMessageBox.warning(self, "Missing Video", "Please select a video file source.")
            return
        if not self.txt_audio.text().strip():
            QtWidgets.QMessageBox.warning(self, "Missing Audio", "Please select an audio file source.")
            return
        paths = [self.txt_video.text().strip(), self.txt_audio.text().strip()]
        if self.txt_sub.text().strip():
            paths.append(self.txt_sub.text().strip())
        if any(not os.path.isfile(path) for path in paths):
            QtWidgets.QMessageBox.warning(self, "Missing File", "Select existing video, audio and subtitle files.")
            return
        if not self.txt_dst_dir.text().strip():
            QtWidgets.QMessageBox.warning(self, "Output Folder", "Choose an output folder.")
            return
        self.accept()

    def get_mux_task(self) -> ConvertTaskItem:
        vid_path = self.txt_video.text().strip()
        aud_path = self.txt_audio.text().strip()
        sub_path = self.txt_sub.text().strip() or None
        fmt = self.combo_format.currentText().lower()
        dst_folder = self.txt_dst_dir.text().strip()

        base_name = os.path.splitext(os.path.basename(vid_path))[0]
        dst_path = os.path.join(dst_folder, f"{base_name}_Muxed.{fmt}")

        return ConvertTaskItem(
            src_file=vid_path,
            dst_file=dst_path,
            video_config=VideoConfig(codec=VideoCodec.COPY),
            audio_config=AudioConfig(codec=AudioCodec.COPY),
            additional_input_files=[aud_path],
            subtitle_file=sub_path,
            is_mux=True,
        )
