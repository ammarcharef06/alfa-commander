# ============================================================
# Alfa Commander - Status Bar Widget
# شريط الحالة السفلي
# ============================================================

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QStatusBar, QLabel, QWidget, QHBoxLayout, QProgressBar
)
from PyQt6.QtGui import QColor

from app.gui.signal_bus import get_signal_bus


class StatusBarWidget(QStatusBar):
    """شريط الحالة المخصص."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = get_signal_bus()
        self._setup_ui()
        self._connect_signals()
        self._start_clock()

    def _setup_ui(self):
        # شريط الحالة هو نفسه QStatusBar

        # ---- الأداة اليسرى: حالة النظام ----
        self.adapter_label = QLabel("لا يوجد محول")
        self.adapter_label.setMinimumWidth(200)
        self.addWidget(self.adapter_label)

        # ---- الفاصل ----
        separator1 = QLabel("│")
        separator1.setStyleSheet("color: #585b70;")
        self.addWidget(separator1)

        # ---- الحالة ----
        self.state_label = QLabel("جاهز")
        self.state_label.setMinimumWidth(150)
        self.addWidget(self.state_label)

        # ---- الفاصل ----
        separator2 = QLabel("│")
        separator2.setStyleSheet("color: #585b70;")
        self.addWidget(separator2)

        # ---- إحصاءات ----
        self.stats_label = QLabel("🌐 0  🔐 0  🔑 0")
        self.addWidget(self.stats_label)

        # ---- مساحة ممتدة ----
        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().horizontalPolicy().Expanding,
            spacer.sizePolicy().verticalPolicy().Preferred,
        )
        self.addWidget(spacer, 1)

        # ---- شريط تقدم غير مرئي افتراضياً ----
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        self.addPermanentWidget(self.progress)

        # ---- الساعة ----
        self.clock_label = QLabel()
        self.clock_label.setMinimumWidth(80)
        self.addPermanentWidget(self.clock_label)

        # ---- الحالة النهائية ----
        self.version_label = QLabel("v1.0.0")
        self.version_label.setStyleSheet("color: #6c7086;")
        self.addPermanentWidget(self.version_label)

    def _connect_signals(self):
        self.bus.adapter_changed.connect(self._on_adapter_changed)
        self.bus.network_found.connect(self._on_network_found)
        self.bus.handshake_captured.connect(self._on_handshake)
        self.bus.crack_succeeded.connect(self._on_cracked)
        self.bus.status_update.connect(self._on_status_update)
        self.bus.scan_started.connect(lambda _: self._show_progress(True))
        self.bus.scan_stopped.connect(lambda: self._show_progress(False))
        self.bus.attack_started.connect(lambda _: self._show_progress(True))
        self.bus.attack_finished.connect(lambda _: self._show_progress(False))

    def _start_clock(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        from datetime import datetime
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def _on_adapter_changed(self, adapter_id: str):
        self.adapter_label.setText(f"📶 {adapter_id[:20]}")

    def _on_network_found(self, data: dict):
        # لا نحدّث هنا، نترك الإحصاءات تتحدث
        pass

    def _on_handshake(self, data: dict):
        pass

    def _on_cracked(self, data: dict):
        pass

    def _on_status_update(self, key: str, value: str):
        self.state_label.setText(value)

    def _show_progress(self, show: bool):
        self.progress.setVisible(show)
        if show:
            self.progress.setRange(0, 0)  # indeterminate
        else:
            self.progress.setRange(0, 100)

    def set_adapter_info(self, adapter: dict):
        model = adapter.get("model", "?")
        iface = adapter.get("interface", "?")
        bands = ",".join(adapter.get("bands", []))
        self.adapter_label.setText(f"📶 {model} ({iface}) [{bands}]")

    def set_stats(self, networks: int, handshakes: int, cracked: int):
        self.stats_label.setText(
            f"🌐 {networks}  🔐 {handshakes}  🔑 {cracked}"
        )

    def set_state(self, text: str, level: str = "info"):
        colors = {
            "info": "#89b4fa",
            "success": "#a6e3a1",
            "warning": "#f9e2af",
            "error": "#f38ba8",
        }
        self.state_label.setText(text)
        self.state_label.setStyleSheet(
            f"color: {colors.get(level, colors['info'])};"
        )
