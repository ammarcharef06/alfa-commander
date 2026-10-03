# ============================================================
# Alfa Commander - Rogue Tab (Evil Twin)
# تبويب نقطة الوصول الشريرة
# ============================================================

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QLineEdit,
    QSpinBox, QMessageBox, QListWidget, QListWidgetItem,
    QTextEdit, QCheckBox, QComboBox,
)

from app.gui.signal_bus import get_signal_bus
from app.logger import get_logger

logger = get_logger()


class RogueTab(QWidget):
    """تبويب Evil Twin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = get_signal_bus()
        self.current_target: dict = {}
        self._manager = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- الهدف ----
        target_box = QGroupBox("الشبكة الهدف")
        target_layout = QHBoxLayout(target_box)
        self.target_label = QLabel("لم يتم اختيار هدف")
        self.target_label.setStyleSheet(
            "color: #89b4fa; font-weight: bold;"
        )
        target_layout.addWidget(self.target_label)
        target_layout.addStretch()
        layout.addWidget(target_box)

        # ---- الإعدادات ----
        settings = QGroupBox("إعدادات Evil Twin")
        form = QFormLayout(settings)

        self.ssid_input = QLineEdit()
        self.ssid_input.setPlaceholderText("SSID (يُملأ تلقائياً)")
        form.addRow("SSID:", self.ssid_input)

        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(1, 165)
        self.channel_spin.setValue(6)
        form.addRow("القناة:", self.channel_spin)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("اتركه فارغاً لشبكة مفتوحة")
        form.addRow("كلمة المرور:", self.password_input)

        self.gateway_input = QLineEdit("192.168.66.1")
        form.addRow("العنوان:", self.gateway_input)

        self.clone_bssid = QCheckBox("نسخ BSSID الهدف")
        form.addRow("", self.clone_bssid)

        self.template_combo = QComboBox()
        self.template_combo.addItem("بوابة عامة", "generic")
        self.template_combo.addItem("TP-Link", "router_tplink")
        self.template_combo.addItem("Netgear", "router_netgear")
        self.template_combo.addItem("Huawei", "router_huawei")
        form.addRow("قالب البوابة:", self.template_combo)

        layout.addWidget(settings)

        # ---- الأزرار ----
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ بدء Evil Twin")
        self.start_btn.setObjectName("danger")
        self.start_btn.clicked.connect(self._start)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ إيقاف")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ---- العملاء ----
        clients_box = QGroupBox("العملاء المتصلون")
        clients_layout = QVBoxLayout(clients_box)
        self.clients_list = QListWidget()
        clients_layout.addWidget(self.clients_list)
        layout.addWidget(clients_box)

        # ---- البيانات المخترقة ----
        creds_box = QGroupBox("🔓 البيانات المخترقة")
        creds_layout = QVBoxLayout(creds_box)
        self.creds_list = QListWidget()
        self.creds_list.setStyleSheet("""
            QListWidget::item {
                color: #a6e3a1;
                font-weight: bold;
            }
        """)
        creds_layout.addWidget(self.creds_list)
        layout.addWidget(creds_box)

        # ---- السجل ----
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        layout.addWidget(QLabel("السجل:"))
        layout.addWidget(self.log)

    def _connect_signals(self):
        self.bus.credential_captured.connect(self._on_credential)
        self.bus.rogue_ap_started.connect(self._on_started)
        self.bus.rogue_ap_stopped.connect(self._on_stopped)

    # ============================================================
    # الواجهة العامة
    # ============================================================
    def set_target(self, network: dict):
        self.current_target = network
        essid = network.get("essid") or ""
        bssid = network.get("bssid", "")
        channel = network.get("channel", 6)

        self.target_label.setText(f"{essid} | {bssid} | CH {channel}")
        self.ssid_input.setText(essid)
        self.channel_spin.setValue(channel if channel else 6)

    # ============================================================
    # التشغيل
    # ============================================================
    def _start(self):
        ssid = self.ssid_input.text().strip()
        if not ssid:
            QMessageBox.warning(self, "تنبيه", "أدخل SSID.")
            return

        from app.core import get_orchestrator
        orch = get_orchestrator()
        adapter = orch.get_active_adapter()
        if not adapter:
            QMessageBox.warning(self, "تنبيه", "لا يوجد محول نشط.")
            return

        # ملاحظة: Evil Twin يحتاج أن يكون المحول في وضع AP
        # هذا يتطلب إيقاف المراقبة أولاً
        adapter_id = adapter.mac or adapter.interface
        channel = self.channel_spin.value()
        password = self.password_input.text().strip() or None
        target_bssid = None
        if self.clone_bssid.isChecked() and self.current_target:
            target_bssid = self.current_target.get("bssid")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log.append(f"بدء Evil Twin على {ssid}")

        from app.core.rogue.evil_twin_manager import EvilTwinManager

        self._manager = EvilTwinManager(
            interface=adapter.interface,
            ssid=ssid,
            channel=channel,
            target_bssid=target_bssid,
            password=password,
            gateway=self.gateway_input.text() or "192.168.66.1",
            on_credential=self._on_manager_credential,
        )

        def _run():
            import asyncio
            asyncio.run(self._manager.start())

        import threading
        threading.Thread(target=_run, daemon=True).start()
        self._refresh_clients_timer()

    def _stop(self):
        if not self._manager:
            return

        def _run():
            import asyncio
            asyncio.run(self._manager.stop())

        import threading
        threading.Thread(target=_run, daemon=True).start()

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log.append("⏹ إيقاف Evil Twin")

    def _refresh_clients_timer(self):
        from PyQt6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_clients)
        self._timer.start(3000)

    def _refresh_clients(self):
        if not self._manager or not self._manager._dnsmasq:
            return

        clients = self._manager._dnsmasq.get_connected_clients()
        self.clients_list.clear()
        for c in clients:
            text = f"{c['ip']:15} | {c['mac']} | {c.get('hostname', '')}"
            self.clients_list.addItem(text)

    # ============================================================
    # الأحداث
    # ============================================================
    def _on_credential(self, data: dict):
        user = data.get("username", "")
        pwd = data.get("password", "")
        mac = data.get("client_mac", "")

        text = f"👤 {user}  🔑 {pwd}  ({mac})"
        self.creds_list.addItem(text)
        self.log.append(f"[!] التقاط: {text}")

    def _on_manager_credential(self, cred):
        # يُستدعى من Evil Twin Manager
        data = {
            "username": cred.username,
            "password": cred.password,
            "client_mac": cred.client_mac,
        }
        self.bus.credential_captured.emit(data)

    def _on_started(self, data: dict):
        self.log.append(f"✓ بدأ Evil Twin: {data}")

    def _on_stopped(self, data: dict):
        self.log.append(f"⏹ انتهى Evil Twin")
