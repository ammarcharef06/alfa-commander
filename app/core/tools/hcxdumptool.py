# ============================================================
# Alfa Commander - hcxdumptool Wrapper
# التقاط PMKID و EAPOL
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
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
class PMKIDCaptureResult:
    success: bool
    file_path: Optional[Path] = None
    hashcat_path: Optional[Path] = None
    pmkid_count: int = 0
    eapol_count: int = 0
    output: str = ""


@dataclass
class HCXDumpOptions:
    interface: str
    output_file: Path
    bssid_filter: Optional[list[str]] = None      # قائمة BSSID مسموحة
    client_filter: Optional[list[str]] = None
    channel_filter: Optional[list[int]] = None
    active_attack: bool = True                     # إرسال طلبات deauth خفيفة
    deauth_count: int = 5
    duration: int = 0                              # 0 = لانهائي
    use_band: str = "2"                            # 2 / 5 / 6


# ------------------------------------------------------------
# الغلاف
# ------------------------------------------------------------
class HCXDumptool:
    BINARY = "hcxdumptool"
    CONVERTER = "hcxpcapngtool"

    @staticmethod
    def is_available() -> bool:
        return command_exists(HCXDumptool.BINARY)

    @staticmethod
    def converter_available() -> bool:
        return command_exists(HCXDumptool.CONVERTER)

    # ---------- بناء الأمر ----------
    @staticmethod
    def build_command(opts: HCXDumpOptions) -> list[str]:
        args = [
            HCXDumptool.BINARY,
            "-i", opts.interface,
            "-o", str(opts.output_file),
        ]

        # فلترة BSSID
        if opts.bssid_filter:
            args.extend(["--filterlist_ap", ",".join(opts.bssid_filter)])

        # فلترة العملاء
        if opts.client_filter:
            args.extend(["--filtermode", "2"])

        # فلترة القنوات
        if opts.channel_filter:
            args.extend(["--channel", ",".join(str(c) for c in opts.channel_filter)])

        # هجوم نشط
        if opts.active_attack:
            args.extend(["--enable_status", "1"])
            args.extend(["--attempt_client_ap", "1"])
        else:
            args.append("--disable_deauthentication")

        # مدة
        if opts.duration > 0:
            args.extend(["--tot", str(opts.duration)])

        return args

    # ---------- تشغيل الالتقاط ----------
    @staticmethod
    async def capture(opts: HCXDumpOptions) -> StreamingProcess:
        args = HCXDumptool.build_command(opts)
        logger.info(f"بدء التقاط PMKID/EAPOL على {opts.interface}")
        proc = StreamingProcess(args)
        await proc.start()
        return proc

    # ---------- تحويل pcapng إلى hashcat 22000 ----------
    @staticmethod
    def convert_to_hashcat(pcapng_file: Path, output_file: Optional[Path] = None) -> CommandResult:
        """
        تحويل ملف pcapng إلى صيغة hashcat 22000.
        """
        if output_file is None:
            output_file = pcapng_file.with_suffix(".22000")

        args = [
            HCXDumptool.CONVERTER,
            "-o", str(output_file),
            str(pcapng_file),
        ]
        result = run(args, timeout=60)

        if result.ok and output_file.exists():
            logger.info(f"تم التحويل: {output_file}")
        else:
            logger.warning(f"فشل التحويل: {result.stderr}")

        return result

    # ---------- تحليل نتائج الالتقاط ----------
    @staticmethod
    def parse_capture_results(pcapng_file: Path) -> PMKIDCaptureResult:
        """
        يحلل ملف pcapng ويرجع عدد PMKID و EAPOL.
        يستخدم hcxpcapngtool.
        """
        if not pcapng_file.exists():
            return PMKIDCaptureResult(success=False, output="الملف غير موجود")

        # نستخدم hcxpcapngtool للحصول على إحصائيات
        result = run(
            [HCXDumptool.CONVERTER, "--all", "-o", "/dev/null", str(pcapng_file)],
            timeout=60,
        )
        output = result.stdout + result.stderr

        pmkid_count = 0
        eapol_count = 0

        m = re.search(r"PMKID\s*\(.*\)\s*:\s*(\d+)", output)
        if m:
            pmkid_count = int(m.group(1))

        m = re.search(r"EAPOL\s*\(.*\)\s*:\s*(\d+)", output)
        if m:
            eapol_count = int(m.group(1))

        success = pmkid_count > 0 or eapol_count > 0

        return PMKIDCaptureResult(
            success=success,
            file_path=pcapng_file,
            pmkid_count=pmkid_count,
            eapol_count=eapol_count,
            output=output,
        )

    # ---------- تشغيل + تحويل تلقائي ----------
    @staticmethod
    async def capture_and_convert(opts: HCXDumpOptions, timeout: int = 120) -> PMKIDCaptureResult:
        """
        تشغيل الالتقاط لمدة محددة ثم التحويل.
        """
        import asyncio
        proc = await HCXDumptool.capture(opts)

        if timeout > 0:
            await asyncio.sleep(timeout)
            await proc.stop()

        # انتظر قليلاً لضمان كتابة الملف
        await asyncio.sleep(1)

        if not opts.output_file.exists():
            return PMKIDCaptureResult(success=False, output="لم يتم إنشاء ملف الالتقاط")

        result = HCXDumptool.parse_capture_results(opts.output_file)
        if result.success:
            hc_file = opts.output_file.with_suffix(".22000")
            HCXDumptool.convert_to_hashcat(opts.output_file, hc_file)
            result.hashcat_path = hc_file

        return result


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
async def capture_pmkid(
    interface: str,
    output_file: Path,
    bssid: Optional[str] = None,
    duration: int = 120,
) -> PMKIDCaptureResult:
    """التقاط PMKID لهدف محدد."""
    opts = HCXDumpOptions(
        interface=interface,
        output_file=output_file,
        bssid_filter=[normalize_mac(bssid)] if bssid else None,
        duration=duration,
    )
    return await HCXDumptool.capture_and_convert(opts, timeout=duration)


def convert_pcapng_to_22000(pcapng: Path, output: Optional[Path] = None) -> CommandResult:
    return HCXDumptool.convert_to_hashcat(pcapng, output)


# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def build_command(opts):
    return HCXDumptool.build_command(opts)


def capture(opts):
    return HCXDumptool.capture(opts)


def convert_to_hashcat(pcapng_file, output_file=None):
    return HCXDumptool.convert_to_hashcat(pcapng_file, output_file)


def parse_capture_results(pcapng_file):
    return HCXDumptool.parse_capture_results(pcapng_file)


def capture_and_convert(opts, timeout: int = 120):
    return HCXDumptool.capture_and_convert(opts, timeout)

