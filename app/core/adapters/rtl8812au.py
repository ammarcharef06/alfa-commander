# ============================================================
# Alfa Commander - RTL8812AU Adapter (AWUS036ACH/AC)
# شريحة الجيل الانتقالي (تحتاج تعريف خارجي)
# ============================================================

from __future__ import annotations

from pathlib import Path

from app.core.adapters.base_adapter import BaseAlfaAdapter
from app.core.tools import iw
from app.utils.shell import run
from app.logger import get_logger

logger = get_logger()


class RTL8812AUAdapter(BaseAlfaAdapter):
    """
    محول AWUS036ACH / AWUS036AC (RTL8812AU).

    ملاحظات:
    - يحتاج تعريف خارجي (8812au من DKMS).
    - يدعم 2.4 و 5GHz.
    - حقن ممتاز عند تثبيت التعريف الصحيح.
    - قد يحتاج إعادة تشغيل الخدمات بعد تثبيت التعريف.
    """

    MODEL = "AWUS036ACH"
    CHIPSET = "RTL8812AU"
    USB_IDS = ["0bda:8812", "0bda:8813"]
    DEFAULT_BANDS = ["2.4", "5"]
    DEFAULT_DRIVER = "8812au"
    DRIVER_TYPE = "external"
    MAX_STANDARD = "802.11ac"
    MIN_KERNEL = None
    SUPPORTS_5GHZ = True
    SUPPORTS_6GHZ = False

    KNOWN_ISSUES = [
        "يحتاج تثبيت تعريف خارجي (8812au من DKMS).",
        "قد لا يعمل مباشرة بعد التوصيل إن لم يُثبّت التعريف.",
        "تحديث النواة قد يتطلب إعادة بناء التعريف.",
    ]

    USAGE_NOTES = [
        "يدعم 5GHz، لذا يمكنه رؤية ومهاجمة الشبكات الحديثة.",
        "مثالي لالتقاط PMKID على 5GHz.",
        "يعمل مع mdk4 بشكل ممتاز.",
    ]

    # ============================================================
    # فحص إضافي: هل التعريف الخارجي مثبت؟
    # ============================================================
    def is_driver_installed(self) -> bool:
        """فحص تثبيت تعريف 8812au عبر DKMS."""
        try:
            result = run(["dkms", "status"])
            if "8812au" in result.stdout or "rtl8812au" in result.stdout:
                return True
        except Exception:
            pass

        # فحص الوحدة في النواة
        result = run(["modinfo", "8812au"])
        return result.ok

    def install_driver_instructions(self) -> str:
        return (
            "لتثبيت التعريف:\n"
            "  sudo apt install -y git dkms\n"
            "  git clone https://github.com/aircrack-ng/rtl8812au.git\n"
            "  cd rtl8812au\n"
            "  sudo make dkms_install"
        )

    # ============================================================
    # وضع المراقبة
    # ============================================================
    def enter_monitor_mode(self) -> bool:
        if not self.is_driver_installed():
            msg = "[AWUS036ACH] التعريف الخارجي 8812au غير مثبت!"
            logger.error(msg)
            if msg not in self.warnings:
                self.warnings.append(msg)
            return False

        logger.info(f"[{self.MODEL}] تفعيل وضع المراقبة...")

        # المحاولة عبر airmon-ng أولاً
        monitor_iface = self._run_airmon_start()
        if monitor_iface and self._verify_monitor_mode(monitor_iface):
            return True

        # fallback إلى iw
        logger.info(f"[{self.MODEL}] محاولة عبر iw...")
        return self._run_iw_monitor()

    def exit_monitor_mode(self) -> bool:
        if self.monitor_interface:
            return self._run_airmon_stop()
        return self._run_iw_managed()

    def _verify_monitor_mode(self, iface: str) -> bool:
        info = iw.get_info(iface)
        return bool(info and info.type == "monitor")

    # ============================================================
    # الحقن
    # ============================================================
    def validate_injection(self) -> int:
        logger.info(f"[{self.MODEL}] اختبار الحقن...")
        ratio = self._run_injection_test()

        if ratio < 30:
            logger.warning(f"[{self.MODEL}] نسبة الحقن ضعيفة ({ratio}%).")

        return ratio

    # ============================================================
    # القدرات
    # ============================================================
    def supports_channel(self, channel: int) -> bool:
        from app.constants import BAND_2GHZ_CHANNELS, BAND_5GHZ_CHANNELS
        return channel in BAND_2GHZ_CHANNELS or channel in BAND_5GHZ_CHANNELS

    def supports_band(self, band: str) -> bool:
        return band in ("2.4", "5")
