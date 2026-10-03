# ============================================================
# Alfa Commander - Capture Tab
# تبويب التقاط Handshake و PMKID
# ============================================================

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QSpinBox,
    QMessageBox, QTabWidget, QListWidget, QListWidgetItem,
    QProgressBar, QTextEdit, QFileDialog,
)

from app.constants import EVIDENCE_DIR
from app.gui.signal_bus import get_signal_bus
from app.logger import get_logger

logger = get_logger()


class CaptureTab(QWidget):
    """تبويب الالتقاط."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = get_signal_bus()
        self.current_target: dict = {}
        self.mode: str = "handshake"

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- الهدف ----
        target_box = QGroupBox("الهدف الحالي")
        target_layout = QHBoxLayout(target_box)
        self.target_label = QLabel("لم يتم اختيار هدف")
        self.target_label.setStyleSheet(
            "color: #89b4fa; font-weight: bold; font-size: 11pt;"
        )
        target_layout.addWidget(self.target_label)
        target_layout.addStretch()
        layout.addWidget(target_box)

        # ---- التبويبات الفرعية ----
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_handshake_tab(), "🤝 Handshake")
        self.tabs.addTab(self._build_pmkid_tab(), "🔑 PMKID")
        self.tabs.addTab(self._build_captured_tab(), "📂 الملفات المحفوظة")
        layout.addWidget(self.tabs, 1)

    def _build_handshake_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        form_box = QGroupBox("إعدادات التقاط Handshake")
        form = QFormLayout(form_box)

        self.hs_duration = QSpinBox()
        self.hs_duration.setRange(30, 3600)
        self.hs_duration.setValue(120)
        self.hs_duration.setSuffix(" ثانية")
        form.addRow("المدة:", self.hs_duration)

        self.hs_auto_deauth = QWidget()
        from PyQt6.QtWidgets import QCheckBox
        self.hs_auto_deauth_cb = QCheckBox(
            "إرسال Deauth تلقائي لإجبار العميل على إعادة الاتصال"
        )
        self.hs_auto_deauth_cb.setChecked(True)
        form.addRow("", self.hs_auto_deauth_cb)

        layout.addWidget(form_box)

        btn_layout = QHBoxLayout()
        self.hs_start = QPushButton("▶ بدء الالتقاط")
        self.hs_start.setObjectName("primary")
        self.hs_start.clicked.connect(self._start_handshake)
        btn_layout.addWidget(self.hs_start)

        self.hs_stop = QPushButton("⏹ إيقاف")
        self.hs_stop.setEnabled(False)
        self.hs_stop.clicked.connect(self._stop_handshake)
        btn_layout.addWidget(self.hs_stop)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ---- التقدم ----
        self.hs_progress = QProgressBar()
        self.hs_progress.setRange(0, 0)
        self.hs_progress.setVisible(False)
        layout.addWidget(self.hs_progress)

        self.hs_log = QTextEdit()
        self.hs_log.setReadOnly(True)
        self.hs_log.setMaximumHeight(200)
        layout.addWidget(QLabel("السجل:"))
        layout.addWidget(self.hs_log)

        layout.addStretch()
        return widget

    def _build_pmkid_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        form_box = QGroupBox("إعدادات التقاط PMKID")
        form = QFormLayout(form_box)

        self.pmkid_duration = QSpinBox()
        self.pmkid_duration.setRange(30, 1800)
        self.pmkid_duration.setValue(120)
        self.pmkid_duration.setSuffix(" ثانية")
        form.addRow("المدة:", self.pmkid_duration)

        from PyQt6.QtWidgets import QCheckBox
        self.pmkid_active = QCheckBox("هجوم نشط (إرسال طلبات)")
        self.pmkid_active.setChecked(True)
        form.addRow("", self.pmkid_active)

        layout.addWidget(form_box)

        btn_layout = QHBoxLayout()
        self.pmkid_start = QPushButton("▶ بدء التقاط PMKID")
        self.pmkid_start.setObjectName("primary")
        self.pmkid_start.clicked.connect(self._start_pmkid)
        btn_layout.addWidget(self.pmkid_start)

        self.pmkid_stop = QPushButton("⏹ إيقاف")
        self.pmkid_stop.setEnabled(False)
        self.pmkid_stop.clicked.connect(self._stop_pmkid)
        btn_layout.addWidget(self.pmkid_stop)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.pmkid_progress = QProgressBar()
        self.pmkid_progress.setRange(0, 0)
        self.pmkid_progress.setVisible(False)
        layout.addWidget(self.pmkid_progress)

        self.pmkid_log = QTextEdit()
        self.pmkid_log.setReadOnly(True)
        self.pmkid_log.setMaximumHeight(200)
        layout.addWidget(QLabel("السجل:"))
        layout.addWidget(self.pmkid_log)

        layout.addStretch()
        return widget

    def _build_captured_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(QLabel("الملفات المحفوظة:"))
        header.addStretch()

        refresh_btn = QPushButton("🔄 تحديث")
        refresh_btn.clicked.connect(self._refresh_captures)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self.captures_list = QListWidget()
        layout.addWidget(self.captures_list, 1)

        btn_layout = QHBoxLayout()

        self.open_folder_btn = QPushButton("📁 فتح مجلد الملفات")
        self.open_folder_btn.clicked.connect(self._open_folder)
        btn_layout.addWidget(self.open_folder_btn)

        self.export_btn = QPushButton("📤 تصدير")
        self.export_btn.clicked.connect(self._export_capture)
        btn_layout.addWidget(self.export_btn)

        self.crack_btn = QPushButton("🔓 إرسال للكسر")
        self.crack_btn.setObjectName("primary")
        self.crack_btn.clicked.connect(self._send_to_crack)
        btn_layout.addWidget(self.crack_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _connect_signals(self):
        self.bus.capture_saved.connect(self._on_capture_saved)
        self.bus.handshake_captured.connect(self._on_capture_saved)
        self.bus.pmkid_captured.connect(self._on_capture_saved)

    # ============================================================
    # الواجهة العامة
    # ============================================================
    def add_target(self, network: dict, mode: str = "handshake"):
        self.current_target = network
        self.mode = mode
        essid = network.get("essid") or "<مخفي>"
        bssid = network.get("bssid", "")
        channel = network.get("channel", "?")
        self.target_label.setText(
            f"{essid} | {bssid} | CH {channel}"
        )
        # تحديد التبويب
        self.tabs.setCurrentIndex(0 if mode == "handshake" else 1)

    # ============================================================
    # Handshake
    # ============================================================
    def _start_handshake(self):
        if not self.current_target:
            QMessageBox.warning(self, "تنبيه", "لم يتم اختيار هدف.")
            return

        from app.core import get_orchestrator
        orch = get_orchestrator()
        adapter = orch.get_active_adapter()
        if not adapter:
            QMessageBox.warning(self, "تنبيه", "لا يوجد محول نشط.")
            return

        bssid = self.current_target.get("bssid", "")
        channel = self.current_target.get("channel", 6)
        adapter_id = adapter.mac or adapter.interface
        duration = self.hs_duration.value()

        self.hs_progress.setVisible(True)
        self.hs_start.setEnabled(False)
        self.hs_stop.setEnabled(True)
        self.hs_log.append(f"بدء الالتقاط على {bssid} (CH {channel})")

        def _done(result, error):
            if error:
                self.hs_log.append(f"✗ فشل: {error}")
            else:
                self.hs_log.append(f"✓ بدأ الالتقاط [{result}]")

        coro = orch.capture_handshake(
            adapter_id=adapter_id,
            bssid=bssid,
            channel=channel,
            duration=duration,
        )
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    def _stop_handshake(self):
        from app.core import get_orchestrator
        from app.core.process_manager import ProcessKind
        orch = get_orchestrator()

        def _done(_, __):
            self.hs_progress.setVisible(False)
            self.hs_start.setEnabled(True)
            self.hs_stop.setEnabled(False)
            self.hs_log.append("⏹ توقف الالتقاط")

        coro = orch.pm.stop_by_kind(ProcessKind.HANDSHAKE)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    # ============================================================
    # PMKID
    # ============================================================
    def _start_pmkid(self):
        if not self.current_target:
            QMessageBox.warning(self, "تنبيه", "لم يتم اختيار هدف.")
            return

        from app.core import get_orchestrator
        orch = get_orchestrator()
        adapter = orch.get_active_adapter()
        if not adapter:
            return

        bssid = self.current_target.get("bssid", "")
        adapter_id = adapter.mac or adapter.interface
        duration = self.pmkid_duration.value()

        self.pmkid_progress.setVisible(True)
        self.pmkid_start.setEnabled(False)
        self.pmkid_stop.setEnabled(True)
        self.pmkid_log.append(f"بدء PMKID على {bssid}")

        def _done(result, error):
            if error:
                self.pmkid_log.append(f"✗ فشل: {error}")
            else:
                self.pmkid_log.append(f"✓ بدأ PMKID [{result}]")

        coro = orch.capture_pmkid(
            adapter_id=adapter_id,
            bssid=bssid,
            duration=duration,
        )
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    def _stop_pmkid(self):
        from app.core import get_orchestrator
        from app.core.process_manager import ProcessKind
        orch = get_orchestrator()

        def _done(_, __):
            self.pmkid_progress.setVisible(False)
            self.pmkid_start.setEnabled(True)
            self.pmkid_stop.setEnabled(False)

        coro = orch.pm.stop_by_kind(ProcessKind.PMKID)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    # ============================================================
    # الملفات المحفوظة
    # ============================================================
    def _refresh_captures(self):
        self.captures_list.clear()
        from app.core.capture import PCAPManager
        try:
            captures = PCAPManager.list_captures()
            for c in captures:
                text = (
                    f"{c.path.name}  |  {c.type}  |  "
                    f"{c.size_bytes // 1024} KB"
                )
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, str(c.path))
                self.captures_list.addItem(item)
        except Exception as e:
            logger.exception(f"فشل التحديث: {e}")

    def _on_capture_saved(self, data: dict):
        self._refresh_captures()
        file = data.get("file", "")
        if file:
            self.hs_log.append(f"✓ تم الحفظ: {file}")
            self.pmkid_log.append(f"✓ تم الحفظ: {file}")

    def _open_folder(self):
        import subprocess
        try:
            subprocess.Popen(["xdg-open", str(EVIDENCE_DIR)])
        except Exception as e:
            QMessageBox.warning(self, "خطأ", str(e))

    def _export_capture(self):
        item = self.captures_list.currentItem()
        if not item:
            QMessageBox.information(self, "تنبيه", "اختر ملفاً أولاً.")
            return
        src = item.data(Qt.ItemDataRole.UserRole)
        if not src:
            return
        from pathlib import Path
        dst, _ = QFileDialog.getSaveFileName(
            self, "تصدير", Path(src).name,
        )
        if not dst:
            return
        try:
            import shutil
            shutil.copy2(src, dst)
            QMessageBox.information(self, "تم", f"تم التصدير إلى: {dst}")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", str(e))

    def _send_to_crack(self):
        item = self.captures_list.currentItem()
        if not item:
            QMessageBox.information(self, "تنبيه", "اختر ملفاً أولاً.")
            return
        filepath = item.data(Qt.ItemDataRole.UserRole)
        if filepath and hasattr(self.window(), "crack_tab"):
            self.window().crack_tab.add_hash_file(filepath)
            self.bus.switch_tab.emit("الكسر")
