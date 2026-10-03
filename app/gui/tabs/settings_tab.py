# ============================================================
# Alfa Commander - Settings Tab
# تبويب الإعدادات
# ============================================================

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QFormLayout, QComboBox,
    QSpinBox, QLineEdit, QCheckBox, QGroupBox,
    QMessageBox, QFileDialog, QListWidget, QListWidgetItem,
)

from app.config import get_config
from app.gui.signal_bus import get_signal_bus
from app.logger import get_logger

logger = get_logger()


class SettingsTab(QWidget):
    """تبويب الإعدادات."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = get_signal_bus()
        self.cfg = get_config()

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("⚙ الإعدادات")
        title.setObjectName("title")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "عام")
        self.tabs.addTab(self._build_scan_tab(), "المسح")
        self.tabs.addTab(self._build_attack_tab(), "الهجوم")
        self.tabs.addTab(self._build_capture_tab(), "الالتقاط")
        self.tabs.addTab(self._build_crack_tab(), "الكسر")
        self.tabs.addTab(self._build_rogue_tab(), "Evil Twin")

        layout.addWidget(self.tabs, 1)

        # ---- الأزرار ----
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("💾 حفظ")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        reset_btn = QPushButton("🔄 إعادة تعيين")
        reset_btn.clicked.connect(self._reset)
        btn_layout.addWidget(reset_btn)

        layout.addLayout(btn_layout)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        ui = self.cfg.config.ui
        general = self.cfg.config.general

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("داكن", "dark")
        self.theme_combo.addItem("فاتح", "light")
        self.theme_combo.setCurrentIndex(
            0 if ui.theme == "dark" else 1
        )
        form.addRow("الثيم:", self.theme_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("العربية", "ar")
        self.lang_combo.addItem("English", "en")
        form.addRow("اللغة:", self.lang_combo)

        self.autocheck_cb = QCheckBox("فحص البيئة تلقائياً")
        self.autocheck_cb.setChecked(general.auto_check_dependencies)
        form.addRow("", self.autocheck_cb)

        return widget

    def _build_scan_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        scan = self.cfg.config.scan

        self.scan_duration = QSpinBox()
        self.scan_duration.setRange(5, 600)
        self.scan_duration.setValue(scan.default_duration)
        self.scan_duration.setSuffix(" ثانية")
        form.addRow("مدة المسح الافتراضية:", self.scan_duration)

        self.scan_dwell = QSpinBox()
        self.scan_dwell.setRange(1, 50)
        self.scan_dwell.setValue(3)
        form.addRow("زمن القفز ×0.1s:", self.scan_dwell)

        return widget

    def _build_attack_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        atk = self.cfg.config.attack

        self.deauth_count = QSpinBox()
        self.deauth_count.setRange(0, 1000)
        self.deauth_count.setValue(atk.deauth_count)
        self.deauth_count.setSpecialValueText("∞")
        form.addRow("عدد Deauth الافتراضي:", self.deauth_count)

        self.deauth_interval = QSpinBox()
        self.deauth_interval.setRange(1, 60)
        self.deauth_interval.setValue(atk.deauth_interval)
        form.addRow("الفاصل الافتراضي (ث):", self.deauth_interval)

        self.auto_check_inj = QCheckBox("فحص الحقن تلقائياً قبل الهجوم")
        self.auto_check_inj.setChecked(atk.auto_check_injection)
        form.addRow("", self.auto_check_inj)

        self.min_inj = QSpinBox()
        self.min_inj.setRange(0, 100)
        self.min_inj.setValue(atk.min_injection_ratio)
        self.min_inj.setSuffix("%")
        form.addRow("أدنى نسبة حقن:", self.min_inj)

        return widget

    def _build_capture_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        cap = self.cfg.config.capture

        self.cap_format = QComboBox()
        self.cap_format.addItems(["pcap", "pcapng", "cap"])
        self.cap_format.setCurrentText(cap.output_format)
        form.addRow("صيغة الالتقاط:", self.cap_format)

        self.auto_hashcat = QCheckBox("تحويل تلقائي إلى hashcat 22000")
        self.auto_hashcat.setChecked(cap.auto_convert_to_hashcat)
        form.addRow("", self.auto_hashcat)

        self.keep_pcap = QCheckBox("الاحتفاظ بملف pcap")
        self.keep_pcap.setChecked(cap.keep_pcap)
        form.addRow("", self.keep_pcap)

        return widget

    def _build_crack_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        crack = self.cfg.config.crack

        self.wordlist_input = QLineEdit(crack.default_wordlist)
        form.addRow("قائمة الكلمات:", self.wordlist_input)

        self.workload_combo = QComboBox()
        self.workload_combo.addItems([
            "1 - منخفض",
            "2 - افتراضي",
            "3 - عالي",
            "4 - أقصى",
        ])
        self.workload_combo.setCurrentIndex(crack.workload_profile - 1)
        form.addRow("مستوى الجهد:", self.workload_combo)

        self.use_gpu = QCheckBox("استخدام GPU")
        self.use_gpu.setChecked(crack.use_gpu)
        form.addRow("", self.use_gpu)

        return widget

    def _build_rogue_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        rogue = self.cfg.config.rogue

        self.gateway_input = QLineEdit(rogue.gateway_ip)
        form.addRow("عنوان البوابة:", self.gateway_input)

        self.dhcp_start = QLineEdit(rogue.dhcp_range_start)
        form.addRow("بداية DHCP:", self.dhcp_start)

        self.dhcp_end = QLineEdit(rogue.dhcp_range_end)
        form.addRow("نهاية DHCP:", self.dhcp_end)

        return widget

    # ============================================================
    # الحفظ
    # ============================================================
    def _save(self):
        cfg = self.cfg.config

        # UI
        cfg.ui.theme = self.theme_combo.currentData()
        cfg.ui.language = self.lang_combo.currentData()
        cfg.general.auto_check_dependencies = self.autocheck_cb.isChecked()

        # Scan
        cfg.scan.default_duration = self.scan_duration.value()

        # Attack
        cfg.attack.deauth_count = self.deauth_count.value()
        cfg.attack.deauth_interval = self.deauth_interval.value()
        cfg.attack.auto_check_injection = self.auto_check_inj.isChecked()
        cfg.attack.min_injection_ratio = self.min_inj.value()

        # Capture
        cfg.capture.output_format = self.cap_format.currentText()
        cfg.capture.auto_convert_to_hashcat = self.auto_hashcat.isChecked()
        cfg.capture.keep_pcap = self.keep_pcap.isChecked()

        # Crack
        cfg.crack.default_wordlist = self.wordlist_input.text()
        cfg.crack.workload_profile = self.workload_combo.currentIndex() + 1
        cfg.crack.use_gpu = self.use_gpu.isChecked()

        # Rogue
        cfg.rogue.gateway_ip = self.gateway_input.text()
        cfg.rogue.dhcp_range_start = self.dhcp_start.text()
        cfg.rogue.dhcp_range_end = self.dhcp_end.text()

        self.cfg.save()
        QMessageBox.information(self, "تم", "تم حفظ الإعدادات.")

    def _reset(self):
        reply = QMessageBox.question(
            self, "إعادة تعيين",
            "هل تريد إعادة تعيين كل الإعدادات للحالة الافتراضية؟",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.cfg.reset()
            QMessageBox.information(
                self, "تم",
                "أُعيد تعيين الإعدادات. أعد تشغيل البرنامج للتطبيق."
            )
