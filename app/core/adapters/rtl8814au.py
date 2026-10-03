# ============================================================
# Alfa Commander - RTL8814AU Adapter (AWUS1900)
# شريحة الجيل الانتقالي المتقدم
# ============================================================

from __future__ import annotations

from app.core.adapters.base_adapter import BaseAlfaAdapter
from app.core.tools import iw
from app.utils.shell import run
from app.logger import get_logger

logger = get_logger()


class RTL8814AUAdapter(BaseAlfaAdapter):
    """
    محول AWUS1900 (RTL8814AU).

    - يحتاج تعريف خارجي (8814au).
    - يدعم 2.4 و 5GHz.
    - 4 هوائيات: مدى استقبال استثنائي.
    - ممتاز للحقن والهجمات الميدانية.
    """

    MODEL = "AWUS1900"
    CHIPSET = "RTL8814AU"
    USB_IDS = ["0bda:8814"]
    DEFAULT_BANDS = ["2.4", "5"]
    DEFAULT_DRIVER = "8814au"
    DRIVER_TYPE = "external"
    MAX_STANDARD = "802.11ac"
    MIN_KERNEL = None
    SUPPORTS_5GHZ = True
    SUPPORTS_6GHZ = False

    KNOWN_ISSUES = [
        "يحتاج تعريف خارجي (8814au).",
        "يسحب طاقة كبيرة، يُفضل استخدامه مع USB 3.0.",
        "قد يسخن كثيراً في العمليات الطويلة.",
    ]

    USAGE_NOTES = [
        "أفضل محول Alfa لمدى الاستقبال.",
        "ممتاز لالتقاط الإشارات الضعيفة من مسافات بعيدة.",
        "يدعم الحقن بقوة عالية، مناسب لـ mdk4.",
    ]

    def is_driver_installed(self) -> bool:
        try:
            result = run(["dkms", "status"])
            if "8814au" in result.stdout or "rtl8814au" in result.stdout:
                return True
        except Exception:
            pass
        result = run(["modinfo", "8814au"])
        return result.ok

    def install_driver_instructions(self) -> str:
        return (
            "لتثبيت التعريف:\n"
            "  sudo apt install -y git dkms\n"
            "  git clone https://github.com/aircrack-ng/rtl8814au.git\n"
            "  cd rtl8814au\n"
            "  sudo make dkms_install"
        )

    def enter_monitor_mode(self) -> bool:
        if not self.is_driver_installed():
            msg = "[AWUS1900] التعريف الخارجي 8814au غير مثبت!"
            logger.error(msg)
            if msg not in self.warnings:
                self.warnings.append(msg)
            return False

        monitor_iface = self._run_airmon_start()
        if monitor_iface and self._verify_monitor_mode(monitor_iface):
            return True

        return self._run_iw_monitor()

    def exit_monitor_mode(self) -> bool:
        if self.monitor_interface:
            return self._run_airmon_stop()
        return self._run_iw_managed()

    def _verify_monitor_mode(self, iface: str) -> bool:
        info = iw.get_info(iface)
        return bool(info and info.type == "monitor")

    def validate_injection(self) -> int:
        logger.info(f"[{self.MODEL}] اختبار الحقن...")
        return self._run_injection_test()

    def supports_channel(self, channel: int) -> bool:
        from app.constants import BAND_2GHZ_CHANNELS, BAND_5GHZ_CHANNELS
        return channel in BAND_2GHZ_CHANNELS or channel in BAND_5GHZ_CHANNELS

    def supports_band(self, band: str) -> bool:
        return band in ("2.4", "5")
