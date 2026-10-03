# ============================================================
# Alfa Commander - Theme Manager
# إدارة ثيمات الواجهة
# ============================================================

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QDir

from app.constants import RESOURCES_DIR
from app.config import get_config
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# الثيم الداكن
# ------------------------------------------------------------
DARK_THEME = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Cairo', 'Segoe UI', 'Tahoma', sans-serif;
    font-size: 11pt;
}

QMainWindow, QDialog {
    background-color: #181825;
}

QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 10px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
    min-width: 100px;
}

QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #89b4fa;
    border-bottom: 3px solid #89b4fa;
}

QTabBar::tab:hover {
    background-color: #313244;
}

QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}

QPushButton:pressed {
    background-color: #585b70;
}

QPushButton:disabled {
    background-color: #252535;
    color: #585b70;
    border-color: #313244;
}

QPushButton#primary {
    background-color: #89b4fa;
    color: #1e1e2e;
}

QPushButton#primary:hover {
    background-color: #b4befe;
}

QPushButton#danger {
    background-color: #f38ba8;
    color: #1e1e2e;
}

QPushButton#danger:hover {
    background-color: #eba0ac;
}

QPushButton#success {
    background-color: #a6e3a1;
    color: #1e1e2e;
}

QPushButton#warning {
    background-color: #f9e2af;
    color: #1e1e2e;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QComboBox:focus {
    border: 1px solid #89b4fa;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #cdd6f4;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QTableWidget, QTableView {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 6px;
    selection-background-color: #313244;
    selection-color: #89b4fa;
}

QTableWidget::item, QTableView::item {
    padding: 6px;
    border: none;
}

QHeaderView::section {
    background-color: #1e1e2e;
    color: #89b4fa;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #313244;
    font-weight: bold;
}

QTreeWidget, QTreeView {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
}

QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
}

QProgressBar {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    text-align: center;
    color: #cdd6f4;
    height: 22px;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 5px;
}

QScrollBar:vertical {
    background-color: #181825;
    width: 12px;
    margin: 0;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    min-height: 20px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #181825;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #45475a;
    min-width: 20px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
}

QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
}

QMenuBar::item:selected {
    background-color: #313244;
}

QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
}

QMenu::item:selected {
    background-color: #313244;
}

QLabel {
    background-color: transparent;
    color: #cdd6f4;
}

QLabel#title {
    font-size: 16pt;
    font-weight: bold;
    color: #89b4fa;
}

QLabel#subtitle {
    font-size: 10pt;
    color: #a6adc8;
}

QLabel#success {
    color: #a6e3a1;
}

QLabel#danger {
    color: #f38ba8;
}

QLabel#warning {
    color: #f9e2af;
}

QCheckBox, QRadioButton {
    spacing: 8px;
    color: #cdd6f4;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #45475a;
    border-radius: 4px;
    background-color: #181825;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QRadioButton::indicator {
    border-radius: 9px;
}

QSplitter::handle {
    background-color: #313244;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}

QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
"""


# ------------------------------------------------------------
# الثيم الفاتح
# ------------------------------------------------------------
LIGHT_THEME = """
QWidget {
    background-color: #eff1f5;
    color: #4c4f69;
    font-family: 'Cairo', 'Segoe UI', 'Tahoma', sans-serif;
    font-size: 11pt;
}

QMainWindow, QDialog {
    background-color: #e6e9ef;
}

QTabWidget::pane {
    border: 1px solid #ccd0da;
    background-color: #eff1f5;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #e6e9ef;
    color: #6c6f85;
    padding: 10px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
    min-width: 100px;
}

QTabBar::tab:selected {
    background-color: #eff1f5;
    color: #1e66f5;
    border-bottom: 3px solid #1e66f5;
}

QPushButton {
    background-color: #dce0e8;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #ccd0da;
}

QPushButton:pressed {
    background-color: #bcc0cc;
}

QPushButton#primary {
    background-color: #1e66f5;
    color: white;
}

QPushButton#primary:hover {
    background-color: #2a76ff;
}

QPushButton#danger {
    background-color: #d20f39;
    color: white;
}

QPushButton#success {
    background-color: #40a02b;
    color: white;
}

QPushButton#warning {
    background-color: #df8e1d;
    color: white;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: white;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 6px 10px;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #1e66f5;
}

QTableWidget, QTableView {
    background-color: white;
    alternate-background-color: #f5f6f8;
    color: #4c4f69;
    gridline-color: #e6e9ef;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    selection-background-color: #dce0e8;
    selection-color: #1e66f5;
}

QHeaderView::section {
    background-color: #e6e9ef;
    color: #1e66f5;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #ccd0da;
    font-weight: bold;
}

QGroupBox {
    border: 1px solid #ccd0da;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #1e66f5;
}

QProgressBar {
    background-color: #e6e9ef;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    text-align: center;
    color: #4c4f69;
    height: 22px;
}

QProgressBar::chunk {
    background-color: #1e66f5;
    border-radius: 5px;
}

QStatusBar {
    background-color: #e6e9ef;
    color: #6c6f85;
    border-top: 1px solid #ccd0da;
}

QLabel {
    background-color: transparent;
}

QLabel#title {
    font-size: 16pt;
    font-weight: bold;
    color: #1e66f5;
}

QLabel#success {
    color: #40a02b;
}

QLabel#danger {
    color: #d20f39;
}

QLabel#warning {
    color: #df8e1d;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #bcc0cc;
    border-radius: 4px;
    background-color: white;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #1e66f5;
    border-color: #1e66f5;
}
"""


# ------------------------------------------------------------
# مدير الثيمات
# ------------------------------------------------------------
class ThemeManager:
    THEMES = {
        "dark": DARK_THEME,
        "light": LIGHT_THEME,
    }

    @staticmethod
    def apply_theme(app: QApplication, theme: str = "dark"):
        """تطبيق ثيم على التطبيق."""
        theme = theme if theme in ThemeManager.THEMES else "dark"
        stylesheet = ThemeManager.THEMES[theme]
        app.setStyleSheet(stylesheet)
        logger.info(f"تم تطبيق الثيم: {theme}")

    @staticmethod
    def load_arabic_font(app: QApplication):
        """تحميل خط عربي مناسب."""
        # الخطوط المتوفرة على النظام
        available_families = QFontDatabase.families()

        preferred = ["Cairo", "Tajawal", "Almarai", "Noto Sans Arabic",
                     "DejaVu Sans", "Ubuntu", "Segoe UI"]

        selected = None
        for font_name in preferred:
            if font_name in available_families:
                selected = font_name
                break

        if not selected:
            selected = available_families[0] if available_families else "Sans"

        font = QFont(selected, 11)
        app.setFont(font)
        logger.info(f"تم تحميل الخط: {selected}")
        return selected

    @staticmethod
    def apply_rtl(app: QApplication, rtl: bool = True):
        """تفعيل اتجاه RTL."""
        app.setLayoutDirection(
            app.layoutDirection().__class__.RightToLeft
            if rtl
            else app.layoutDirection().__class__.LeftToRight
        )

    @staticmethod
    def apply_all(app: QApplication, theme: Optional[str] = None):
        """تطبيق كل الإعدادات."""
        cfg = get_config().config.ui
        ThemeManager.load_arabic_font(app)
        ThemeManager.apply_theme(app, theme or cfg.theme)
        ThemeManager.apply_rtl(app, cfg.language == "ar")
