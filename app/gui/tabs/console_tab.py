# ============================================================
# Alfa Commander - Console Tab
# طرفية مدمجة لتنفيذ الأوامر
# ============================================================

from __future__ import annotations

import asyncio
import threading

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QLineEdit, QPushButton, QComboBox,
    QMessageBox,
)

from app.utils.shell import StreamingProcess
from app.logger import get_logger

logger = get_logger()


class ConsoleSignals(QObject):
    output = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal(int)


class ConsoleTab(QWidget):
    """تبويب طرفية مدمجة."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = ConsoleSignals()
        self._process = None
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._history: list[str] = []
        self._history_index = 0

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- الرأس ----
        header = QHBoxLayout()
        title = QLabel("💻 الطرفية")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        header.addWidget(QLabel("أوامر سريعة:"))
        self.quick_combo = QComboBox()
        self.quick_combo.addItem("اختر...", "")
        self.quick_combo.addItem("iwconfig", "iwconfig")
        self.quick_combo.addItem("lsusb", "lsusb")
        self.quick_combo.addItem("ifconfig -a", "ifconfig -a")
        self.quick_combo.addItem("iw dev", "iw dev")
        self.quick_combo.addItem("ip link show", "ip link show")
        self.quick_combo.addItem("dmesg | tail -50", "dmesg | tail -50")
        self.quick_combo.addItem("airmon-ng", "airmon-ng")
        self.quick_combo.addItem("lsmod | grep 8187", "lsmod | grep 8187")
        self.quick_combo.addItem("lsmod | grep 8812", "lsmod | grep 8812")
        self.quick_combo.addItem("lsmod | grep mt76", "lsmod | grep mt76")
        self.quick_combo.currentIndexChanged.connect(self._on_quick)
        header.addWidget(self.quick_combo)

        clear_btn = QPushButton("🗑 مسح")
        clear_btn.clicked.connect(self._clear)
        header.addWidget(clear_btn)

        layout.addLayout(header)

        # ---- منطقة الإخراج ----
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Monospace", 9))
        self.output.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0d0d15;
                color: #a6e3a1;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.output, 1)

        # ---- الإدخال ----
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("$"))

        self.input = QLineEdit()
        self.input.setPlaceholderText("اكتب أمراً واضغط Enter...")
        self.input.setFont(QFont("Monospace", 10))
        self.input.returnPressed.connect(self._execute)
        input_layout.addWidget(self.input, 1)

        self.run_btn = QPushButton("▶ تنفيذ")
        self.run_btn.setObjectName("primary")
        self.run_btn.clicked.connect(self._execute)
        input_layout.addWidget(self.run_btn)

        self.cancel_btn = QPushButton("⏹ إلغاء")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        input_layout.addWidget(self.cancel_btn)

        layout.addLayout(input_layout)

    def _connect_signals(self):
        self.signals.output.connect(self._append_output)
        self.signals.error.connect(self._append_error)
        self.signals.finished.connect(self._on_finished)

    # ============================================================
    # التنفيذ
    # ============================================================
    def _on_quick(self, idx: int):
        cmd = self.quick_combo.currentData()
        if cmd:
            self.input.setText(cmd)
            self.quick_combo.setCurrentIndex(0)

    def _execute(self):
        cmd = self.input.text().strip()
        if not cmd:
            return

        # حفظ في التاريخ
        self._history.append(cmd)
        self._history_index = len(self._history)

        # عرض الأمر
        self._append_output(f"$ {cmd}\n")

        # مسح الإدخال
        self.input.clear()

        # تعطيل الأزرار
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        # تشغيل الأمر
        self._run_command(cmd)

    def _run_command(self, cmd: str):
        from app.utils.shell import StreamingProcess

        def _on_stdout(line: str):
            self.signals.output.emit(line + "\n")

        def _on_stderr(line: str):
            self.signals.error.emit(line + "\n")

        def _on_exit(rc: int):
            self.signals.finished.emit(rc)

        proc = StreamingProcess(
            cmd,
            on_stdout=_on_stdout,
            on_stderr=_on_stderr,
            on_exit=_on_exit,
        )

        self._process = proc

        async def _run():
            try:
                await proc.start()
                await proc.wait()
            except Exception as e:
                self.signals.error.emit(f"خطأ: {e}\n")
                self.signals.finished.emit(-1)

        def _thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            try:
                loop.run_until_complete(_run())
            finally:
                loop.close()

        self._thread = threading.Thread(target=_thread, daemon=True)
        self._thread.start()

    def _cancel(self):
        if self._process and self._process.proc:
            try:
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._process.stop(),
                        self._loop,
                    )
            except Exception:
                pass
        self.cancel_btn.setEnabled(False)

    # ============================================================
    # العرض
    # ============================================================
    def _append_output(self, text: str):
        self.output.appendPlainText(text.rstrip("\n"))
        # التمرير للأسفل
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _append_error(self, text: str):
        # ألوان مختلفة للأخطاء
        cursor = self.output.textCursor()
        from PyQt6.QtGui import QTextCharFormat
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#f38ba8"))
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text, fmt)
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_finished(self, rc: int):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._append_output(f"\n[العملية انتهت برمز {rc}]\n\n")

    def _clear(self):
        self.output.clear()

    # ============================================================
    # أحداث لوحة المفاتيح
    # ============================================================
    def keyPressEvent(self, event):
        # السهم الأعلى/الأسفل للتاريخ
        if event.key() == Qt.Key.Key_Up and self.input.hasFocus():
            if self._history_index > 0:
                self._history_index -= 1
                self.input.setText(self._history[self._history_index])
            return
        if event.key() == Qt.Key.Key_Down and self.input.hasFocus():
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                self.input.setText(self._history[self._history_index])
            elif self._history_index == len(self._history) - 1:
                self._history_index += 1
                self.input.clear()
            return
        super().keyPressEvent(event)
