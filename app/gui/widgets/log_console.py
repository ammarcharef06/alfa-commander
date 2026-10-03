# ============================================================
# Alfa Commander - Log Console Widget
# وحدة عرض السجلات
# ============================================================

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QTextCursor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QComboBox, QLabel, QFileDialog, QMessageBox,
)

from app.gui.signal_bus import get_signal_bus
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# ألوان المستويات
# ------------------------------------------------------------
LEVEL_COLORS = {
    "DEBUG": "#6c7086",
    "INFO": "#89b4fa",
    "SUCCESS": "#a6e3a1",
    "WARNING": "#f9e2af",
    "ERROR": "#f38ba8",
    "CRITICAL": "#eba0ac",
}

LEVEL_ICONS = {
    "DEBUG": "🔍",
    "INFO": "ℹ",
    "SUCCESS": "✓",
    "WARNING": "⚠",
    "ERROR": "✗",
    "CRITICAL": "☠",
}


class LogConsole(QWidget):
    """وحدة عرض السجلات مع تلوين وفلترة."""

    def __init__(self, parent=None, max_lines: int = 5000):
        super().__init__(parent)
        self.bus = get_signal_bus()
        self.max_lines = max_lines
        self._buffer: list[tuple[str, str, str]] = []  # (level, time, message)
        self._auto_scroll = True

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ---- شريط الأدوات ----
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 8, 8, 0)

        toolbar.addWidget(QLabel("المستوى:"))

        self.level_filter = QComboBox()
        self.level_filter.addItems(
            ["الكل", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
        self.level_filter.setCurrentIndex(0)
        self.level_filter.setMinimumWidth(120)
        self.level_filter.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.level_filter)

        toolbar.addStretch()

        self.autoscroll_btn = QPushButton("⏬ تمرير تلقائي")
        self.autoscroll_btn.setCheckable(True)
        self.autoscroll_btn.setChecked(True)
        self.autoscroll_btn.clicked.connect(self._toggle_autoscroll)
        toolbar.addWidget(self.autoscroll_btn)

        clear_btn = QPushButton("🗑 مسح")
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)

        save_btn = QPushButton("💾 حفظ")
        save_btn.clicked.connect(self._save_log)
        toolbar.addWidget(save_btn)

        layout.addLayout(toolbar)

        # ---- منطقة النص ----
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumBlockCount(self.max_lines)
        self.text_edit.setFont(QFont("Monospace", 9))

        # منع تحديد النص بالكامل
        self.text_edit.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        layout.addWidget(self.text_edit)

        # ---- العدّاد ----
        self.counter_label = QLabel("0 سطر")
        self.counter_label.setStyleSheet("color: #6c7086; padding: 0 8px 8px;")
        layout.addWidget(self.counter_label)

    def _connect_signals(self):
        self.bus.log_message.connect(self.append_log)
        self.bus.status_update.connect(self._on_status_update)

    # ============================================================
    # إضافة السجلات
    # ============================================================
    @pyqtSlot(str, str)
    def append_log(self, level: str, message: str):
        """إضافة سطر جديد."""
        level = level.upper()
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._buffer.append((level, timestamp, message))

        # فحص الفلتر
        if not self._should_show(level):
            return

        self._append_to_view(level, timestamp, message)

    def _append_to_view(self, level: str, timestamp: str, message: str):
        """إضافة سطر مع تنسيق."""
        color = LEVEL_COLORS.get(level, "#cdd6f4")
        icon = LEVEL_ICONS.get(level, "•")

        # استخدم HTML للتلوين
        html = (
            f'<span style="color:#6c7086;">[{timestamp}]</span> '
            f'<span style="color:{color};">{icon} {level:8}</span> '
            f'<span style="color:#cdd6f4;">{self._escape_html(message)}</span>'
        )

        self.text_edit.appendHtml(html)

        if self._auto_scroll:
            self.text_edit.verticalScrollBar().setValue(
                self.text_edit.verticalScrollBar().maximum()
            )

        self._update_counter()

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # ============================================================
    # الفلترة
    # ============================================================
    def _should_show(self, level: str) -> bool:
        filter_text = self.level_filter.currentText()
        if filter_text == "الكل":
            return True
        return level == filter_text

    def _apply_filter(self):
        """إعادة بناء العرض بناءً على الفلتر."""
        self.text_edit.clear()
        for level, timestamp, message in self._buffer:
            if self._should_show(level):
                self._append_to_view(level, timestamp, message)

    # ============================================================
    # أدوات
    # ============================================================
    def clear(self):
        self.text_edit.clear()
        self._buffer.clear()
        self._update_counter()

    def _toggle_autoscroll(self):
        self._auto_scroll = self.autoscroll_btn.isChecked()

    def _update_counter(self):
        count = self.text_edit.blockCount() - 1
        self.counter_label.setText(f"{count} سطر")

    def _save_log(self):
        file, _ = QFileDialog.getSaveFileName(
            self, "حفظ السجل",
            f"alfa_commander_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)",
        )
        if not file:
            return
        try:
            with open(file, "w", encoding="utf-8") as f:
                for level, timestamp, message in self._buffer:
                    f.write(f"[{timestamp}] {level:8} {message}\n")
            QMessageBox.information(self, "تم", f"تم الحفظ في:\n{file}")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")

    def _on_status_update(self, key: str, value: str):
        self.append_log("INFO", f"{key}: {value}")
