# ============================================================
# Alfa Commander - Ralink RT3070 Adapter
# شريحة Ralink RT2870/RT3070 (شائعة جداً في محولات Alfa)
# AWUS036NH / AWUS036NEH / AWUS051NH
# ============================================================

from __future__ import annotations

from typing import Optional

from app.core.adapters.base_adapter import BaseAlfaAdapter
from app.core.tools import iw
from app.logger import get_logger

logger = get_logger()


class RT3070Adapter(BaseAlfaAdapter):
    """
    محول Ralink RT2870/RT3070 (AWUS036NH / AWUS036NEH).

    ملاحظات مهمة:
    - شريحة قديمة لكن مستقرة جداً على Linux.
    - التعريف rt2800usb مدمج في النواة.
    - يدعم 2.4GHz فقط (802.11n حتى 150Mbps).
    - حقن ممتاز (غالباً 90%+) في البيئات الجيدة.
    - لا يدعم 5GHz إطلاقاً.
    - يدعم Monitor Mode و Injection بشكل ممتاز.
    """

    MODEL = "AWUS036NH"
    CHIPSET = "RT3070"
    USB_IDS = ["148f:3070", "148f:2870", "148f:3572", "148f:3071"]
    DEFAULT_BANDS = ["2.4"]
    DEFAULT_DRIVER = "rt2800usb"
    DRIVER_TYPE = "in-kernel"
    MAX_STANDARD = "802.11n"
    MIN_KERNEL = "2.6.31"
    SUPPORTS_5GHZ = False
    SUPPORTS_6GHZ = False

    KNOWN_ISSUES = [
        "يدعم 2.4GHz فقط، لا يمكنه رؤية شبكات 5GHz.",
        "أقصى سرعة 150 Mbps (802.11n أحادي السلسلة).",
        "بعض النسخ المقلدة تحمل نفس VID:PID لكن بأداء مختلف.",
    ]

    USAGE_NOTES = [
        "من أكثر الشرائح استقراراً على Linux.",
        "حقن ممتاز، مثالي لهجمات Deauth و WPS.",
        "يعمل مباشرة دون تثبيت أي تعريف.",
        "مثالي لـ Raspberry Pi والأنظمة المدمجة.",
    ]

    # ============================================================
    # وضع المراقبة
    # ============================================================
    def enter_monitor_mode(self) -> bool:
        """
        تفعيل المراقبة.
        RT3070 يدعم airmon-ng و iw بشكل ممتاز.
        """
        logger.info(f"[{self.MODEL}] تفعيل وضع المراقبة على {self.interface}")

        # المحاولة الأولى: airmon-ng
        monitor_iface = self._run_airmon_start()
        if monitor_iface and self._verify_monitor_mode(monitor_iface):
            logger.info(f"[{self.MODEL}] airmon-ng نجح: {monitor_iface}")
            return True

        # المحاولة الثانية: iw مباشرة
        logger.info(f"[{self.MODEL}] محاولة تفعيل المراقبة عبر iw...")
        if self._run_iw_monitor():
            # تفعيل Active Monitor إن أمكن (مفيد للـ RT3070)
            self._enable_active_monitor()
            return True

        logger.error(f"[{self.MODEL}] فشل تفعيل المراقبة")
        return False

    def _enable_active_monitor(self):
        """تفعيل Active Monitor للاستكشاف التلقائي."""
        from app.utils.shell import run
        active = run([
            "iw", self.get_active_interface(),
            "set", "monitor", "active"
        ])
        if active.ok:
            logger.info(f"[{self.MODEL}] تم تفعيل Active Monitor")

    def exit_monitor_mode(self) -> bool:
        logger.info(f"[{self.MODEL}] تعطيل وضع المراقبة")
        if self.monitor_interface:
            if self._run_airmon_stop():
                return True
        return self._run_iw_managed()

    def _verify_monitor_mode(self, iface: str) -> bool:
        """التحقق من أن الواجهة فعلاً في وضع المراقبة."""
        info = iw.get_info(iface)
        return bool(info and info.type == "monitor")

    # ============================================================
    # اختبار الحقن
    # ============================================================
    def validate_injection(self) -> int:
        """
        اختبار الحقن.
        RT3070 معروف بنسب حقن ممتازة (غالباً > 80%).
        """
        logger.info(f"[{self.MODEL}] اختبار الحقن...")

        # تأكد من أن الواجهة في وضع monitor
        iface = self.get_active_interface()
        if "mon" not in iface and not self.is_monitor():
            logger.warning(f"[{self.MODEL}] الواجهة ليست monitor — تفعيل تلقائي")
            if not self.enter_monitor_mode():
                logger.error(f"[{self.MODEL}] فشل تفعيل المراقبة")
                return 0
            iface = self.get_active_interface()

        ratio = self._run_injection_test()

        if ratio >= 80:
            logger.info(f"[{self.MODEL}] الحقن ممتاز: {ratio}%")
        elif ratio >= 50:
            logger.info(f"[{self.MODEL}] الحقن جيد: {ratio}%")
        elif ratio >= 15:
            logger.warning(f"[{self.MODEL}] الحقن ضعيف: {ratio}%")
            if "ضعف الحقن" not in " ".join(self.warnings):
                self.warnings.append(
                    f"نسبة الحقن منخفضة ({ratio}%). "
                    "قد تحتاج الاقتراب من الهدف."
                )
        else:
            logger.error(f"[{self.MODEL}] الحقن معطل: {ratio}%")
            self.warnings.append(
                "الحقن لا يعمل. راجع مخرجات aireplay-ng --test. "
                "على VMware، قد لا يعمل الحقن بشكل كامل."
            )

        return ratio

    # ============================================================
    # توصيات خاصة بالشريحة
    # ============================================================
    def recommended_deauth_count(self) -> int:
        """RT3070 يدعم Deauth بقوة، لذا أعداد منخفضة كافية."""
        if self.injection_ratio >= 80:
            return 3
        if self.injection_ratio >= 50:
            return 5
        if self.injection_ratio >= 30:
            return 8
        return 15

    def recommended_deauth_interval(self) -> int:
        return 1

    # ============================================================
    # القيود
    # ============================================================
    def get_capabilities(self):
        caps = super().get_capabilities()
        caps.supports_5ghz = False
        caps.supports_6ghz = False
        caps.bands = ["2.4"]
        caps.max_standard = "802.11n"
        return caps

    def supports_channel(self, channel: int) -> bool:
        """RT3070 يدعم قنوات 2.4GHz فقط (1-14)."""
        from app.constants import BAND_2GHZ_CHANNELS
        return channel in BAND_2GHZ_CHANNELS

    def supports_band(self, band: str) -> bool:
        return band == "2.4"
