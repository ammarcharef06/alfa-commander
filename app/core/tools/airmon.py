# ============================================================
# Alfa Commander - airmon-ng Wrapper
# إدارة وضع المراقبة مع وعي بالشرائح
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.utils.shell import run, CommandResult, command_exists
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نماذج
# ------------------------------------------------------------
@dataclass
class MonitorResult:
    success: bool
    interface: Optional[str] = None         # wlan0mon
    original_interface: Optional[str] = None
    output: str = ""
    error: str = ""


# ------------------------------------------------------------
# الخدمات المتعارضة الشائعة
# ------------------------------------------------------------
CONFLICTING_SERVICES = [
    "NetworkManager",
    "wpa_supplicant",
    "wpa_supplicant.service",
    "avahi-daemon",
    "dhclient",
    "dhcpcd",
]


# ------------------------------------------------------------
# غلاف airmon-ng
# ------------------------------------------------------------
class Airmon:
    BINARY = "airmon-ng"

    @staticmethod
    def is_available() -> bool:
        return command_exists(Airmon.BINARY)

    # ---------- فحص ----------
    @staticmethod
    def check() -> CommandResult:
        return run([Airmon.BINARY, "check"])

    @staticmethod
    def check_kill() -> CommandResult:
        """إيقاف الخدمات المتعارضة."""
        logger.info("إيقاف الخدمات المتعارضة...")
        return run([Airmon.BINARY, "check", "kill"], timeout=15)

    # ---------- تفعيل المراقبة ----------
    @staticmethod
    def start(iface: str, channel: Optional[int] = None) -> MonitorResult:
        """
        تفعيل وضع المراقبة.
        يرجع MonitorResult باسم الواجهة الجديدة (عادة wlan0mon).
        """
        args = [Airmon.BINARY, "start", iface]
        if channel:
            args.extend([str(channel)])

        result = run(args, timeout=20)

        if not result.ok:
            logger.error(f"فشل تفعيل المراقبة: {result.stderr}")
            return MonitorResult(
                success=False,
                original_interface=iface,
                output=result.stdout,
                error=result.stderr,
            )

        # استخراج اسم الواجهة الجديدة
        monitor_iface = Airmon._extract_monitor_iface(result.stdout)
        if monitor_iface is None:
            # بعض الشرائح تحتفظ بنفس الاسم
            if "monitor mode" in result.stdout.lower():
                monitor_iface = iface

        if monitor_iface:
            logger.info(f"تم تفعيل المراقبة على {monitor_iface}")
            return MonitorResult(
                success=True,
                interface=monitor_iface,
                original_interface=iface,
                output=result.stdout,
            )

        return MonitorResult(
            success=False,
            original_interface=iface,
            output=result.stdout,
            error="لم يتم استخراج اسم واجهة المراقبة",
        )

    @staticmethod
    def stop(monitor_iface: str) -> CommandResult:
        """تعطيل وضع المراقبة."""
        result = run([Airmon.BINARY, "stop", monitor_iface], timeout=15)
        if result.ok:
            logger.info(f"تم تعطيل المراقبة على {monitor_iface}")
        return result

    @staticmethod
    def _extract_monitor_iface(output: str) -> Optional[str]:
        """استخراج اسم واجهة المراقبة من مخرجات airmon-ng."""
        # مثال: "monitor mode vif enabled for [phy0]wlan0 on [phy0]wlan0mon"
        patterns = [
            r"monitor mode.*enabled.*on\s+\[\w+\](\w+)",
            r"monitor mode.*enabled.*on\s+(\w+)",
            r"\(monitor mode enabled on (\w+)\)",
            r"\(monitor mode enabled\)",
        ]
        for pattern in patterns:
            m = re.search(pattern, output, re.IGNORECASE)
            if m:
                if m.lastindex:
                    return m.group(1)
        return None

    # ---------- قائمة الواجهات ----------
    @staticmethod
    def list_interfaces() -> list[dict]:
        """قائمة الواجهات اللاسلكية وحالتها."""
        result = run([Airmon.BINARY])
        interfaces = []
        for line in result.stdout.splitlines():
            # تنسيق: phy0 wlan0 ... driver
            m = re.match(r"(phy\d+)\s+(\S+)\s+(\S+)\s+(\S+)", line)
            if m:
                interfaces.append({
                    "phy": m.group(1),
                    "interface": m.group(2),
                    "chipset": m.group(3),
                    "driver": m.group(4),
                })
        return interfaces


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
def enter_monitor_mode(iface: str, channel: Optional[int] = None) -> MonitorResult:
    """تفعيل المراقبة مع إيقاف الخدمات المتعارضة أولاً."""
    Airmon.check_kill()
    return Airmon.start(iface, channel)


def exit_monitor_mode(monitor_iface: str):
    """تعطيل المراقبة وإعادة تشغيل NetworkManager."""
    Airmon.stop(monitor_iface)
    run(["systemctl", "restart", "NetworkManager"])


# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def check():
    return Airmon.check()


def check_kill():
    return Airmon.check_kill()


def start(iface: str, channel=None):
    return Airmon.start(iface, channel)


def stop(monitor_iface: str):
    return Airmon.stop(monitor_iface)


def list_interfaces():
    return Airmon.list_interfaces()

