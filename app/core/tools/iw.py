# ============================================================
# Alfa Commander - iw Wrapper
# التحكم بالواجهات اللاسلكية عبر iw
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.utils.shell import run, CommandResult, command_exists
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نماذج البيانات
# ------------------------------------------------------------
@dataclass
class WirelessInterface:
    name: str
    phy: str = ""
    type: str = ""              # managed / monitor / AP / ...
    channel: int = 0
    frequency: int = 0          # MHz
    txpower: float = 0.0        # dBm
    mac: str = ""
    ssid: str = ""
    driver: str = ""
    bands: list[str] = field(default_factory=list)
    supports_monitor: bool = False
    supports_ap: bool = False
    supports_mesh: bool = False
    is_up: bool = False


@dataclass
class PhyInfo:
    phy: str
    index: int
    name: str = ""
    addresses: list[str] = field(default_factory=list)
    bands: list[str] = field(default_factory=list)
    supported_ciphers: list[str] = field(default_factory=list)
    supported_modes: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    max_scan_ssids: int = 0


# ------------------------------------------------------------
# الواجهات
# ------------------------------------------------------------
class IW:
    BINARY = "iw"

    @staticmethod
    def is_available() -> bool:
        return command_exists(IW.BINARY)

    # ---------- قائمة الواجهات ----------
    @staticmethod
    def list_interfaces() -> list[str]:
        """يرجع أسماء واجهات الشبكة."""
        result = run([IW.BINARY, "dev"])
        if not result.ok:
            logger.error(f"فشل iw dev: {result.stderr}")
            return []
        # مثال السطر: Interface wlan0
        return re.findall(r"Interface\s+(\S+)", result.stdout)

    # ---------- معلومات واجهة ----------
    @staticmethod
    def get_interface_info(iface: str) -> Optional[WirelessInterface]:
        result = run([IW.BINARY, "dev", iface, "info"])
        if not result.ok:
            logger.error(f"فشل iw dev {iface} info: {result.stderr}")
            return None

        info = WirelessInterface(name=iface)
        text = result.stdout

        m = re.search(r"wiphy\s+(\d+)", text)
        if m:
            info.phy = f"phy{m.group(1)}"

        m = re.search(r"type\s+(\S+)", text)
        if m:
            info.type = m.group(1)

        m = re.search(r"channel\s+(\d+)\s+\((\d+)\s+MHz\)", text)
        if m:
            info.channel = int(m.group(1))
            info.frequency = int(m.group(2))

        m = re.search(r"txpower\s+([\d.]+)\s+dBm", text)
        if m:
            info.txpower = float(m.group(1))

        m = re.search(r"addr\s+([0-9a-fA-F:]{17})", text)
        if m:
            info.mac = m.group(1).upper()

        m = re.search(r"ssid\s+(.+)", text)
        if m:
            info.ssid = m.group(1).strip()

        # حالة UP/DOWN
        link_result = run([IW.BINARY, "dev", iface, "link"])
        info.is_up = "Not connected" not in link_result.stdout and link_result.ok

        # القدرات من phy
        if info.phy:
            phy_info = IW.get_phy_info(info.phy)
            if phy_info:
                info.bands = phy_info.bands
                info.supports_monitor = "monitor" in phy_info.supported_modes
                info.supports_ap = "AP" in phy_info.supported_modes
                info.supports_mesh = "mesh point" in phy_info.supported_modes

        return info

    # ---------- معلومات phy ----------
    @staticmethod
    def get_phy_info(phy: str) -> Optional[PhyInfo]:
        result = run([IW.BINARY, "phy", phy, "info"])
        if not result.ok:
            return None

        text = result.stdout
        info = PhyInfo(phy=phy, index=int(re.sub(r"\D", "", phy) or 0))

        # النطاقات
        if "Band 1:" in text:
            info.bands.append("2.4")
        if "Band 2:" in text:
            info.bands.append("5")
        if "Band 4:" in text:
            info.bands.append("6")

        # الأوضاع المدعومة
        modes_match = re.search(r"Supported interface modes:\s*\n((?:\s+\*\s+\S+.*\n)+)", text)
        if modes_match:
            for line in modes_match.group(1).splitlines():
                line = line.strip().lstrip("*").strip()
                if line:
                    info.supported_modes.append(line)

        # الأصفار المدعومة
        ciphers_match = re.search(r"Supported Ciphers:\s*\n((?:\s+\*\s+\S+.*\n)+)", text)
        if ciphers_match:
            for line in ciphers_match.group(1).splitlines():
                line = line.strip().lstrip("*").strip()
                if line:
                    info.supported_ciphers.append(line)

        # عدد SSID في المسح
        m = re.search(r"max\s+(\d+)\s+scan SSIDs", text)
        if m:
            info.max_scan_ssids = int(m.group(1))

        # الأوامر المدعومة
        cmds_match = re.search(r"Supported commands:\s*\n((?:\s+\*\s+\S+.*\n)+)", text)
        if cmds_match:
            for line in cmds_match.group(1).splitlines():
                line = line.strip().lstrip("*").strip()
                if line:
                    info.commands.append(line)

        return info

    # ---------- تغيير الوضع ----------
    @staticmethod
    def set_mode(iface: str, mode: str) -> CommandResult:
        """
        تغيير وضع الواجهة.
        mode: managed / monitor / AP / mesh / adhoc
        """
        IW.set_interface_down(iface)
        result = run([IW.BINARY, "dev", iface, "set", "type", mode])
        IW.set_interface_up(iface)
        if result.ok:
            logger.info(f"تم تغيير وضع {iface} إلى {mode}")
        else:
            logger.error(f"فشل تغيير الوضع: {result.stderr}")
        return result

    @staticmethod
    def set_monitor_mode(iface: str) -> CommandResult:
        return IW.set_mode(iface, "monitor")

    @staticmethod
    def set_managed_mode(iface: str) -> CommandResult:
        return IW.set_mode(iface, "managed")

    # ---------- القناة ----------
    @staticmethod
    def set_channel(iface: str, channel: int) -> CommandResult:
        # يحتاج الواجهة أن تكون down أولاً
        run([IW.BINARY, "dev", iface, "set", "channel", str(channel)])
        return run([IW.BINARY, "dev", iface, "set", "channel", str(channel)])

    @staticmethod
    def get_channel(iface: str) -> Optional[int]:
        result = run([IW.BINARY, "dev", iface, "info"])
        m = re.search(r"channel\s+(\d+)", result.stdout)
        return int(m.group(1)) if m else None

    # ---------- UP/DOWN ----------
    @staticmethod
    def set_interface_up(iface: str) -> CommandResult:
        return run(["ip", "link", "set", iface, "up"])

    @staticmethod
    def set_interface_down(iface: str) -> CommandResult:
        return run(["ip", "link", "set", iface, "down"])

    # ---------- الطاقة ----------
    @staticmethod
    def set_txpower(iface: str, dbm: int) -> CommandResult:
        return run([IW.BINARY, "dev", iface, "set", "txpower", "fixed", str(dbm)])

    # ---------- المسح ----------
    @staticmethod
    def scan(iface: str, timeout: int = 15) -> CommandResult:
        return run([IW.BINARY, "dev", iface, "scan"], timeout=timeout)

    # ---------- الوصول إلى قاعدة البيانات اللاسلكية ----------
    @staticmethod
    def get_regulatory_domain() -> str:
        result = run([IW.BINARY, "reg", "get"])
        m = re.search(r"country\s+(\S+):", result.stdout)
        return m.group(1) if m else "00"

    @staticmethod
    def set_regulatory_domain(country: str) -> CommandResult:
        return run([IW.BINARY, "reg", "set", country])


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
def list_wireless_interfaces() -> list[str]:
    return IW.list_interfaces()


def get_info(iface: str) -> Optional[WirelessInterface]:
    return IW.get_interface_info(iface)


def enable_monitor(iface: str) -> CommandResult:
    return IW.set_monitor_mode(iface)


def disable_monitor(iface: str) -> CommandResult:
    return IW.set_managed_mode(iface)


# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def list_interfaces() -> list[str]:
    return IW.list_interfaces()


def list_wireless_interfaces() -> list[str]:
    return IW.list_interfaces()


def get_info(iface: str):
    return IW.get_interface_info(iface)


def get_phy_info(phy: str):
    return IW.get_phy_info(phy)


def set_mode(iface: str, mode: str):
    return IW.set_mode(iface, mode)


def set_monitor_mode(iface: str):
    return IW.set_monitor_mode(iface)


def set_managed_mode(iface: str):
    return IW.set_managed_mode(iface)


def set_channel(iface: str, channel: int):
    return IW.set_channel(iface, channel)


def get_channel(iface: str):
    return IW.get_channel(iface)


def set_interface_up(iface: str):
    return IW.set_interface_up(iface)


def set_interface_down(iface: str):
    return IW.set_interface_down(iface)


def set_txpower(iface: str, dbm: int):
    return IW.set_txpower(iface, dbm)


def scan(iface: str, timeout: int = 15):
    return IW.scan(iface, timeout)


def get_regulatory_domain() -> str:
    return IW.get_regulatory_domain()


def set_regulatory_domain(country: str):
    return IW.set_regulatory_domain(country)


def enable_monitor(iface: str):
    return IW.set_monitor_mode(iface)


def disable_monitor(iface: str):
    return IW.set_managed_mode(iface)

