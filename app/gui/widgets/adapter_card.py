# ============================================================
# Alfa Commander - Adapter Card Widget
# بطاقة عرض محول Alfa
# ============================================================

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QSizePolicy, QWidget,
)


class AdapterCard(QFrame):
    """بطاقة عرض محول واحد."""

    selected = pyqtSignal(str)          # adapter_id
    test_requested = pyqtSignal(str)    # adapter_id
    prepare_requested = pyqtSignal(str) # adapter_id
    release_requested = pyqtSignal(str) # adapter_id

    def __init__(self, adapter_info: dict, parent=None):
        super().__init__(parent)
        self.adapter_id = adapter_info.get("id", "")
        self.info = adapter_info
        self._setup_ui()
        self._populate()

    def _setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            AdapterCard {
                background-color: #252535;
                border: 1px solid #313244;
                border-radius: 10px;
                padding: 4px;
            }
            AdapterCard:hover {
                border-color: #89b4fa;
            }
        """)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.setMinimumHeight(160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # ---- الصف الأول: الاسم + USB ID ----
        row1 = QHBoxLayout()
        self.model_label = QLabel()
        f = QFont()
        f.setBold(True)
        f.setPointSize(12)
        self.model_label.setFont(f)
        self.model_label.setStyleSheet("color: #89b4fa;")
        row1.addWidget(self.model_label)
        row1.addStretch()

        self.usb_label = QLabel()
        self.usb_label.setStyleSheet("color: #6c7086; font-size: 9pt;")
        row1.addWidget(self.usb_label)
        layout.addLayout(row1)

        # ---- الصف الثاني: الشرائح والنطاقات ----
        row2 = QHBoxLayout()
        self.chipset_label = QLabel()
        self.chipset_label.setStyleSheet("color: #cdd6f4; font-size: 10pt;")
        row2.addWidget(self.chipset_label)
        row2.addStretch()

        self.bands_label = QLabel()
        self.bands_label.setStyleSheet(
            "background-color: #313244; color: #cdd6f4; "
            "border-radius: 4px; padding: 2px 8px; font-size: 9pt;"
        )
        row2.addWidget(self.bands_label)
        layout.addLayout(row2)

        # ---- الصف الثالث: الواجهة + الحالة ----
        row3 = QHBoxLayout()
        self.interface_label = QLabel()
        self.interface_label.setStyleSheet("color: #a6adc8; font-size: 9pt;")
        row3.addWidget(self.interface_label)
        row3.addStretch()

        self.state_label = QLabel()
        self.state_label.setStyleSheet(
            "color: #a6e3a1; font-weight: bold; font-size: 9pt;"
        )
        row3.addWidget(self.state_label)
        layout.addLayout(row3)

        # ---- شريط الحقن ----
        inj_layout = QHBoxLayout()
        inj_layout.addWidget(QLabel("الحقن:"))
        self.injection_bar = QProgressBar()
        self.injection_bar.setRange(0, 100)
        self.injection_bar.setTextVisible(True)
        self.injection_bar.setMaximumHeight(18)
        inj_layout.addWidget(self.injection_bar, 1)
        layout.addLayout(inj_layout)

        # ---- الأزرار ----
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_test = QPushButton("🧪 فحص الحقن")
        self.btn_test.clicked.connect(
            lambda: self.test_requested.emit(self.adapter_id)
        )
        btn_layout.addWidget(self.btn_test)

        self.btn_prepare = QPushButton("▶ تجهيز")
        self.btn_prepare.setObjectName("primary")
        self.btn_prepare.clicked.connect(
            lambda: self.prepare_requested.emit(self.adapter_id)
        )
        btn_layout.addWidget(self.btn_prepare)

        self.btn_release = QPushButton("⏹ تحرير")
        self.btn_release.setObjectName("warning")
        self.btn_release.clicked.connect(
            lambda: self.release_requested.emit(self.adapter_id)
        )
        btn_layout.addWidget(self.btn_release)

        layout.addLayout(btn_layout)

    def _populate(self):
        self.model_label.setText(self.info.get("model", "?"))
        self.chipset_label.setText(self.info.get("chipset", "?"))
        self.usb_label.setText(self.info.get("usb_id", ""))
        self.interface_label.setText(
            f"واجهة: {self.info.get('interface', '?')}"
        )

        bands = self.info.get("bands", [])
        self.bands_label.setText(" / ".join(b + "GHz" for b in bands))

        state = self.info.get("state", "unknown")
        self.state_label.setText(state)
        self._update_state_style(state)

        ratio = self.info.get("injection_ratio", 0)
        self.set_injection_ratio(ratio)

    def _update_state_style(self, state: str):
        colors = {
            "connected": "#a6e3a1",
            "managed": "#89b4fa",
            "monitor": "#f9e2af",
            "injecting": "#f9e2af",
            "ap_mode": "#cba6f7",
            "disconnected": "#6c7086",
            "error": "#f38ba8",
        }
        color = colors.get(state, "#cdd6f4")
        self.state_label.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 9pt;"
        )

    def set_injection_ratio(self, ratio: int):
        self.injection_bar.setValue(ratio)
        if ratio >= 50:
            color = "#a6e3a1"
        elif ratio >= 30:
            color = "#f9e2af"
        elif ratio >= 15:
            color = "#fab387"
        else:
            color = "#f38ba8"

        self.injection_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 4px;
                color: #cdd6f4;
                font-size: 8pt;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)

    def set_state(self, state: str):
        self.info["state"] = state
        self.state_label.setText(state)
        self._update_state_style(state)

    def set_buttons_enabled(self, enabled: bool):
        self.btn_test.setEnabled(enabled)
        self.btn_prepare.setEnabled(enabled)
        self.btn_release.setEnabled(enabled)

    def mousePressEvent(self, event):
        self.selected.emit(self.adapter_id)
        super().mousePressEvent(event)
