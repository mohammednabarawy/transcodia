"""Transcodia's shared palette, spacing and interaction styles."""

_STYLE = """
QWidget { font-family: "Segoe UI", "Noto Sans", sans-serif; font-size: 13px; color: @text; }
QMainWindow, QDialog { background: @background; }
QMenuBar { background: @surface; padding: 5px 18px; border: none; }
QMenuBar::item { padding: 5px 10px; border-radius: 5px; }
QMenuBar::item:selected, QMenu::item:selected { background: @hover; }
QMenu { background: @surface; border: 1px solid @border; padding: 6px; }
QMenu::item { padding: 7px 28px; }
QToolBar { background: @surface; border: none; spacing: 8px; padding: 6px; }
QToolBar::separator { width: 1px; background: @border; margin: 8px; }
QToolButton, QPushButton { background: @surface; border: 1px solid @border; border-radius: 9px; padding: 8px 12px; }
QToolButton:hover, QPushButton:hover { background: @hover; border-color: @accent; }
QToolButton:disabled, QPushButton:disabled { color: @muted; border-color: @border; background: @background; }
QToolButton#startConversion { background: @accent; color: white; border: none; padding: 9px 22px; font-weight: 600; }
QToolButton#startConversion:disabled { background: @border; color: @muted; }
QFrame#brandHeader { background: @surface; border-bottom: 1px solid @border; }
QLabel#brandTitle { font-size: 27px; font-weight: 700; }
QLabel#brandSubtitle, QLabel#sectionHint { color: @muted; }
QLabel#sectionTitle { font-size: 20px; font-weight: 650; }
QFrame#navigationRail { background: @nav; border: none; border-radius: 16px; }
QToolButton[class="category-header"] { border: none; background: transparent; padding: 8px; border-radius: 12px; }
QToolButton[class="category-header"]:checked { background: @hover; border: 1px solid @accent; }
QWidget#categoryPage, QWidget#categoryViewport { background: transparent; }
QPushButton[class="format-tile"] { background: @surface; border: 1px solid @border; border-radius: 12px; padding: 0; font-size: 12px; }
QPushButton[class="format-tile"]:hover { background: @hover; border-color: @accent; }
QPushButton[class="format-tile"]:focus { border: 2px solid @accent; }
QFrame#queueSurface { background: @surface; border: 1px solid @border; border-radius: 16px; }
QTableWidget { background: @surface; alternate-background-color: @surface; border: none; selection-background-color: @hover; selection-color: @text; }
QHeaderView::section { background: @surface; color: @muted; border: none; border-bottom: 1px solid @border; padding: 12px 8px; font-weight: 600; }
QProgressBar { background: @background; border: none; border-radius: 6px; min-height: 16px; text-align: center; }
QProgressBar::chunk { background: @accent; border-radius: 6px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit { background: @surface; border: 1px solid @border; border-radius: 7px; padding: 6px; min-height: 22px; }
QLineEdit:focus, QComboBox:focus { border-color: @accent; }
QGroupBox { border: 1px solid @border; border-radius: 10px; margin-top: 16px; padding: 16px 10px 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; font-weight: 600; }
QTabWidget::pane { background: @surface; border: 1px solid @border; border-radius: 10px; }
QTabBar::tab { padding: 9px 15px; background: @background; border: none; }
QTabBar::tab:selected { background: @surface; color: @accent; }
QFrame#workspaceFooter { background: @surface; border-top: 1px solid @border; }
QFrame#workspaceFooter QLineEdit { border: none; background: transparent; color: @muted; }
QCheckBox { spacing: 6px; }
QSplitter::handle { background: transparent; width: 14px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: @border; border-radius: 4px; min-height: 30px; }
"""


def _palette(background, surface, text, muted, border, accent, hover, nav):
    result = _STYLE
    for name, value in locals().copy().items():
        if name != "result":
            result = result.replace("@" + name, value)
    return result


class ThemeManager:
    THEMES = {
        "Transcodia Light": _palette("#f2f6fb", "#ffffff", "#172d49", "#6b7d92", "#dce5ef", "#126bce", "#e8f4ff", "#e3edf8"),
        "Ocean": _palette("#eef8f8", "#ffffff", "#153c49", "#5f7e87", "#d1e5e7", "#087e91", "#e0f4f4", "#daeff0"),
        "Slate": _palette("#eef0f5", "#ffffff", "#26344e", "#738099", "#d9deea", "#5b62bc", "#edf0ff", "#e2e5f2"),
        "Paper": _palette("#f6f4ef", "#fffefa", "#3f3a32", "#898171", "#e5dfd3", "#936b2e", "#f5ecd9", "#ede7dc"),
        "Midnight": _palette("#111d2d", "#192a3f", "#e5effb", "#94abc4", "#2b415c", "#3998f5", "#263e5b", "#142438"),
    }

    @classmethod
    def apply_theme(cls, theme_name, app_or_widget):
        app_or_widget.setStyleSheet(cls.THEMES.get(theme_name, cls.THEMES["Transcodia Light"]))
