# ============================================================
# Alfa Commander - Network Row
# نموذج بيانات لشبكة في جدول المسح
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import QTableWidgetItem

from app.utils.formatters import (
    format_power, format_mac, power_color, signal_bars,
    truncate, safe_ssid,
)
from app.utils.oui_lookup import lookup as oui_lookup


# ------------------------------------------------------------
# ألوان أنواع التشفير
# ------------------------------------------------------------
ENCRYPTION_COLORS = {
    "OPEN": "#a6e3a1",
    "WEP": "#f9e2af",
    "WPA": "#fab387",
    "WPA2": "#89b4fa",
    "WPA3": "#cba6f7",
    "WPA2/WPA3": "#b4befe",
    "UNKNOWN": "#6c7086",
}


@dataclass
class NetworkRowData:
    """بيانات شبكة للعرض في الجدول."""
    bssid: str
    essid: str
    channel: int
    band: str
    encryption: str
    power: int
    beacons: int
    data_frames: int
    clients_count: int
    hidden: bool
    vendor: str
    last_seen: datetime


class NetworkRowFactory:
    """ينشئ QTableWidgetItem لكل عمود."""

    # الأعمدة:
    # 0: BSSID | 1: ESSID | 2: Channel | 3: Band | 4: Encryption
    # 5: Power | 6: Beacons | 7: Data | 8: Clients | 9: Vendor

    HEADERS = [
        "BSSID", "ESSID", "قناة", "نطاق", "تشفير",
        "قوة", "Beacons", "Data", "عملاء", "الشركة",
    ]

    @staticmethod
    def from_dict(data: dict) -> NetworkRowData:
        return NetworkRowData(
            bssid=data.get("bssid", ""),
            essid=data.get("essid", ""),
            channel=data.get("channel", 0),
            band=data.get("band", ""),
            encryption=data.get("encryption", "UNKNOWN"),
            power=data.get("power", -100),
            beacons=data.get("beacons", 0),
            data_frames=data.get("data_frames", 0),
            clients_count=data.get("clients_count", 0),
            hidden=data.get("hidden", False),
            vendor=data.get("vendor", ""),
            last_seen=data.get("last_seen", datetime.now()),
        )

    @staticmethod
    def create_items(row: NetworkRowData) -> list[QTableWidgetItem]:
        """ينشئ قائمة QTableWidgetItem لهذه الشبكة."""
        items = []

        # 0: BSSID
        item = QTableWidgetItem(row.bssid)
        item.setData(Qt.ItemDataRole.UserRole, row.bssid)
        items.append(item)

        # 1: ESSID
        essid_text = safe_ssid(row.essid) if not row.hidden else "<مخفي>"
        item = QTableWidgetItem(essid_text)
        if row.hidden:
            item.setForeground(QBrush(QColor("#6c7086")))
        items.append(item)

        # 2: Channel
        item = QTableWidgetItem(str(row.channel))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        items.append(item)

        # 3: Band
        item = QTableWidgetItem(row.band)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        items.append(item)

        # 4: Encryption
        item = QTableWidgetItem(row.encryption)
        color = ENCRYPTION_COLORS.get(row.encryption, "#cdd6f4")
        item.setForeground(QBrush(QColor(color)))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        items.append(item)

        # 5: Power
        power_text = f"{row.power} dBm"
        item = QTableWidgetItem(power_text)
        item.setForeground(QBrush(QColor(power_color(row.power))))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        # عمود مخصص للفرز
        item.setData(Qt.ItemDataRole.UserRole + 1, row.power)
        items.append(item)

        # 6: Beacons
        item = QTableWidgetItem(str(row.beacons))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        items.append(item)

        # 7: Data
        item = QTableWidgetItem(str(row.data_frames))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        items.append(item)

        # 8: Clients
        item = QTableWidgetItem(str(row.clients_count))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if row.clients_count > 0:
            item.setForeground(QBrush(QColor("#89b4fa")))
        items.append(item)

        # 9: Vendor
        item = QTableWidgetItem(truncate(row.vendor, 20))
        item.setForeground(QBrush(QColor("#a6adc8")))
        items.append(item)

        return items
