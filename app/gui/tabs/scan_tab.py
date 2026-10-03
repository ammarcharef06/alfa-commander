# ============================================================
# Alfa Commander - Scan Tab
# تبويب المسح
# ============================================================

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QSpinBox, QComboBox,
    QMessageBox, QMenu, QAbstractItemView, QGroupBox,
    QGridLayout,
)

from app.gui.signal_bus import get_signal_bus
from app.gui.widgets.network_row import NetworkRowFactory, ENCRYPTION_COLORS
from app.logger import get_logger

logger = get_logger()


class ScanTab(QWidget):
    """تبويب المسح والاستكشاف."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = get_signal_bus()
        self.networks: dict[str, dict] = {}    # bssid → بيانات
        self.selected_bssids: set[str] = set()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- إعدادات المسح ----
        settings_box = QGroupBox("إعدادات المسح")
        grid = QGridLayout(settings_box)
        grid.setSpacing(10)

        # النطاق
        grid.addWidget(QLabel("النطاق:"), 0, 0)
        self.band_24 = QCheckBox("2.4GHz")
        self.band_24.setChecked(True)
        grid.addWidget(self.band_24, 0, 1)

        self.band_5 = QCheckBox("5GHz")
        self.band_5.setChecked(True)
        grid.addWidget(self.band_5, 0, 2)

        self.band_6 = QCheckBox("6GHz")
        grid.addWidget(self.band_6, 0, 3)

        # مدة القفز
        grid.addWidget(QLabel("زمن القفز (ث):"), 0, 4)
        self.dwell_spin = QSpinBox()
        self.dwell_spin.setRange(1, 50)
        self.dwell_spin.setValue(3)
        self.dwell_spin.setSuffix(" ×0.1s")
        grid.addWidget(self.dwell_spin, 0, 5)

        # تجاوز
        self.ignore_neg = QCheckBox("تجاهل خطأ -1 (RTL8187)")
        self.ignore_neg.setChecked(True)
        grid.addWidget(self.ignore_neg, 0, 6)

        # الأزرار
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ بدء المسح")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._toggle_scan)
        self.start_btn.setCheckable(True)
        btn_layout.addWidget(self.start_btn)

        self.clear_btn = QPushButton("🗑 مسح القائمة")
        self.clear_btn.clicked.connect(self._clear)
        btn_layout.addWidget(self.clear_btn)

        self.export_btn = QPushButton("💾 تصدير CSV")
        self.export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(self.export_btn)

        btn_layout.addStretch()

        self.summary = QLabel("لا يوجد مسح نشط")
        self.summary.setStyleSheet("color: #a6adc8;")
        btn_layout.addWidget(self.summary)

        grid.addLayout(btn_layout, 1, 0, 1, 7)

        layout.addWidget(settings_box)

        # ---- جدول الشبكات ----
        self.table = QTableWidget()
        self.table.setColumnCount(len(NetworkRowFactory.HEADERS))
        self.table.setHorizontalHeaderLabels(NetworkRowFactory.HEADERS)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in [0, 2, 3, 4, 5, 6, 7, 8]:
            header.setSectionResizeMode(
                i, QHeaderView.ResizeMode.ResizeToContents
            )

        layout.addWidget(self.table, 1)

        # ---- الشريط السفلي ----
        bottom = QHBoxLayout()

        self.count_label = QLabel("0 شبكة")
        self.count_label.setStyleSheet("color: #89b4fa; font-weight: bold;")
        bottom.addWidget(self.count_label)

        bottom.addStretch()

        self.attack_btn = QPushButton("⚔ إرسال إلى تبويب الهجوم")
        self.attack_btn.setObjectName("danger")
        self.attack_btn.clicked.connect(self._send_to_attack)
        bottom.addWidget(self.attack_btn)

        self.capture_btn = QPushButton("🎯 إرسال إلى الالتقاط")
        self.capture_btn.clicked.connect(self._send_to_capture)
        bottom.addWidget(self.capture_btn)

        layout.addLayout(bottom)

    def _connect_signals(self):
        self.bus.network_found.connect(self._on_network_found)
        self.bus.network_updated.connect(self._on_network_found)
        self.bus.scan_cleared.connect(self._clear)
        self.bus.scan_started.connect(self._on_scan_started)
        self.bus.scan_stopped.connect(self._on_scan_stopped)

    # ============================================================
    # المسح
    # ============================================================
    def _toggle_scan(self, checked: bool):
        if checked:
            self._start_scan()
        else:
            self._stop_scan()

    def _start_scan(self):
        from app.core import get_orchestrator
        orch = get_orchestrator()

        # اختيار المحول النشط
        active = orch.get_active_adapter()
        if not active:
            QMessageBox.warning(
                self, "لا يوجد محول",
                "قم بتجهيز محول أولاً من تبويب المحولات."
            )
            self.start_btn.setChecked(False)
            return

        # النطاقات
        channels = []
        if self.band_24.isChecked():
            from app.constants import BAND_2GHZ_CHANNELS
            channels.extend(BAND_2GHZ_CHANNELS)
        if self.band_5.isChecked() and "5" in active.DEFAULT_BANDS:
            from app.constants import BAND_5GHZ_CHANNELS
            channels.extend(BAND_5GHZ_CHANNELS)
        if self.band_6.isChecked() and "6" in active.DEFAULT_BANDS:
            from app.constants import BAND_6GHZ_CHANNELS
            channels.extend(BAND_6GHZ_CHANNELS)

        if not channels:
            QMessageBox.warning(
                self, "خطأ",
                "المحول لا يدعم النطاقات المختارة."
            )
            self.start_btn.setChecked(False)
            return

        self.start_btn.setText("⏹ إيقاف المسح")
        self.summary.setText("جارٍ المسح...")

        dwell = self.dwell_spin.value() / 10.0

        def _done(result, error):
            if error:
                self.summary.setText(f"فشل: {error}")
                self.start_btn.setChecked(False)

        coro = orch.start_scan(
            active_id := (active.mac or active.interface),
            channels=channels,
            dwell=dwell,
            ignore_negative_one=self.ignore_neg.isChecked(),
        )

        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    def _stop_scan(self):
        from app.core import get_orchestrator
        orch = get_orchestrator()

        def _done(_, __):
            self.summary.setText("متوقف")
            self.start_btn.setText("▶ بدء المسح")

        coro = orch.stop_scan()
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    # ============================================================
    # الأحداث
    # ============================================================
    @pyqtSlot(dict)
    def _on_network_found(self, data: dict):
        bssid = data.get("bssid", "")
        if not bssid:
            return

        self.networks[bssid] = data
        self._upsert_row(data)

        self.count_label.setText(f"{len(self.networks)} شبكة")

    def _upsert_row(self, data: dict):
        row_data = NetworkRowFactory.from_dict(data)
        items = NetworkRowFactory.create_items(row_data)

        # هل موجود؟
        existing_row = self._find_row(data["bssid"])
        if existing_row is not None:
            for col, item in enumerate(items):
                self.table.setItem(existing_row, col, item)
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

    def _find_row(self, bssid: str) -> int:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.text() == bssid:
                return row
        return -1

    def _on_scan_started(self, _):
        self.summary.setText("جارٍ المسح...")

    def _on_scan_stopped(self):
        self.summary.setText("متوقف")
        self.start_btn.setChecked(False)
        self.start_btn.setText("▶ بدء المسح")

    # ============================================================
    # الأدوات
    # ============================================================
    def _clear(self):
        self.table.setRowCount(0)
        self.networks.clear()
        self.selected_bssids.clear()
        self.count_label.setText("0 شبكة")

    def _export_csv(self):
        from PyQt6.QtWidgets import QFileDialog
        from datetime import datetime

        filename, _ = QFileDialog.getSaveFileName(
            self, "حفظ CSV",
            f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV (*.csv)",
        )
        if not filename:
            return

        try:
            import csv
            with open(filename, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(NetworkRowFactory.HEADERS)
                for row in range(self.table.rowCount()):
                    row_data = [
                        self.table.item(row, col).text()
                        if self.table.item(row, col) else ""
                        for col in range(self.table.columnCount())
                    ]
                    writer.writerow(row_data)
            QMessageBox.information(self, "تم", f"تم الحفظ: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل الحفظ: {e}")

    def _show_context_menu(self, pos):
        menu = QMenu(self)

        act_attack = menu.addAction("⚔ مهاجمة الشبكة")
        act_capture = menu.addAction("🎯 التقاط مصافحة")
        act_pmkid = menu.addAction("🔑 التقاط PMKID")
        act_wps = menu.addAction("📶 هجوم WPS")
        menu.addSeparator()
        act_evil = menu.addAction("🎭 Evil Twin")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_attack:
            self._send_to_attack()
        elif action == act_capture:
            self._send_to_capture()
        elif action == act_pmkid:
            self._send_to_pmkid()
        elif action == act_wps:
            self._send_to_wps()
        elif action == act_evil:
            self._send_to_evil_twin()

    def _get_selected_networks(self) -> list[dict]:
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        return [
            self.networks.get(self.table.item(r, 0).text(), {})
            for r in rows if self.table.item(r, 0)
        ]

    def _send_to_attack(self):
        selected = self._get_selected_networks()
        if not selected:
            QMessageBox.information(self, "تنبيه", "اختر شبكة أولاً.")
            return

        # إرسال الحدث
        self.bus.switch_tab.emit("الهجوم")
        if hasattr(self.window(), "attack_tab"):
            self.window().attack_tab.add_target(selected[0])

    def _send_to_capture(self):
        selected = self._get_selected_networks()
        if not selected:
            QMessageBox.information(self, "تنبيه", "اختر شبكة أولاً.")
            return

        self.bus.switch_tab.emit("الالتقاط")
        if hasattr(self.window(), "capture_tab"):
            self.window().capture_tab.add_target(selected[0])

    def _send_to_pmkid(self):
        selected = self._get_selected_networks()
        if not selected:
            QMessageBox.information(self, "تنبيه", "اختر شبكة أولاً.")
            return

        self.bus.switch_tab.emit("الالتقاط")
        if hasattr(self.window(), "capture_tab"):
            self.window().capture_tab.add_target(selected[0], mode="pmkid")

    def _send_to_wps(self):
        selected = self._get_selected_networks()
        if not selected:
            QMessageBox.information(self, "تنبيه", "اختر شبكة أولاً.")
            return
        self.bus.switch_tab.emit("الهجوم")
        if hasattr(self.window(), "attack_tab"):
            self.window().attack_tab.set_wps_target(selected[0])

    def _send_to_evil_twin(self):
        selected = self._get_selected_networks()
        if not selected:
            QMessageBox.information(self, "تنبيه", "اختر شبكة أولاً.")
            return
        self.bus.switch_tab.emit("Evil Twin")
        if hasattr(self.window(), "rogue_tab"):
            self.window().rogue_tab.set_target(selected[0])
