# ============================================================
# Alfa Commander - Adapter Detector
# التعرف التلقائي على محولات Alfa
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.adapters.base_adapter import BaseAlfaAdapter
from app.core.adapters.registry import (
    ADAPTER_REGISTRY,
    get_adapter_class,
    is_supported_usb_id,
)
from app.core.tools import ip, iw
from app.utils.shell import run, command_exists
from app.utils.validators import is_valid_mac
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# بيانات USB الخام
# ------------------------------------------------------------
@dataclass
class UsbDevice:
    usb_id: str            # "0bda:8187"
    bus: str = ""
    device: str = ""
    description: str = ""
    vendor: str = ""
    product: str = ""


@dataclass
class DetectedAdapter:
    """محول مكتشف قبل أن يصبح كائن كامل."""
    usb_device: UsbDevice
    interface: Optional[str] = None
    mac: Optional[str] = None
    phy: Optional[str] = None
    driver: Optional[str] = None
    is_alfa: bool = False
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------
# المكتشف
# ------------------------------------------------------------
class AdapterDetector:
    """
    يكتشف محولات Alfa المتصلة:
    1) يسأل lsusb عن كل الأجهزة.
    2) يطابق VID:PID مع السجل.
    3) يربط كل USB ID بواجهة شبكة.
    4) يُنشئ كائن AlfaAdapter المناسب.
    """

    @staticmethod
    def detect_all() -> list[BaseAlfaAdapter]:
        """يكتشف ويرجع قائمة بكل محولات Alfa المتصلة."""
        detected = AdapterDetector._scan_usb()
        adapters: list[BaseAlfaAdapter] = []

        for det in detected:
            if not det.is_alfa:
                continue
            if not det.interface:
                logger.warning(
                    f"محول Alfa {det.usb_device.usb_id} موجود لكن بدون واجهة شبكة"
                )
                continue

            cls = get_adapter_class(det.usb_device.usb_id)
            if cls is None:
                logger.warning(f"USB ID غير مسجل: {det.usb_device.usb_id}")
                continue

            try:
                adapter = cls(
                    interface=det.interface,
                    mac=det.mac or "",
                    usb_id=det.usb_device.usb_id,
                )
                adapter.warnings.extend(det.warnings)
                adapters.append(adapter)
                logger.info(
                    f"تم اكتشاف {adapter.MODEL} ({adapter.CHIPSET}) على {det.interface}"
                )
            except Exception as e:
                logger.exception(f"فشل إنشاء كائن المحول: {e}")

        return adapters

    # ---------- فحص USB ----------
    @staticmethod
    def _scan_usb() -> list[DetectedAdapter]:
        """قراءة lsusb وربط الأجهزة بالواجهات."""
        if not command_exists("lsusb"):
            logger.error("lsusb غير مثبت")
            return []

        result = run(["lsusb"])
        if not result.ok:
            logger.error(f"فشل lsusb: {result.stderr}")
            return []

        usb_devices = AdapterDetector._parse_lsusb(result.stdout)
        detected: list[DetectedAdapter] = []

        for dev in usb_devices:
            det = DetectedAdapter(usb_device=dev)
            det.is_alfa = is_supported_usb_id(dev.usb_id)

            if det.is_alfa:
                # نحاول إيجاد الواجهة المرتبطة
                iface, mac, phy, driver = AdapterDetector._find_interface_for_usb(dev)
                det.interface = iface
                det.mac = mac
                det.phy = phy
                det.driver = driver

                if not iface:
                    det.warnings.append(
                        "لم يتم العثور على واجهة شبكة. "
                        "قد يكون التعريف غير محمل أو الجهاز غير مدعوم."
                    )

            detected.append(det)

        return detected

    @staticmethod
    def _parse_lsusb(output: str) -> list[UsbDevice]:
        """تحليل مخرجات lsusb."""
        devices: list[UsbDevice] = []
        pattern = re.compile(
            r"Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\s*(.*)"
        )
        for line in output.splitlines():
            m = pattern.match(line.strip())
            if not m:
                continue
            devices.append(UsbDevice(
                bus=m.group(1),
                device=m.group(2),
                usb_id=m.group(3).lower(),
                description=m.group(4).strip(),
            ))
        return devices

    # ---------- ربط USB بالواجهة ----------
    @staticmethod
    def _find_interface_for_usb(dev: UsbDevice) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        يبحث عن واجهة الشبكة المرتبطة بجهاز USB معين.
        يعتمد على /sys/class/net/*/device/uevent.
        """
        iface = None
        mac = None
        phy = None
        driver = None

        net_dir = Path("/sys/class/net")
        if not net_dir.exists():
            return None, None, None, None

        for iface_path in net_dir.iterdir():
            iface_name = iface_path.name
            if iface_name == "lo":
                continue

            # فحص إذا كانت الواجهة لاسلكية
            wireless_dir = iface_path / "wireless"
            if not wireless_dir.exists():
                continue

            # اقرأ الـ uevent للتحقق من USB ID
            uevent_file = iface_path / "device" / "uevent"
            if not uevent_file.exists():
                continue

            try:
                content = uevent_file.read_text(errors="ignore").upper()
            except Exception:
                continue

            # البحث عن VID:PID
            vid_match = re.search(r"PRODUCT=([0-9A-F]+)/([0-9A-F]+)/", content)
            if not vid_match:
                continue

            vid = vid_match.group(1).lower().zfill(4)
            pid = vid_match.group(2).lower().zfill(4)
            found_usb_id = f"{vid}:{pid}"

            if found_usb_id != dev.usb_id:
                continue

            # وجدناه!
            iface = iface_name
            mac = ip.get_interface_mac(iface_name)

            # PHY
            phy_link = iface_path / "phy80211"
            if phy_link.exists():
                try:
                    phy = phy_link.resolve().name
                except Exception:
                    phy = None

            # Driver
            driver_link = iface_path / "device" / "driver"
            if driver_link.exists():
                try:
                    driver = driver_link.resolve().name
                except Exception:
                    driver = None

            break

        return iface, mac, phy, driver

    # ---------- دوال مساعدة ----------
    @staticmethod
    def detect_and_report() -> list[dict]:
        """يكتشف كل محولات Alfa ويعيدها كتقارير dict."""
        adapters = AdapterDetector.detect_all()
        return [a.describe() for a in adapters]

    @staticmethod
    def get_interface_to_usb_map() -> dict[str, str]:
        """
        يرجع dict: اسم واجهة → USB ID.
        مفيد لمعرفة أي USB ID مرتبط بأي واجهة.
        """
        mapping = {}
        for det in AdapterDetector._scan_usb():
            if det.interface:
                mapping[det.interface] = det.usb_device.usb_id
        return mapping

    @staticmethod
    def diagnose_missing_adapter(usb_id: str) -> str:
        """
        إذا لم يتم العثور على الواجهة، نقدم تشخيصاً مفيداً.
        """
        cls = get_adapter_class(usb_id)
        if cls is None:
            return f"USB ID غير معروف: {usb_id}"

        lines = [f"تشخيص المحول {cls.MODEL} ({cls.CHIPSET}):"]

        if cls.DRIVER_TYPE == "external":
            lines.append(f"  ⚠ يحتاج تعريف خارجي: {cls.DEFAULT_DRIVER}")
            lines.append("  جرّب تثبيت التعريف ثم أعد توصيل الجهاز.")

        if cls.MIN_KERNEL:
            import platform
            current = platform.release().split("-")[0]
            lines.append(f"  ⚠ إصدار النواة الحالي: {current}")
            lines.append(f"  ⚠ المطلوب: {cls.MIN_KERNEL}+")

        lines.append("  خطوات مقترحة:")
        lines.append("    1) تأكد من تحميل التعريف: lsmod | grep " + cls.DEFAULT_DRIVER.split("_")[0])
        lines.append("    2) افحص dmesg: dmesg | tail -50")
        lines.append("    3) أعد توصيل الجهاز")
        lines.append("    4) أعد تشغيل الخدمات: sudo systemctl restart NetworkManager")

        return "\n".join(lines)


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
def detect_adapters() -> list[BaseAlfaAdapter]:
    return AdapterDetector.detect_all()


def detect_and_describe() -> list[dict]:
    return AdapterDetector.detect_and_report()
