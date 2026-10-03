# ============================================================
# Alfa Commander - RTL8187L Adapter (AWUS036H)
# شريحة الجيل الكلاسيكي
# ============================================================

from __future__ import annotations

from typing import Optional

from app.core.adapters.base_adapter import BaseAlfaAdapter
from app.core.tools import iw
from app.logger import get_logger

logger = get_logger()


class RTL8187Adapter(BaseAlfaAdapter):
    """
    محول AWUS036H (RTL8187L).

    ملاحظات مهمة:
    - يدعم 2.4GHz فقط.
    - الحقن ضعيف في البيئات المزدحمة.
    - يحتاج أحياناً --ignore-negative-one.
    - لا يدعم 5GHz إطلاقاً.
    """

    MODEL = "AWUS036H"
    CHIPSET = "RTL8187L"
    USB_IDS = ["0bda:8187", "0bda:8189"]
    DEFAULT_BANDS = ["2.4"]
    DEFAULT_DRIVER = "rtl8187"
    DRIVER_TYPE = "in-kernel"
    MAX_STANDARD = "802.11g"
    MIN_KERNEL = None
    SUPPORTS_5GHZ = False
    SUPPORTS_6GHZ = False

    KNOWN_ISSUES = [
        "يدعم 2.4GHz فقط، لا يمكنه رؤية شبكات 5GHz.",
        "قد يحتاج --ignore-negative-one في aireplay-ng.",
        "نسبة الحقن تنخفض في البيئات المزدحمة (أقل من 30%).",
        "لا يدعم 802.11n/ac، لذا السرعة القصوى 54 Mbps.",
    ]

    USAGE_NOTES = [
        "مثالي لاختبار شبكات 2.4GHz القديمة.",
        "يُفضل استخدام Deauth بعدد منخفض لتفادي الفشل.",
        "استخدم hcxdumptool بدلاً من aireplay للـ PMKID إن أمكن.",
    ]

    # ============================================================
    # وضع المراقبة
    # ============================================================
    def enter_monitor_mode(self) -> bool:
        """
        تفعيل المراقبة.
        RTL8187 يدعم airmon-ng مباشرة، لكن أحياناً يعطي اسم واجهة غير متوقع.
        """
        logger.info(f"[{self.MODEL}] تفعيل وضع المراقبة على {self.interface}")

        # المحاولة عبر airmon-ng
        monitor_iface = self._run_airmon_start()
        if monitor_iface:
            # بعض الإصدارات القديمة من airmon-ng قد لا تعيد الاسم الصحيح
            if not self._verify_monitor_mode(monitor_iface):
                logger.warning(f"[{self.MODEL}] airmon-ng لم يُفعّل المراقبة، تجربة iw...")
                if self._run_iw_monitor():
                    return True
                return False
            return True

        # المحاولة عبر iw
        logger.info(f"[{self.MODEL}] محاولة تفعيل المراقبة عبر iw مباشرة...")
        return self._run_iw_monitor()

    def exit_monitor_mode(self) -> bool:
        logger.info(f"[{self.MODEL}] تعطيل وضع المراقبة")
        if self.monitor_interface:
            return self._run_airmon_stop()
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
        RTL8187L معروف بنسب حقن منخفضة في البيئات المزدحمة.
        """
        logger.info(f"[{self.MODEL}] اختبار الحقن...")
        ratio = self._run_injection_test()

        if ratio < 15:
            warning = (
                f"[{self.MODEL}] نسبة الحقن ضعيفة ({ratio}%). "
                "قد تفشل هجمات Deauth. جرّب الاقتراب من الهدف أو تغيير القناة."
            )
            logger.warning(warning)
            if warning not in self.warnings:
                self.warnings.append(warning)
        elif ratio < 30:
            logger.info(f"[{self.MODEL}] نسبة الحقن متوسطة ({ratio}%).")

        return ratio

    # ============================================================
    # ضبط Deauth
    # ============================================================
    def recommended_deauth_count(self) -> int:
        """
        عدد Deauth الموصى به بناءً على نسبة الحقن.
        RTL8187L يفشل في الحقن إذا أرسلت حزماً كثيرة بسرعة.
        """
        if self.injection_ratio >= 50:
            return 5
        if self.injection_ratio >= 30:
            return 10
        if self.injection_ratio >= 15:
            return 15
        return 0  # لا يُنصح بـ Deauth

    def recommended_deauth_interval(self) -> int:
        """الفاصل الزمني الموصى به بين حزم Deauth."""
        if self.injection_ratio >= 50:
            return 1
        if self.injection_ratio >= 30:
            return 2
        return 3

    # ============================================================
    # قيود
    # ============================================================
    def get_capabilities(self):
        caps = super().get_capabilities()
        # تأكيد أن 5GHz و 6GHz غير مدعومين
        caps.supports_5ghz = False
        caps.supports_6ghz = False
        caps.bands = ["2.4"]
        return caps

    def supports_channel(self, channel: int) -> bool:
        """هل يدعم القناة المعطاة؟"""
        from app.constants import BAND_2GHZ_CHANNELS
        return channel in BAND_2GHZ_CHANNELS

    def supports_band(self, band: str) -> bool:
        return band == "2.4"
