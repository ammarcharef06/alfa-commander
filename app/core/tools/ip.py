# ============================================================
# Alfa Commander - ip Wrapper
# إدارة واجهات الشبكة عبر ip
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
class LinkInfo:
    name: str
    state: str = ""             # UP / DOWN / UNKNOWN
    mac: str = ""
    mtu: int = 0
    flags: list[str] = field(default_factory=list)


# ------------------------------------------------------------
# الصنف الرئيسي
# ------------------------------------------------------------
class IP:
    BINARY = "ip"

    @staticmethod
    def is_available() -> bool:
        return command_exists(IP.BINARY)

    @staticmethod
    def list_links() -> list[LinkInfo]:
        result = run([IP.BINARY, "-o", "link", "show"])
        if not result.ok:
            return []

        links = []
        for line in result.stdout.splitlines():
            # مثال: 2: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
            m = re.match(
                r"\d+:\s+(\S+):\s+<([^>]+)>\s+mtu\s+(\d+).*link/\w+\s+([0-9a-fA-F:]+)",
                line,
            )
            if m:
                links.append(LinkInfo(
                    name=m.group(1),
                    state="UP" if "UP" in m.group(2) else "DOWN",
                    mtu=int(m.group(3)),
                    mac=m.group(4).upper(),
                    flags=m.group(2).split(","),
                ))
        return links

    @staticmethod
    def get_link(iface: str) -> Optional[LinkInfo]:
        for link in IP.list_links():
            if link.name == iface:
                return link
        return None

    @staticmethod
    def link_up(iface: str) -> CommandResult:
        return run([IP.BINARY, "link", "set", iface, "up"])

    @staticmethod
    def link_down(iface: str) -> CommandResult:
        return run([IP.BINARY, "link", "set", iface, "down"])

    @staticmethod
    def set_mac(iface: str, mac: str) -> CommandResult:
        IP.link_down(iface)
        result = run([IP.BINARY, "link", "set", "dev", iface, "address", mac])
        IP.link_up(iface)
        return result

    @staticmethod
    def set_mtu(iface: str, mtu: int) -> CommandResult:
        return run([IP.BINARY, "link", "set", "dev", iface, "mtu", str(mtu)])

    @staticmethod
    def add_ip(iface: str, cidr: str) -> CommandResult:
        return run([IP.BINARY, "addr", "add", cidr, "dev", iface])

    @staticmethod
    def del_ip(iface: str, cidr: str) -> CommandResult:
        return run([IP.BINARY, "addr", "del", cidr, "dev", iface])

    @staticmethod
    def flush_ip(iface: str) -> CommandResult:
        return run([IP.BINARY, "addr", "flush", "dev", iface])

    @staticmethod
    def list_addresses(iface: Optional[str] = None) -> dict[str, list[str]]:
        args = [IP.BINARY, "-o", "addr", "show"]
        if iface:
            args.append("dev")
            args.append(iface)
        result = run(args)
        addresses: dict[str, list[str]] = {}
        current = None
        for line in result.stdout.splitlines():
            m = re.match(r"\d+:\s+(\S+)\s+inet\s+(\S+)", line)
            if m:
                current = m.group(1)
                addresses.setdefault(current, []).append(m.group(2))
        return addresses

    @staticmethod
    def add_route(dest: str, via: Optional[str] = None, dev: Optional[str] = None) -> CommandResult:
        args = [IP.BINARY, "route", "add", dest]
        if via:
            args.extend(["via", via])
        if dev:
            args.extend(["dev", dev])
        return run(args)

    @staticmethod
    def del_route(dest: str) -> CommandResult:
        return run([IP.BINARY, "route", "del", dest])

    @staticmethod
    def default_route() -> Optional[str]:
        result = run([IP.BINARY, "route", "show", "default"])
        m = re.search(r"default via (\S+)", result.stdout)
        return m.group(1) if m else None

    @staticmethod
    def enable_forwarding() -> CommandResult:
        return run(["sysctl", "-w", "net.ipv4.ip_forward=1"])

    @staticmethod
    def disable_forwarding() -> CommandResult:
        return run(["sysctl", "-w", "net.ipv4.ip_forward=0"])

    @staticmethod
    def get_interface_mac(iface: str) -> Optional[str]:
        """يرجع MAC للواجهة."""
        info = IP.get_link(iface)
        return info.mac if info else None


# ------------------------------------------------------------
# دوال مختصرة على مستوى الوحدة (module-level)
# ------------------------------------------------------------
def list_links() -> list[LinkInfo]:
    return IP.list_links()


def get_link(iface: str) -> Optional[LinkInfo]:
    return IP.get_link(iface)


def link_up(iface: str) -> CommandResult:
    return IP.link_up(iface)


def link_down(iface: str) -> CommandResult:
    return IP.link_down(iface)


def set_mac(iface: str, mac: str) -> CommandResult:
    return IP.set_mac(iface, mac)


def set_mtu(iface: str, mtu: int) -> CommandResult:
    return IP.set_mtu(iface, mtu)


def add_ip(iface: str, cidr: str) -> CommandResult:
    return IP.add_ip(iface, cidr)


def del_ip(iface: str, cidr: str) -> CommandResult:
    return IP.del_ip(iface, cidr)


def flush_ip(iface: str) -> CommandResult:
    return IP.flush_ip(iface)


def list_addresses(iface: Optional[str] = None) -> dict[str, list[str]]:
    return IP.list_addresses(iface)


def add_route(dest: str, via: Optional[str] = None, dev: Optional[str] = None) -> CommandResult:
    return IP.add_route(dest, via, dev)


def del_route(dest: str) -> CommandResult:
    return IP.del_route(dest)


def default_route() -> Optional[str]:
    return IP.default_route()


def enable_forwarding() -> CommandResult:
    return IP.enable_forwarding()


def disable_forwarding() -> CommandResult:
    return IP.disable_forwarding()


def get_interface_mac(iface: str) -> Optional[str]:
    """يرجع MAC للواجهة (دالة module-level)."""
    return IP.get_interface_mac(iface)
