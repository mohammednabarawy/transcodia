"""
Output Settings Dialog.
Dialog for video/audio stream properties,
hardware acceleration selectors, bitrate/resolution controls, and watermark/subtitle styling.
"""

from typing import Optional, Tuple
from copy import deepcopy
from PySide6 import QtCore, QtGui, QtWidgets

import sys
import os

# Add parent path for imports if running standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from transcodia_engine.models import (
    VideoConfig,
    AudioConfig,
    SubtitleStyle,
    WatermarkConfig,
    VideoCodec,
    AudioCodec,
    HardwareAccel,
    AspectRatio,
)
from transcodia_engine.presets import ProfileCatalog


class OutputSettingsDialog(QtWidgets.QDialog):
    """Configuration dialog for output stream parameters and encoding options."""

    def __init__(
        self,
        target_format: str = "mp4",
        parent: Optional[QtWidgets.QWidget] = None,
        initial_video_config: Optional[VideoConfig] = None,
        initial_audio_config: Optional[AudioConfig] = None,
        initial_sub_style: Optional[SubtitleStyle] = None,
        initial_watermark: Optional[WatermarkConfig] = None,
    ):
        super().__init__(parent)
        self.target_format = target_format.lower()
        self.setWindowTitle(f"Output Setting - {self.target_format.upper()}")
        self.resize(680, 560)
        self.setModal(True)

        self._updating_from_preset = False
        self._setup_ui()
        self._load_initial_values(
            initial_video_config,
            initial_audio_config,
            initial_sub_style,
            initial_watermark,
        )

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 1. Preset Profile Header Bar
        preset_box = QtWidgets.QGroupBox("Profile Selection")
        preset_layout = QtWidgets.QHBoxLayout(preset_box)
        preset_layout.addWidget(QtWidgets.QLabel("Preset Profile:"))

        self.combo_preset = QtWidgets.QComboBox()
        self.combo_preset.addItems([
            "Optimal quality and size",
            "1080p High Quality",
            "720p Medium Quality",
            "480p Economy",
            "HEVC High Quality",
            "WebM VP9 Web Stream",
            "NVENC H.264 Fast",
            "Intel QSV H.264 Balanced",
            "AMD AMF H.264 Quality",
            "MP3 High 320k",
            "MP3 Standard 192k",
            "AAC High 256k",
            "FLAC Lossless",
            "Custom",
        ])
        self.combo_preset.currentTextChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.combo_preset, stretch=1)
        main_layout.addWidget(preset_box)

        # 2. Tab Widget for Categorized Settings
        self.tabs = QtWidgets.QTabWidget()

        # Tab 1: Video Settings
        self.tab_video = self._create_video_tab()
        self.tabs.addTab(self.tab_video, "🎥 Video Stream")

        # Tab 2: Audio Settings
        self.tab_audio = self._create_audio_tab()
        self.tabs.addTab(self.tab_audio, "🎵 Audio Stream")

        # Tab 3: Subtitles & Watermark
        self.tab_extras = self._create_extras_tab()
        self.tabs.addTab(self.tab_extras, "✨ Subtitles & Watermark")

        main_layout.addWidget(self.tabs, stretch=1)

        # 3. Action Buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Reset
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        btn_box.button(QtWidgets.QDialogButtonBox.StandardButton.Reset).clicked.connect(self._reset_to_default)
        main_layout.addWidget(btn_box)

    def _create_video_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setSpacing(10)

        # Video Codec
        self.combo_video_codec = QtWidgets.QComboBox()
        self.combo_video_codec.addItems([
            "H.264 (AVC)",
            "H.265 (HEVC)",
            "VP9",
            "MPEG-4",
            "AV1",
            "MPEG-2",
            "WMV",
            "FLV",
            "GIF",
            "Copy (No Re-encode)",
        ])
        self.combo_video_codec.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("Video Encode:", self.combo_video_codec)

        # Hardware Acceleration
        self.combo_hw_accel = QtWidgets.QComboBox()
        self.combo_hw_accel.addItems(["None (CPU)", "NVIDIA NVENC", "Intel QSV", "AMD AMF", "Windows Media Foundation"])
        self.combo_hw_accel.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("Hardware Acceleration:", self.combo_hw_accel)

        # Resolution / Size
        self.combo_resolution = QtWidgets.QComboBox()
        self.combo_resolution.addItems([
            "Original / Default",
            "3840x2160 (4K UHD)",
            "1920x1080 (1080p FHD)",
            "1280x720 (720p HD)",
            "854x480 (480p SD)",
            "640x360 (360p)",
            "Custom Resolution",
        ])
        self.combo_resolution.currentTextChanged.connect(self._on_resolution_changed)
        layout.addRow("Video Size:", self.combo_resolution)

        # Custom Size Row
        self.w_custom_size = QtWidgets.QWidget()
        cs_layout = QtWidgets.QHBoxLayout(self.w_custom_size)
        cs_layout.setContentsMargins(0, 0, 0, 0)
        cs_layout.addWidget(QtWidgets.QLabel("Width:"))
        self.spin_width = QtWidgets.QSpinBox()
        self.spin_width.setRange(16, 7680)
        self.spin_width.setValue(1920)
        self.spin_width.setSingleStep(2)
        cs_layout.addWidget(self.spin_width)
        cs_layout.addWidget(QtWidgets.QLabel("Height:"))
        self.spin_height = QtWidgets.QSpinBox()
        self.spin_height.setRange(16, 4320)
        self.spin_height.setValue(1080)
        self.spin_height.setSingleStep(2)
        cs_layout.addWidget(self.spin_height)
        self.w_custom_size.setVisible(False)
        layout.addRow("", self.w_custom_size)

        # Bitrate
        self.combo_bitrate = QtWidgets.QComboBox()
        self.combo_bitrate.addItems(["Auto / CRF Rate Control", "512 KB/s", "1000 KB/s", "1500 KB/s", "2500 KB/s", "4000 KB/s", "8000 KB/s", "12000 KB/s", "Custom"])
        self.combo_bitrate.currentTextChanged.connect(self._on_bitrate_changed)
        layout.addRow("Bitrate (KB/s):", self.combo_bitrate)

        # Custom Bitrate Spinbox
        self.spin_custom_bitrate = QtWidgets.QSpinBox()
        self.spin_custom_bitrate.setRange(64, 100000)
        self.spin_custom_bitrate.setValue(2500)
        self.spin_custom_bitrate.setSuffix(" kbps")
        self.spin_custom_bitrate.setVisible(False)
        layout.addRow("Custom Bitrate:", self.spin_custom_bitrate)

        # CRF / Constant Rate Factor
        self.spin_crf = QtWidgets.QSpinBox()
        self.spin_crf.setRange(0, 51)
        self.spin_crf.setValue(23)
        self.spin_crf.valueChanged.connect(self._mark_custom)
        layout.addRow("Quality / CRF (0-51):", self.spin_crf)

        # FPS
        self.combo_fps = QtWidgets.QComboBox()
        self.combo_fps.addItems(["Default / Keep Original", "23.976", "24", "25", "29.97", "30", "50", "60"])
        self.combo_fps.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("FPS (Frame Rate):", self.combo_fps)

        # Aspect Ratio
        self.combo_aspect = QtWidgets.QComboBox()
        self.combo_aspect.addItems(["Auto / Original", "16:9", "4:3", "3:2", "5:4"])
        self.combo_aspect.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("Aspect Ratio:", self.combo_aspect)

        # Encode Preset Speed
        self.combo_speed_preset = QtWidgets.QComboBox()
        self.combo_speed_preset.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.combo_speed_preset.setCurrentText("fast")
        self.combo_speed_preset.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("Encoding Speed:", self.combo_speed_preset)

        # Additional Video Flags
        self.chk_two_pass = QtWidgets.QCheckBox("2-Pass Encoding (Optimal bit distribution)")
        self.chk_two_pass.stateChanged.connect(self._mark_custom)
        layout.addRow("", self.chk_two_pass)

        self.chk_deinterlace = QtWidgets.QCheckBox("Deinterlace (YADIF filter for interlaced video)")
        self.chk_deinterlace.stateChanged.connect(self._mark_custom)
        layout.addRow("", self.chk_deinterlace)

        self.chk_antishake = QtWidgets.QCheckBox("Anti-shake Stabilization (Vidstab filter)")
        self.chk_antishake.stateChanged.connect(self._mark_custom)
        layout.addRow("", self.chk_antishake)

        # Rotation
        self.combo_rotation = QtWidgets.QComboBox()
        self.combo_rotation.addItems(["None", "Rotate 90° Clockwise", "Rotate 90° Counter-Clockwise", "Flip Horizontal", "Flip Vertical"])
        self.combo_rotation.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("Transform / Rotate:", self.combo_rotation)

        return widget

    def _create_audio_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setSpacing(10)

        # Audio Codec
        self.combo_audio_codec = QtWidgets.QComboBox()
        self.combo_audio_codec.addItems([
            "AAC",
            "MP3",
            "AC3",
            "OPUS",
            "FLAC",
            "Vorbis",
            "WMAv2",
            "PCM (WAV)",
            "Copy (No Re-encode)",
            "Disable Audio",
        ])
        self.combo_audio_codec.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("Audio Encode:", self.combo_audio_codec)

        # Sample Rate
        self.combo_sample_rate = QtWidgets.QComboBox()
        self.combo_sample_rate.addItems(["48000 Hz", "44100 Hz", "32000 Hz", "24000 Hz", "22050 Hz"])
        self.combo_sample_rate.setCurrentText("44100 Hz")
        self.combo_sample_rate.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("Sample Rate:", self.combo_sample_rate)

        # Audio Bitrate
        self.combo_audio_bitrate = QtWidgets.QComboBox()
        self.combo_audio_bitrate.addItems(["64 KB/s", "96 KB/s", "128 KB/s", "192 KB/s", "256 KB/s", "320 KB/s"])
        self.combo_audio_bitrate.setCurrentText("128 KB/s")
        self.combo_audio_bitrate.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("Bitrate:", self.combo_audio_bitrate)

        # Channels
        self.combo_channels = QtWidgets.QComboBox()
        self.combo_channels.addItems(["2 (Stereo)", "1 (Mono)", "6 (5.1 Surround)"])
        self.combo_channels.currentIndexChanged.connect(self._mark_custom)
        layout.addRow("Audio Channel:", self.combo_channels)

        # Volume Control
        self.spin_volume = QtWidgets.QSpinBox()
        self.spin_volume.setRange(0, 400)
        self.spin_volume.setValue(100)
        self.spin_volume.setSuffix(" %")
        self.spin_volume.valueChanged.connect(self._mark_custom)
        layout.addRow("Volume Control:", self.spin_volume)

        # Denoise / Reverse
        self.chk_audio_denoise = QtWidgets.QCheckBox("Audio Denoise Filter")
        self.chk_audio_denoise.stateChanged.connect(self._mark_custom)
        layout.addRow("", self.chk_audio_denoise)

        self.chk_audio_reverse = QtWidgets.QCheckBox("Reverse Audio Stream")
        self.chk_audio_reverse.stateChanged.connect(self._mark_custom)
        layout.addRow("", self.chk_audio_reverse)

        return widget

    def _create_extras_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(14)

        # Watermark Section
        wm_group = QtWidgets.QGroupBox("Watermark Overlay")
        wm_layout = QtWidgets.QFormLayout(wm_group)

        self.chk_watermark = QtWidgets.QCheckBox("Enable Watermark Overlay")
        self.chk_watermark.toggled.connect(self._toggle_watermark_fields)
        wm_layout.addRow(self.chk_watermark)

        self.w_wm_file = QtWidgets.QWidget()
        wmf_layout = QtWidgets.QHBoxLayout(self.w_wm_file)
        wmf_layout.setContentsMargins(0, 0, 0, 0)
        self.txt_wm_path = QtWidgets.QLineEdit()
        self.txt_wm_path.setPlaceholderText("Select image (*.png, *.jpg)...")
        btn_browse_wm = QtWidgets.QPushButton("Browse...")
        btn_browse_wm.clicked.connect(self._browse_watermark)
        wmf_layout.addWidget(self.txt_wm_path)
        wmf_layout.addWidget(btn_browse_wm)
        wm_layout.addRow("Watermark File:", self.w_wm_file)

        self.w_wm_coords = QtWidgets.QWidget()
        wmc_layout = QtWidgets.QHBoxLayout(self.w_wm_coords)
        wmc_layout.setContentsMargins(0, 0, 0, 0)
        wmc_layout.addWidget(QtWidgets.QLabel("X:"))
        self.spin_wm_x = QtWidgets.QSpinBox()
        self.spin_wm_x.setRange(0, 7680)
        self.spin_wm_x.setValue(20)
        wmc_layout.addWidget(self.spin_wm_x)
        wmc_layout.addWidget(QtWidgets.QLabel("Y:"))
        self.spin_wm_y = QtWidgets.QSpinBox()
        self.spin_wm_y.setRange(0, 4320)
        self.spin_wm_y.setValue(20)
        wmc_layout.addWidget(self.spin_wm_y)
        wm_layout.addRow("Position (px):", self.w_wm_coords)

        self._toggle_watermark_fields(False)
        layout.addWidget(wm_group)

        # Subtitles Section
        sub_group = QtWidgets.QGroupBox("Subtitle Burn-In Styling")
        sub_layout = QtWidgets.QFormLayout(sub_group)

        self.combo_sub_font = QtWidgets.QFontComboBox()
        self.combo_sub_font.setCurrentFont(QtGui.QFont("Arial"))
        sub_layout.addRow("Font Family:", self.combo_sub_font)

        self.spin_sub_size = QtWidgets.QSpinBox()
        self.spin_sub_size.setRange(8, 96)
        self.spin_sub_size.setValue(24)
        sub_layout.addRow("Font Size:", self.spin_sub_size)

        # Subtitle styling checkboxes
        sub_chk_widget = QtWidgets.QWidget()
        sub_chk_layout = QtWidgets.QHBoxLayout(sub_chk_widget)
        sub_chk_layout.setContentsMargins(0, 0, 0, 0)
        self.chk_sub_bold = QtWidgets.QCheckBox("Bold")
        self.chk_sub_italic = QtWidgets.QCheckBox("Italic")
        sub_chk_layout.addWidget(self.chk_sub_bold)
        sub_chk_layout.addWidget(self.chk_sub_italic)
        sub_chk_layout.addStretch()
        sub_layout.addRow("Style:", sub_chk_widget)

        self.spin_sub_outline = QtWidgets.QSpinBox()
        self.spin_sub_outline.setRange(0, 10)
        self.spin_sub_outline.setValue(2)
        sub_layout.addRow("Outline Width:", self.spin_sub_outline)

        layout.addWidget(sub_group)
        layout.addStretch()

        return widget

    def _mark_custom(self):
        if not self._updating_from_preset:
            self.combo_preset.setCurrentText("Custom")

    def _on_preset_changed(self, preset_name: str):
        if preset_name == "Custom" or self._updating_from_preset:
            return

        preset_key_map = {
            "Optimal quality and size": "mp4_optimal",
            "1080p High Quality": "mp4_1080p_high",
            "720p Medium Quality": "mp4_720p_medium",
            "480p Economy": "mp4_480p_economy",
            "HEVC High Quality": "hevc_high_quality",
            "WebM VP9 Web Stream": "webm_vp9",
            "NVENC H.264 Fast": "nvenc_h264_fast",
            "Intel QSV H.264 Balanced": "qsv_h264_balanced",
            "AMD AMF H.264 Quality": "amf_h264_quality",
            "MP3 High 320k": "mp3_high_320k",
            "MP3 Standard 192k": "mp3_standard_192k",
            "AAC High 256k": "aac_high_256k",
            "FLAC Lossless": "flac_lossless",
        }

        key = preset_key_map.get(preset_name)
        if not key:
            return

        self._updating_from_preset = True
        try:
            v_cfg, a_cfg = ProfileCatalog.get_preset(key)
            self._apply_video_config(v_cfg)
            self._apply_audio_config(a_cfg)
        finally:
            self._updating_from_preset = False

    def _on_resolution_changed(self, text: str):
        self.w_custom_size.setVisible(text == "Custom Resolution")
        self._mark_custom()

    def _on_bitrate_changed(self, text: str):
        self.spin_custom_bitrate.setVisible(text == "Custom")
        self._mark_custom()

    def _toggle_watermark_fields(self, enabled: bool):
        self.w_wm_file.setEnabled(enabled)
        self.w_wm_coords.setEnabled(enabled)

    def _browse_watermark(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Watermark Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*.*)",
        )
        if path:
            self.txt_wm_path.setText(path)

    def _apply_video_config(self, cfg: VideoConfig):
        self._video_template = deepcopy(cfg)
        # Codec
        codec_idx_map = {
            VideoCodec.H264: 0,
            VideoCodec.HEVC: 1,
            VideoCodec.VP9: 2,
            VideoCodec.MPEG4: 3,
            VideoCodec.AV1: 4,
            VideoCodec.MPEG2: 5,
            VideoCodec.WMV: 6,
            VideoCodec.FLV: 7,
            VideoCodec.GIF: 8,
            VideoCodec.COPY: 9,
        }
        self.combo_video_codec.setCurrentIndex(codec_idx_map.get(cfg.codec, 0))

        # HW Accel
        hw_idx_map = {
            HardwareAccel.NONE: 0,
            HardwareAccel.NVENC: 1,
            HardwareAccel.QSV: 2,
            HardwareAccel.AMF: 3,
            HardwareAccel.MEDIA_FOUNDATION: 4,
        }
        self.combo_hw_accel.setCurrentIndex(hw_idx_map.get(cfg.hw_accel, 0))

        # Resolution
        if cfg.width == 1920 and cfg.height == 1080:
            self.combo_resolution.setCurrentText("1920x1080 (1080p FHD)")
        elif cfg.width == 1280 and cfg.height == 720:
            self.combo_resolution.setCurrentText("1280x720 (720p HD)")
        elif cfg.width == 854 and cfg.height == 480:
            self.combo_resolution.setCurrentText("854x480 (480p SD)")
        elif cfg.width or cfg.height:
            self.combo_resolution.setCurrentText("Custom Resolution")
            if cfg.width:
                self.spin_width.setValue(cfg.width)
            if cfg.height:
                self.spin_height.setValue(cfg.height)
        else:
            self.combo_resolution.setCurrentText("Original / Default")

        # CRF / Bitrate
        if cfg.bitrate_kbps:
            self.spin_custom_bitrate.setValue(cfg.bitrate_kbps)
            self.combo_bitrate.setCurrentText("Custom")
        elif cfg.crf is not None:
            self.spin_crf.setValue(cfg.crf)
            self.combo_bitrate.setCurrentText("Auto / CRF Rate Control")

        # Preset
        if cfg.preset in [self.combo_speed_preset.itemText(i) for i in range(self.combo_speed_preset.count())]:
            self.combo_speed_preset.setCurrentText(cfg.preset)

        # Flags
        self.chk_two_pass.setChecked(cfg.two_pass)
        self.chk_deinterlace.setChecked(cfg.deinterlace)
        self.chk_antishake.setChecked(cfg.anti_shake)
        if cfg.fps is not None:
            value = f"{cfg.fps:g}"
            if self.combo_fps.findText(value) < 0:
                self.combo_fps.addItem(value)
            self.combo_fps.setCurrentText(value)
        else:
            self.combo_fps.setCurrentIndex(0)
        if cfg.aspect_ratio != AspectRatio.AUTO:
            self.combo_aspect.setCurrentText(cfg.aspect_ratio.value)
        else:
            self.combo_aspect.setCurrentIndex(0)
        rotation = 1 if cfg.transpose == 1 else 2 if cfg.transpose == 2 else 3 if cfg.hflip else 4 if cfg.vflip else 0
        self.combo_rotation.setCurrentIndex(rotation)
        self._initial_rotation = rotation

    def _apply_audio_config(self, cfg: AudioConfig):
        self._audio_template = deepcopy(cfg)
        codec_idx_map = {
            AudioCodec.AAC: 0,
            AudioCodec.MP3: 1,
            AudioCodec.AC3: 2,
            AudioCodec.OPUS: 3,
            AudioCodec.FLAC: 4,
            AudioCodec.VORBIS: 5,
            AudioCodec.WMA: 6,
            AudioCodec.PCM: 7,
            AudioCodec.COPY: 8,
        }
        if cfg.disable_audio:
            self.combo_audio_codec.setCurrentText("Disable Audio")
        else:
            self.combo_audio_codec.setCurrentIndex(codec_idx_map.get(cfg.codec, 0))

        self.combo_sample_rate.setCurrentText(f"{cfg.sample_rate} Hz")
        self.combo_audio_bitrate.setCurrentText(f"{cfg.bitrate_kbps} KB/s")

        if cfg.channels == 1:
            self.combo_channels.setCurrentText("1 (Mono)")
        elif cfg.channels == 6:
            self.combo_channels.setCurrentText("6 (5.1 Surround)")
        else:
            self.combo_channels.setCurrentText("2 (Stereo)")

        self.spin_volume.setValue(cfg.volume_percent)
        self.chk_audio_denoise.setChecked(cfg.denoise)
        self.chk_audio_reverse.setChecked(cfg.reverse)

    def _load_initial_values(
        self,
        v_cfg: Optional[VideoConfig],
        a_cfg: Optional[AudioConfig],
        s_style: Optional[SubtitleStyle],
        wm: Optional[WatermarkConfig],
    ):
        self._subtitle_template = deepcopy(s_style)
        self._watermark_template = deepcopy(wm or (v_cfg.watermark if v_cfg else None))
        wm = self._watermark_template
        if v_cfg:
            self._apply_video_config(v_cfg)
        if a_cfg:
            self._apply_audio_config(a_cfg)
        if s_style:
            self.combo_sub_font.setCurrentFont(QtGui.QFont(s_style.font_name))
            self.spin_sub_size.setValue(s_style.font_size)
            self.chk_sub_bold.setChecked(s_style.bold)
            self.chk_sub_italic.setChecked(s_style.italic)
            self.spin_sub_outline.setValue(s_style.outline_width)
        if wm:
            self.chk_watermark.setChecked(True)
            self.txt_wm_path.setText(wm.image_path)
            self.spin_wm_x.setValue(wm.x)
            self.spin_wm_y.setValue(wm.y)

    def _reset_to_default(self):
        self.combo_preset.setCurrentText("Optimal quality and size")

    def get_configuration(self) -> Tuple[VideoConfig, AudioConfig, Optional[SubtitleStyle], Optional[WatermarkConfig]]:
        """Constructs strongly-typed configurations from user UI selections."""
        # 1. Video Config
        v_codec_map = {
            0: VideoCodec.H264,
            1: VideoCodec.HEVC,
            2: VideoCodec.VP9,
            3: VideoCodec.MPEG4,
            4: VideoCodec.AV1,
            5: VideoCodec.MPEG2,
            6: VideoCodec.WMV,
            7: VideoCodec.FLV,
            8: VideoCodec.GIF,
            9: VideoCodec.COPY,
        }
        v_codec = v_codec_map.get(self.combo_video_codec.currentIndex(), VideoCodec.H264)

        hw_map = {
            0: HardwareAccel.NONE,
            1: HardwareAccel.NVENC,
            2: HardwareAccel.QSV,
            3: HardwareAccel.AMF,
            4: HardwareAccel.MEDIA_FOUNDATION,
        }
        hw_accel = hw_map.get(self.combo_hw_accel.currentIndex(), HardwareAccel.NONE)

        res_text = self.combo_resolution.currentText()
        width, height = None, None
        if "3840x2160" in res_text:
            width, height = 3840, 2160
        elif "1920x1080" in res_text:
            width, height = 1920, 1080
        elif "1280x720" in res_text:
            width, height = 1280, 720
        elif "854x480" in res_text:
            width, height = 854, 480
        elif "640x360" in res_text:
            width, height = 640, 360
        elif res_text == "Custom Resolution":
            width = self.spin_width.value()
            height = self.spin_height.value()

        br_text = self.combo_bitrate.currentText()
        bitrate_kbps = None
        crf = None
        if br_text == "Auto / CRF Rate Control":
            crf = self.spin_crf.value()
        elif br_text == "Custom":
            bitrate_kbps = self.spin_custom_bitrate.value()
        else:
            try:
                bitrate_kbps = int(br_text.split()[0])
            except ValueError:
                crf = 23

        fps_text = self.combo_fps.currentText()
        fps = None
        if "Default" not in fps_text:
            try:
                fps = float(fps_text)
            except ValueError:
                pass

        ar_text = self.combo_aspect.currentText()
        ar_map = {
            "16:9": AspectRatio.AR_16_9,
            "4:3": AspectRatio.AR_4_3,
            "3:2": AspectRatio.AR_3_2,
            "5:4": AspectRatio.AR_5_4,
        }
        aspect_ratio = ar_map.get(ar_text, AspectRatio.AUTO)

        rot_idx = self.combo_rotation.currentIndex()
        transpose = None
        vflip, hflip = False, False
        if rot_idx == 1:
            transpose = 1
        elif rot_idx == 2:
            transpose = 2
        elif rot_idx == 3:
            hflip = True
        elif rot_idx == 4:
            vflip = True

        v_config = VideoConfig(
            codec=v_codec,
            hw_accel=hw_accel,
            width=width,
            height=height,
            bitrate_kbps=bitrate_kbps,
            crf=crf,
            fps=fps,
            aspect_ratio=aspect_ratio,
            preset=self.combo_speed_preset.currentText(),
            two_pass=self.chk_two_pass.isChecked(),
            deinterlace=self.chk_deinterlace.isChecked(),
            anti_shake=self.chk_antishake.isChecked(),
            transpose=transpose,
            hflip=hflip,
            vflip=vflip,
        )
        template = getattr(self, "_video_template", None)
        if template:
            for key in ("crop", "delogo", "cq", "custom_aspect_ratio", "pad_color", "x264_extra_params"):
                setattr(v_config, key, deepcopy(getattr(template, key)))
            if self.combo_rotation.currentIndex() == getattr(self, "_initial_rotation", -1):
                v_config.transpose, v_config.hflip, v_config.vflip = template.transpose, template.hflip, template.vflip

        # 2. Audio Config
        a_codec_map = {
            0: AudioCodec.AAC,
            1: AudioCodec.MP3,
            2: AudioCodec.AC3,
            3: AudioCodec.OPUS,
            4: AudioCodec.FLAC,
            5: AudioCodec.VORBIS,
            6: AudioCodec.WMA,
            7: AudioCodec.PCM,
            8: AudioCodec.COPY,
        }
        disable_audio = (self.combo_audio_codec.currentText() == "Disable Audio")
        a_codec = a_codec_map.get(self.combo_audio_codec.currentIndex(), AudioCodec.AAC)

        sr_str = self.combo_sample_rate.currentText().split()[0]
        sample_rate = int(sr_str) if sr_str.isdigit() else 44100

        ab_str = self.combo_audio_bitrate.currentText().split()[0]
        a_bitrate = int(ab_str) if ab_str.isdigit() else 128

        ch_str = self.combo_channels.currentText().split()[0]
        channels = int(ch_str) if ch_str.isdigit() else 2

        a_config = AudioConfig(
            codec=a_codec,
            bitrate_kbps=a_bitrate,
            sample_rate=sample_rate,
            channels=channels,
            volume_percent=self.spin_volume.value(),
            denoise=self.chk_audio_denoise.isChecked(),
            reverse=self.chk_audio_reverse.isChecked(),
            disable_audio=disable_audio,
        )
        template = getattr(self, "_audio_template", None)
        if template:
            a_config.echo, a_config.fade_out_start, a_config.fade_out_duration = template.echo, template.fade_out_start, template.fade_out_duration

        # 3. Subtitles
        sub_style = SubtitleStyle(
            font_name=self.combo_sub_font.currentFont().family(),
            font_size=self.spin_sub_size.value(),
            bold=self.chk_sub_bold.isChecked(),
            italic=self.chk_sub_italic.isChecked(),
            outline_width=self.spin_sub_outline.value(),
        )
        if getattr(self, "_subtitle_template", None):
            for key in ("primary_color", "outline_color", "shadow_depth", "underline", "strikeout", "char_encoding"):
                setattr(sub_style, key, getattr(self._subtitle_template, key))

        # 4. Watermark
        watermark = None
        if self.chk_watermark.isChecked() and self.txt_wm_path.text().strip():
            watermark = WatermarkConfig(
                image_path=self.txt_wm_path.text().strip(),
                x=self.spin_wm_x.value(),
                y=self.spin_wm_y.value(),
            )
            if getattr(self, "_watermark_template", None):
                for key in ("width", "height", "enable_start", "enable_end"):
                    setattr(watermark, key, getattr(self._watermark_template, key))
        v_config.watermark = watermark

        return v_config, a_config, sub_style, watermark
