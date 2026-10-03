# ============================================================
# Alfa Commander - MT7921AUN Adapter (AWUS036AXM/AXML)
# شريحة WiFi 6 الحديثة
# ============================================================

from __future__ import annotations

from app.core.adapters.base_adapter import BaseAlfaAdapter
from app.core.tools import iw
from app.utils.shell import run
from app.logger import get_logger

logger = get_logger()


class MT7921AUNAdapter(BaseAlfaAdapter):
    """
    محول AWUS036AXM / AWUS036AXML (MT7921AUN).

    - WiFi 6 (802.11ax) و يدعم 6GHz.
    - يحتاج نواة 5.18 أو أحدث.
    - بعض إصدارات Kali بها مشاكل توافق مع Bluetooth.
    - قد يحتاج تحديث firmware.
    """

    MODEL = "AWUS036AXML"
    CHIPSET = "MT7921AUN"
    USB_IDS = ["0e8d:7961", "0e8d:7962"]
    DEFAULT_BANDS = ["2.4", "5", "6"]
    DEFAULT_DRIVER = "mt7921u"
    DRIVER_TYPE = "in-kernel"
    MAX_STANDARD = "802.11ax"
    MIN_KERNEL = "5.18"
    SUPPORTS_5GHZ = True
    SUPPORTS_6GHZ = True

    KNOWN_ISSUES = [
        "يحتاج نواة 5.18 أو أحدث.",
        "بعض إصدارات Kali 2024/2025 بها مشاكل توافق مع Bluetooth.",
        "قد يحتاج تحديث firmware يدوياً من linux-firmware.",
    ]

    USAGE_NOTES = [
        "أول محول Alfa يدعم 6GHz.",
        "مثالي لمهاجمة شبكات WiFi 6/6E الحديثة.",
        "على Kali، قد تحتاج تخفيض إصدار النواة للاستقرار.",
    ]

    # ============================================================
    # فحص إضافي لإصدار النواة
    # ============================================================
    def _check_kernel(self) -> bool:
        import platform
        try:
            current = platform.release().split("-")[0]
            parts = tuple(int(x) for x in current.split(".")[:2])
            required = tuple(int(x) for x in self.MIN_KERNEL.split(".")[:2])
            return parts >= required
        except Exception:
            return True

    def check_readiness(self, test_injection: bool = True):
        report = super().check_readiness(test_injection)
        if not self._check_kernel():
            report.warnings.append(
                f"إصدار النواة الحالي قديم. المطلوب: {self.MIN_KERNEL}+"
            )
            report.ready = False
        return report

    # ============================================================
    # وضع المراقبة
    # ============================================================
    def enter_monitor_mode(self) -> bool:
        logger.info(f"[{self.MODEL}] تفعيل وضع المراقبة...")

        if self._run_iw_monitor():
            # mt7921 يدعم active monitor
            run(["iw", self.get_active_interface(), "set", "monitor", "active"])
            return True

        monitor_iface = self._run_airmon_start()
        return bool(monitor_iface)

    def exit_monitor_mode(self) -> bool:
        return self._run_iw_managed()

    def validate_injection(self) -> int:
        logger.info(f"[{self.MODEL}] اختبار الحقن...")
        return self._run_injection_test()

    def supports_channel(self, channel: int) -> bool:
        from app.constants import (
            BAND_2GHZ_CHANNELS, BAND_5GHZ_CHANNELS, BAND_6GHZ_CHANNELS
        )
        return channel in BAND_2GHZ_CHANNELS or \
               channel in BAND_5GHZ_CHANNELS or \
               channel in BAND_6GHZ_CHANNELS

    def supports_band(self, band: str) -> bool:
        return band in ("2.4", "5", "6")
