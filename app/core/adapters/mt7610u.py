# ============================================================
# Alfa Commander - MT7610U Adapter (AWUS036ACHM/ACM)
# شريحة الجيل الحديث المدمجة في النواة
# ============================================================

from __future__ import annotations

from app.core.adapters.base_adapter import BaseAlfaAdapter
from app.core.tools import iw
from app.logger import get_logger

logger = get_logger()


class MT7610UAdapter(BaseAlfaAdapter):
    """
    محول AWUS036ACHM / AWUS036ACM (MT7610U/MT7612U).

    - التعريف مدمج في النواة منذ 2018.
    - يعمل بمجرد التوصيل.
    - يدعم وضع Monitor نشط (Active Monitor).
    - مشاكل معروفة على معالجات ARM.
    """

    MODEL = "AWUS036ACHM"
    CHIPSET = "MT7610U"
    USB_IDS = ["0e8d:7610", "0e8d:7612"]
    DEFAULT_BANDS = ["2.4", "5"]
    DEFAULT_DRIVER = "mt76x0u"
    DRIVER_TYPE = "in-kernel"
    MAX_STANDARD = "802.11ac"
    MIN_KERNEL = "4.19"
    SUPPORTS_5GHZ = True
    SUPPORTS_6GHZ = False

    KNOWN_ISSUES = [
        "على معالجات ARM (Raspberry Pi)، قد يفشل وضع Active Monitor.",
        "بعض إصدارات النواة القديمة تحتاج حزمة firmware إضافية.",
    ]

    USAGE_NOTES = [
        "أفضل محول Alfa من حيث التوافق المباشر مع Linux.",
        "لا يحتاج تثبيت أي تعريف.",
        "مثالي للتجارب على أجهزة Raspberry Pi.",
    ]

    # ============================================================
    # وضع المراقبة - MT7610U يدعم Active Monitor
    # ============================================================
    def enter_monitor_mode(self) -> bool:
        logger.info(f"[{self.MODEL}] تفعيل وضع المراقبة...")

        # بعض إصدارات airmon-ng تسبب مشاكل مع mt76، لذا نفضل iw
        if self._run_iw_monitor():
            # تفعيل Active Monitor إن أمكن
            self._enable_active_monitor()
            return True

        # fallback إلى airmon-ng
        monitor_iface = self._run_airmon_start()
        return bool(monitor_iface)

    def _enable_active_monitor(self):
        """
        تفعيل Active Monitor على mt76.
        يسمح للواجهة بإرسال حزم استكشاف بشكل دوري.
        """
        from app.utils.shell import run
        active = run(["iw", self.get_active_interface(), "set", "monitor", "active"])
        if active.ok:
            logger.info(f"[{self.MODEL}] تم تفعيل Active Monitor")
        else:
            logger.debug(f"[{self.MODEL}] Active Monitor غير مدعوم على هذه البيئة")

    def exit_monitor_mode(self) -> bool:
        return self._run_iw_managed()

    def validate_injection(self) -> int:
        logger.info(f"[{self.MODEL}] اختبار الحقن...")
        return self._run_injection_test()

    def supports_channel(self, channel: int) -> bool:
        from app.constants import BAND_2GHZ_CHANNELS, BAND_5GHZ_CHANNELS
        return channel in BAND_2GHZ_CHANNELS or channel in BAND_5GHZ_CHANNELS

    def supports_band(self, band: str) -> bool:
        return band in ("2.4", "5")
