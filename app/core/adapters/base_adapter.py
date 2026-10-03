# ============================================================
# Alfa Commander - Base Adapter (Abstract)
# الصنف المجرد لكل محولات Alfa
# ============================================================

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.constants import AdapterState
from app.core.tools import iw, ip, airmon, aireplay
from app.utils.shell import run, command_exists
from app.utils.validators import is_valid_mac, normalize_mac
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نموذج نتيجة فحص الجاهزية
# ------------------------------------------------------------
@dataclass
class ReadinessReport:
    ready: bool = False
    driver_loaded: bool = False
    firmware_ok: bool = False
    monitor_supported: bool = False
    injection_supported: bool = False
    injection_ratio: int = 0
    bands_available: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class AdapterCapabilities:
    """قدرات المحول الكاملة."""
    bands: list[str] = field(default_factory=list)
    supports_monitor: bool = False
    supports_injection: bool = False
    supports_ap: bool = False
    supports_mesh: bool = False
    supports_5ghz: bool = False
    supports_6ghz: bool = False
    max_channel_width: int = 20          # MHz
    max_standard: str = "802.11g"
    driver_type: str = "in-kernel"       # in-kernel / external
    requires_external_driver: bool = False
    min_kernel: Optional[str] = None


# ------------------------------------------------------------
# الصنف المجرد
# ------------------------------------------------------------
class BaseAlfaAdapter(ABC):
    """
    الصنف الأساسي لكل محولات Alfa.
    كل شريحة ترث منه وتنفذ الأساليب المجردة.
    """

    # --- خصائص يتعين على كل شريحة تعريفها ---
    MODEL: str = "Unknown"
    CHIPSET: str = "Unknown"
    USB_IDS: list[str] = []                  # ["0bda:8187"]
    DEFAULT_BANDS: list[str] = ["2.4"]
    DEFAULT_DRIVER: str = ""
    DRIVER_TYPE: str = "in-kernel"
    MAX_STANDARD: str = "802.11g"
    MIN_KERNEL: Optional[str] = None
    SUPPORTS_5GHZ: bool = False
    SUPPORTS_6GHZ: bool = False
    SUPPORTS_MONITOR: bool = True
    SUPPORTS_INJECTION: bool = True
    SUPPORTS_AP: bool = True

    # ملاحظات معروفة تُعرض للمستخدم
    KNOWN_ISSUES: list[str] = []
    USAGE_NOTES: list[str] = []

    def __init__(self, interface: str, mac: str = "", usb_id: str = ""):
        self.interface = interface
        self.monitor_interface: Optional[str] = None
        self.mac = normalize_mac(mac) if mac and is_valid_mac(mac) else ""
        self.usb_id = usb_id
        self.state = AdapterState.CONNECTED
        self.injection_ratio: int = 0
        self.warnings: list[str] = []
        self._original_mode: str = "managed"

    # ============================================================
    # أساليب مجردة يجب على كل شريحة تنفيذها
    # ============================================================
    @abstractmethod
    def enter_monitor_mode(self) -> bool:
        """تفعيل وضع المراقبة. يجب أن يعيد True عند النجاح."""
        pass

    @abstractmethod
    def exit_monitor_mode(self) -> bool:
        """تعطيل وضع المراقبة والعودة إلى managed."""
        pass

    @abstractmethod
    def validate_injection(self) -> int:
        """اختبار الحقن. يعيد نسبة الحقن %."""
        pass

    # ============================================================
    # أساليب مشتركة (يمكن تجاوزها في الشرائح الخاصة)
    # ============================================================
    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            bands=self.DEFAULT_BANDS.copy(),
            supports_monitor=self.SUPPORTS_MONITOR,
            supports_injection=self.SUPPORTS_INJECTION,
            supports_ap=self.SUPPORTS_AP,
            supports_5ghz=self.SUPPORTS_5GHZ,
            supports_6ghz=self.SUPPORTS_6GHZ,
            max_standard=self.MAX_STANDARD,
            driver_type=self.DRIVER_TYPE,
            requires_external_driver=self.DRIVER_TYPE == "external",
            min_kernel=self.MIN_KERNEL,
        )

    def is_monitor(self) -> bool:
        """هل الواجهة حالياً في وضع المراقبة؟"""
        if self.monitor_interface:
            info = iw.get_info(self.monitor_interface)
            if info and info.type == "monitor":
                return True
        info = iw.get_info(self.interface)
        return bool(info and info.type == "monitor")

    def get_active_interface(self) -> str:
        """يرجع واجهة المراقبة إن وُجدت، وإلا الواجهة الأساسية."""
        return self.monitor_interface or self.interface

    def get_current_channel(self) -> Optional[int]:
        return iw.get_channel(self.get_active_interface())

    def set_channel(self, channel: int) -> bool:
        result = iw.set_channel(self.get_active_interface(), channel)
        return result.ok

    def set_txpower(self, dbm: int) -> bool:
        result = iw.set_txpower(self.get_active_interface(), dbm)
        return result.ok

    def get_mac(self) -> Optional[str]:
        if not self.mac:
            self.mac = ip.get_interface_mac(self.interface) or ""
        return self.mac or None

    # ============================================================
    # فحص الجاهزية الشامل
    # ============================================================
    def check_readiness(self, test_injection: bool = True) -> ReadinessReport:
        """
        فحص شامل لجاهزية المحول قبل أي عملية هجوم.
        """
        report = ReadinessReport()

        # 1) فحص وجود الواجهة
        if not ip.get_link(self.interface):
            report.errors.append(f"الواجهة {self.interface} غير موجودة")
            return report

        # 2) فحص تحميل التعريف
        report.driver_loaded = self._check_driver_loaded()
        if not report.driver_loaded:
            report.errors.append(f"تعريف {self.DEFAULT_DRIVER} غير محمل")

        # 3) فحص إصدار النواة
        if self.MIN_KERNEL and not self._check_kernel_version():
            report.warnings.append(
                f"يحتاج إصدار نواة >= {self.MIN_KERNEL}"
            )

        # 4) فحص قدرات phy
        info = iw.get_info(self.interface)
        if info:
            report.monitor_supported = "monitor" in (
                iw.get_phy_info(info.phy).supported_modes if info.phy else []
            )
            report.bands_available = info.bands

        # 5) اختبار الحقن (اختياري)
        if test_injection and report.monitor_supported:
            ratio = self.validate_injection()
            report.injection_ratio = ratio
            report.injection_supported = ratio > 0

        # 6) إضافة الملاحظات المعروفة
        report.warnings.extend(self.KNOWN_ISSUES)

        # 7) الحكم النهائي
        report.ready = (
            report.driver_loaded
            and report.monitor_supported
            and (not test_injection or report.injection_supported)
        )

        return report

    def _check_driver_loaded(self) -> bool:
        """فحص تحميل التعريف."""
        if not self.DEFAULT_DRIVER:
            return True

        # نتحقق من وجود الواجهة في /sys/class/net
        result = run(["lsmod"])
        # بعض الشرائح مدمجة، لذا نتحقق من وجود المجلد
        driver_link = Path(f"/sys/class/net/{self.interface}/device/driver")
        if driver_link.exists():
            try:
                driver_name = driver_link.resolve().name
                return self.DEFAULT_DRIVER.split("_")[0] in driver_name or driver_name in self.DEFAULT_DRIVER
            except Exception:
                pass

        return result.ok  # fallback: نعتبرها محملة إذا فشل الفحص

    def _check_kernel_version(self) -> bool:
        """فحص إصدار النواة."""
        if not self.MIN_KERNEL:
            return True
        try:
            import platform
            current = platform.release().split("-")[0]
            current_parts = [int(x) for x in current.split(".")[:2]]
            required_parts = [int(x) for x in self.MIN_KERNEL.split(".")[:2]]
            return current_parts >= required_parts
        except Exception:
            return True

    # ============================================================
    # أدوات مساعدة للأبناء
    # ============================================================
    def _run_airmon_start(self, channel: Optional[int] = None) -> Optional[str]:
        """تشغيل airmon-ng start وقراءة الواجهة الجديدة."""
        result = airmon.Airmon.start(self.interface, channel)
        if result.success:
            self.monitor_interface = result.interface
            self.state = AdapterState.MONITOR
            return result.interface
        return None

    def _run_airmon_stop(self) -> bool:
        """إيقاف المراقبة عبر airmon-ng."""
        if not self.monitor_interface:
            return True
        result = airmon.Airmon.stop(self.monitor_interface)
        if result.ok:
            self.monitor_interface = None
            self.state = AdapterState.MANAGED
            return True
        return False

    def _run_iw_monitor(self) -> bool:
        """تفعيل المراقبة عبر iw (للشرائح المدعومة في النواة)."""
        iface = self.interface
        iw.IW.set_interface_down(iface)
        result = iw.IW.set_monitor_mode(iface)
        iw.IW.set_interface_up(iface)
        if result.ok:
            self.monitor_interface = iface
            self.state = AdapterState.MONITOR
            return True
        return False

    def _run_iw_managed(self) -> bool:
        """العودة إلى managed عبر iw."""
        iface = self.get_active_interface()
        iw.IW.set_interface_down(iface)
        result = iw.IW.set_managed_mode(iface)
        iw.IW.set_interface_up(iface)
        if result.ok:
            self.monitor_interface = None
            self.state = AdapterState.MANAGED
            return True
        return False

    def _run_injection_test(self) -> int:
        """اختبار الحقن وإرجاع النسبة."""
        iface = self.get_active_interface()
        result = aireplay.Aireplay.test_injection(iface)
        self.injection_ratio = result.ratio
        return result.ratio

    # ============================================================
    # معلومات
    # ============================================================
    @property
    def id(self) -> str:
        """معرّف فريد للمحول (MAC أو الواجهة)."""
        return self.mac or self.interface

    def describe(self) -> dict:
        caps = self.get_capabilities()
        return {
            "id": self.id,
            "model": self.MODEL,
            "chipset": self.CHIPSET,
            "interface": self.interface,
            "monitor_interface": self.monitor_interface,
            "mac": self.mac,
            "usb_id": self.usb_id,
            "state": self.state,
            "bands": caps.bands,
            "max_standard": caps.max_standard,
            "driver": self.DEFAULT_DRIVER,
            "driver_type": caps.driver_type,
            "supports_monitor": caps.supports_monitor,
            "supports_injection": caps.supports_injection,
            "supports_ap": caps.supports_ap,
            "injection_ratio": self.injection_ratio,
            "known_issues": self.KNOWN_ISSUES,
            "usage_notes": self.USAGE_NOTES,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.MODEL} iface={self.interface} state={self.state}>"
