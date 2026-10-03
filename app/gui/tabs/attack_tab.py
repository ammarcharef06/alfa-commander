# ============================================================
# Alfa Commander - Attack Tab
# تبويب الهجمات
# ============================================================

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout, QComboBox,
    QSpinBox, QCheckBox, QLineEdit, QMessageBox,
    QTabWidget, QListWidget, QListWidgetItem, QProgressBar,
    QTextEdit, QSplitter, QFormLayout,
)

from app.gui.signal_bus import get_signal_bus
from app.logger import get_logger

logger = get_logger()


class AttackTab(QWidget):
    """تبويب تنفيذ الهجمات."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = get_signal_bus()
        self.current_target: dict = {}
        self.active_attacks: dict[str, str] = {}  # attack_id → نوع

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- الهدف الحالي ----
        target_box = QGroupBox("الهدف الحالي")
        target_layout = QHBoxLayout(target_box)

        self.target_label = QLabel("لم يتم اختيار هدف")
        self.target_label.setStyleSheet(
            "color: #89b4fa; font-weight: bold; font-size: 11pt;"
        )
        target_layout.addWidget(self.target_label)
        target_layout.addStretch()

        self.injection_label = QLabel("الحقن: —")
        self.injection_label.setStyleSheet("color: #a6adc8;")
        target_layout.addWidget(self.injection_label)

        layout.addWidget(target_box)

        # ---- التبويبات الفرعية للهجمات ----
        self.attack_tabs = QTabWidget()
        self.attack_tabs.addTab(self._build_deauth_tab(), "⚡ Deauth")
        self.attack_tabs.addTab(self._build_beacon_tab(), "📡 Beacon Flood")
        self.attack_tabs.addTab(self._build_auth_tab(), "🔐 Auth Flood")
        self.attack_tabs.addTab(self._build_wps_tab(), "🔑 WPS")
        self.attack_tabs.addTab(self._build_monitor_tab(), "📊 المراقبة")

        layout.addWidget(self.attack_tabs, 1)

    # ============================================================
    # تبويب Deauth
    # ============================================================
    def _build_deauth_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        # ---- الإعدادات ----
        form_box = QGroupBox("إعدادات Deauth")
        form = QFormLayout(form_box)

        self.deauth_count = QSpinBox()
        self.deauth_count.setRange(0, 1000)
        self.deauth_count.setValue(5)
        self.deauth_count.setSpecialValueText("∞")
        form.addRow("عدد الحزم (0=∞):", self.deauth_count)

        self.deauth_interval = QSpinBox()
        self.deauth_interval.setRange(1, 60)
        self.deauth_interval.setValue(1)
        form.addRow("الفاصل (ث):", self.deauth_interval)

        self.deauth_client = QLineEdit()
        self.deauth_client.setPlaceholderText(
            "MAC العميل (اتركه فارغاً للبث)"
        )
        form.addRow("العميل:", self.deauth_client)

        self.deauth_reason = QComboBox()
        from app.core.tools.aireplay import DEAUTH_REASONS
        for code, name in DEAUTH_REASONS.items():
            self.deauth_reason.addItem(f"{code} - {name}", code)
        self.deauth_reason.setCurrentIndex(6)  # 7
        form.addRow("السبب:", self.deauth_reason)

        self.deauth_auto = QCheckBox(
            "تكييف تلقائي بناءً على نسبة الحقن"
        )
        self.deauth_auto.setChecked(True)
        form.addRow("", self.deauth_auto)

        layout.addWidget(form_box)

        # ---- الأزرار ----
        btn_layout = QHBoxLayout()
        self.deauth_start = QPushButton("▶ بدء Deauth")
        self.deauth_start.setObjectName("danger")
        self.deauth_start.clicked.connect(self._start_deauth)
        btn_layout.addWidget(self.deauth_start)

        self.deauth_stop = QPushButton("⏹ إيقاف")
        self.deauth_stop.clicked.connect(self._stop_deauth)
        self.deauth_stop.setEnabled(False)
        btn_layout.addWidget(self.deauth_stop)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        return widget

    # ============================================================
    # تبويب Beacon Flood
    # ============================================================
    def _build_beacon_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form_box = QGroupBox("إعدادات Beacon Flood")
        form = QFormLayout(form_box)

        self.beacon_count = QSpinBox()
        self.beacon_count.setRange(1, 10000)
        self.beacon_count.setValue(100)
        form.addRow("عدد SSIDs:", self.beacon_count)

        self.beacon_channel = QSpinBox()
        self.beacon_channel.setRange(0, 165)
        self.beacon_channel.setValue(0)
        self.beacon_channel.setSpecialValueText("كل القنوات")
        form.addRow("القناة:", self.beacon_channel)

        self.beacon_category = QComboBox()
        from app.core.attacks.beacon_flood import SSID_TEMPLATES
        self.beacon_category.addItem("عشوائي", None)
        for cat in SSID_TEMPLATES.keys():
            self.beacon_category.addItem(cat, cat)
        form.addRow("فئة SSID:", self.beacon_category)

        self.beacon_wpa = QCheckBox("محاكاة WPA (يظهر كشبكة محمية)")
        self.beacon_wpa.setChecked(True)
        form.addRow("", self.beacon_wpa)

        layout.addWidget(form_box)

        btn_layout = QHBoxLayout()
        self.beacon_start = QPushButton("▶ بدء Beacon Flood")
        self.beacon_start.setObjectName("danger")
        self.beacon_start.clicked.connect(self._start_beacon)
        btn_layout.addWidget(self.beacon_start)

        self.beacon_stop = QPushButton("⏹ إيقاف")
        self.beacon_stop.setEnabled(False)
        self.beacon_stop.clicked.connect(self._stop_beacon)
        btn_layout.addWidget(self.beacon_stop)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        return widget

    # ============================================================
    # تبويب Auth Flood
    # ============================================================
    def _build_auth_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "يُرسل مئات طلبات المصادقة للهدف، مما يستهلك موارده.\n"
            "⚠ استخدمه فقط على شبكات تملكها."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #f9e2af; padding: 12px;")
        layout.addWidget(info)

        btn_layout = QHBoxLayout()
        self.auth_start = QPushButton("▶ بدء Auth Flood")
        self.auth_start.setObjectName("danger")
        self.auth_start.clicked.connect(self._start_auth)
        btn_layout.addWidget(self.auth_start)

        self.auth_stop = QPushButton("⏹ إيقاف")
        self.auth_stop.setEnabled(False)
        self.auth_stop.clicked.connect(self._stop_auth)
        btn_layout.addWidget(self.auth_stop)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        return widget

    # ============================================================
    # تبويب WPS
    # ============================================================
    def _build_wps_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form_box = QGroupBox("إعدادات WPS")
        form = QFormLayout(form_box)

        self.wps_mode = QComboBox()
        self.wps_mode.addItem("Pixie Dust (سريع)", "pixie")
        self.wps_mode.addItem("PIN Brute Force (بطيء)", "pin")
        form.addRow("الوضع:", self.wps_mode)

        self.wps_pin = QLineEdit()
        self.wps_pin.setPlaceholderText("PIN محدد (اختياري)")
        form.addRow("PIN:", self.wps_pin)

        self.wps_duration = QSpinBox()
        self.wps_duration.setRange(30, 3600)
        self.wps_duration.setValue(300)
        self.wps_duration.setSuffix(" ثانية")
        form.addRow("المدة:", self.wps_duration)

        layout.addWidget(form_box)

        btn_layout = QHBoxLayout()
        self.wps_start = QPushButton("▶ بدء هجوم WPS")
        self.wps_start.setObjectName("primary")
        self.wps_start.clicked.connect(self._start_wps)
        btn_layout.addWidget(self.wps_start)

        self.wps_stop = QPushButton("⏹ إيقاف")
        self.wps_stop.setEnabled(False)
        self.wps_stop.clicked.connect(self._stop_wps)
        btn_layout.addWidget(self.wps_stop)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        return widget

    # ============================================================
    # تبويب المراقبة
    # ============================================================
    def _build_monitor_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.attack_list = QListWidget()
        layout.addWidget(QLabel("الهجمات النشطة:"))
        layout.addWidget(self.attack_list, 1)

        self.attack_log = QTextEdit()
        self.attack_log.setReadOnly(True)
        self.attack_log.setMaximumHeight(150)
        layout.addWidget(QLabel("سجل الهجوم:"))
        layout.addWidget(self.attack_log)

        return widget

    # ============================================================
    # إشارات
    # ============================================================
    def _connect_signals(self):
        self.bus.attack_started.connect(self._on_attack_started)
        self.bus.attack_finished.connect(self._on_attack_finished)
        self.bus.injection_tested.connect(self._on_injection_tested)

    def _on_attack_started(self, data: dict):
        attack_id = data.get("process_id", "")
        atype = data.get("type", "unknown")
        target = data.get("target_bssid", "")

        if attack_id:
            self.active_attacks[attack_id] = atype

        item = QListWidgetItem(
            f"▶ {atype} على {target} [{attack_id}]"
        )
        self.attack_list.addItem(item)

        self.attack_log.append(
            f"[بدأ] {atype} | الهدف: {target} | المعرّف: {attack_id}"
        )

    def _on_attack_finished(self, data: dict):
        attack_id = data.get("process_id", "")
        success = data.get("success", False)

        if attack_id in self.active_attacks:
            del self.active_attacks[attack_id]

        status = "✓" if success else "✗"
        self.attack_log.append(
            f"[{status}] انتهى {attack_id}"
        )

    def _on_injection_tested(self, data: dict):
        ratio = data.get("ratio", 0)
        quality = data.get("quality", "")
        self.injection_label.setText(f"الحقن: {ratio}% ({quality})")

    # ============================================================
    # الواجهة العامة
    # ============================================================
    def add_target(self, network: dict):
        self.current_target = network
        essid = network.get("essid") or "<مخفي>"
        bssid = network.get("bssid", "")
        channel = network.get("channel", "?")
        encryption = network.get("encryption", "?")
        self.target_label.setText(
            f"{essid} | {bssid} | CH {channel} | {encryption}"
        )

    def set_wps_target(self, network: dict):
        self.add_target(network)
        self.attack_tabs.setCurrentIndex(3)  # WPS tab

    # ============================================================
    # الإجراءات - Deauth
    # ============================================================
    def _start_deauth(self):
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
        client = self.deauth_client.text().strip() or None
        count = self.deauth_count.value()
        interval = self.deauth_interval.value()

        adapter_id = adapter.mac or adapter.interface

        def _done(result, error):
            if error:
                QMessageBox.critical(self, "فشل", str(error))
                return
            self.deauth_stop.setEnabled(True)
            self.deauth_start.setEnabled(False)
            self.attack_log.append(f"Deauth بدأ: {result}")

        coro = orch.deauth(
            adapter_id=adapter_id,
            bssid=bssid,
            client=client,
            count=count if count > 0 else None,
            interval=interval,
        )

        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    def _stop_deauth(self):
        from app.core import get_orchestrator
        orch = get_orchestrator()
        from app.core.process_manager import ProcessKind

        def _done(_, __):
            self.deauth_stop.setEnabled(False)
            self.deauth_start.setEnabled(True)
            self.attack_log.append("Deauth متوقف")

        coro = orch.pm.stop_by_kind(ProcessKind.DEAUTH)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    # ============================================================
    # الإجراءات - Beacon
    # ============================================================
    def _start_beacon(self):
        from app.core import get_orchestrator
        orch = get_orchestrator()
        adapter = orch.get_active_adapter()
        if not adapter:
            QMessageBox.warning(self, "تنبيه", "لا يوجد محول نشط.")
            return

        adapter_id = adapter.mac or adapter.interface
        channel = self.beacon_channel.value() or None
        category = self.beacon_category.currentData()
        wpa = self.beacon_wpa.isChecked()
        count = self.beacon_count.value()

        def _done(result, error):
            if error:
                QMessageBox.critical(self, "فشل", str(error))
                return
            self.beacon_stop.setEnabled(True)
            self.beacon_start.setEnabled(False)

        coro = orch.beacon_flood(
            adapter_id=adapter_id,
            channel=channel,
            ssid_random=True,
            wpa=wpa,
        )
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    def _stop_beacon(self):
        from app.core import get_orchestrator
        from app.core.process_manager import ProcessKind
        orch = get_orchestrator()

        def _done(_, __):
            self.beacon_stop.setEnabled(False)
            self.beacon_start.setEnabled(True)

        coro = orch.pm.stop_by_kind(ProcessKind.BEACON_FLOOD)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    # ============================================================
    # الإجراءات - Auth Flood
    # ============================================================
    def _start_auth(self):
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

        def _done(result, error):
            if error:
                QMessageBox.critical(self, "فشل", str(error))
                return
            self.auth_stop.setEnabled(True)
            self.auth_start.setEnabled(False)

        coro = orch.auth_flood(adapter_id, bssid)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    def _stop_auth(self):
        from app.core import get_orchestrator
        from app.core.process_manager import ProcessKind
        orch = get_orchestrator()

        def _done(_, __):
            self.auth_stop.setEnabled(False)
            self.auth_start.setEnabled(True)

        coro = orch.pm.stop_by_kind(ProcessKind.AUTH_FLOOD)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    # ============================================================
    # الإجراءات - WPS
    # ============================================================
    def _start_wps(self):
        if not self.current_target:
            QMessageBox.warning(self, "تنبيه", "لم يتم اختيار هدف.")
            return
        from app.core import get_orchestrator
        orch = get_orchestrator()
        adapter = orch.get_active_adapter()
        if not adapter:
            return

        bssid = self.current_target.get("bssid", "")
        channel = self.current_target.get("channel", 6)
        adapter_id = adapter.mac or adapter.interface
        mode = self.wps_mode.currentData()
        pin = self.wps_pin.text().strip() or None

        def _done(result, error):
            if error:
                QMessageBox.critical(self, "فشل", str(error))
                return
            self.wps_stop.setEnabled(True)
            self.wps_start.setEnabled(False)

        coro = orch.wps_attack(
            adapter_id=adapter_id,
            bssid=bssid,
            channel=channel,
            pixie_dust=(mode == "pixie"),
            pin=pin,
        )
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    def _stop_wps(self):
        from app.core import get_orchestrator
        from app.core.process_manager import ProcessKind
        orch = get_orchestrator()

        def _done(_, __):
            self.wps_stop.setEnabled(False)
            self.wps_start.setEnabled(True)

        coro = orch.pm.stop_by_kind(ProcessKind.WPS)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)
