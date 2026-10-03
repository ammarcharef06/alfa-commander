# ============================================================
# Alfa Commander - Hash Converter
# تحويل ملفات الالتقاط إلى صيغ hashcat
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.utils.shell import run, command_exists
from app.logger import get_logger

logger = get_logger()


@dataclass
class ConversionResult:
    success: bool
    input_file: Path
    output_file: Optional[Path] = None
    hashes_count: int = 0
    format: str = ""
    error: Optional[str] = None
    output: str = ""


class HashConverter:
    """
    يحوّل ملفات الالتقاط إلى صيغ hashcat:
    - 22000: WPA-PBKDF2-PMKID+EAPOL (موحد)
    - 2500: WPA-EAPOL-PBKDF2 (قديم)
    - 16800: WPA-PMKID-PBKDF2 (قديم)
    """

    @staticmethod
    def to_22000(pcapng_file: Path, output: Optional[Path] = None) -> ConversionResult:
        """تحويل إلى hashcat 22000 (الأحدث)."""
        if not command_exists("hcxpcapngtool"):
            return ConversionResult(
                success=False,
                input_file=pcapng_file,
                error="hcxpcapngtool غير مثبت",
            )

        output = output or pcapng_file.with_suffix(".22000")

        # دعم كلا الإصدارين من hcxpcapngtool
        result = run(
            ["hcxpcapngtool", "-o", str(output), str(pcapng_file)],
            timeout=120,
        )

        if not result.ok:
            # محاولة بالخيار القديم
            result = run(
                ["hcxpcapngtool", "--pmkid", str(output), str(pcapng_file)],
                timeout=120,
            )

        if result.ok and output.exists():
            hashes = HashConverter._count_hashes(output)
            return ConversionResult(
                success=True,
                input_file=pcapng_file,
                output_file=output,
                hashes_count=hashes,
                format="22000",
                output=result.stdout,
            )

        return ConversionResult(
            success=False,
            input_file=pcapng_file,
            error=result.stderr or "فشل التحويل",
            output=result.stdout,
        )

    @staticmethod
    def to_2500(cap_file: Path, output: Optional[Path] = None) -> ConversionResult:
        """تحويل إلى hashcat 2500 (WPA-EAPOL)."""
        if not command_exists("cap2hccapx"):
            logger.warning("cap2hccapx غير مثبت، سيتم استخدام aircrack-ng")

        output = output or cap_file.with_suffix(".hccapx")

        if command_exists("cap2hccapx"):
            result = run(
                ["cap2hccapx", str(cap_file), str(output)],
                timeout=60,
            )
            if result.ok and output.exists():
                hashes = HashConverter._count_hashes(output)
                return ConversionResult(
                    success=True,
                    input_file=cap_file,
                    output_file=output,
                    hashes_count=hashes,
                    format="2500",
                )

        return ConversionResult(
            success=False,
            input_file=cap_file,
            error="cap2hccapx غير متوفر",
        )

    @staticmethod
    def to_16800(pcapng_file: Path, output: Optional[Path] = None) -> ConversionResult:
        """تحويل إلى hashcat 16800 (PMKID فقط)."""
        if not command_exists("hcxpcapngtool"):
            return ConversionResult(
                success=False,
                input_file=pcapng_file,
                error="hcxpcapngtool غير مثبت",
            )

        output = output or pcapng_file.with_suffix(".16800")
        result = run(
            ["hcxpcapngtool", "--pmkid-only", "-o", str(output), str(pcapng_file)],
            timeout=60,
        )

        if result.ok and output.exists():
            hashes = HashConverter._count_hashes(output)
            return ConversionResult(
                success=True,
                input_file=pcapng_file,
                output_file=output,
                hashes_count=hashes,
                format="16800",
            )

        return ConversionResult(
            success=False,
            input_file=pcapng_file,
            error=result.stderr or "فشل التحويل",
        )

    @staticmethod
    def _count_hashes(file: Path) -> int:
        """عد عدد الهاشات في الملف."""
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                lines = [l for l in f if l.strip() and not l.startswith("#")]
            return len(lines)
        except Exception:
            return 0

    @staticmethod
    def detect_input_format(file: Path) -> str:
        """كشف صيغة ملف الالتقاط."""
        suffix = file.suffix.lower()
        if suffix in (".pcapng",):
            return "pcapng"
        if suffix in (".cap", ".pcap"):
            return "pcap"
        if suffix in (".22000",):
            return "hashcat_22000"
        if suffix in (".hccapx",):
            return "hccapx"
        if suffix in (".16800",):
            return "hashcat_16800"
        return "unknown"

    @staticmethod
    def to_unified_hashcat(file: Path) -> ConversionResult:
        """
        تحويل ذكي: يكتشف الصيغة ويحول للأفضل.
        """
        fmt = HashConverter.detect_input_format(file)

        if fmt == "pcapng":
            return HashConverter.to_22000(file)
        if fmt == "pcap":
            # نحتاج تحويل cap إلى pcapng أولاً
            pcapng = file.with_suffix(".pcapng")
            if command_exists("editcap"):
                run(["editcap", "-F", "pcapng", str(file), str(pcapng)])
                if pcapng.exists():
                    return HashConverter.to_22000(pcapng)
            return HashConverter.to_2500(file)

        return ConversionResult(
            success=False,
            input_file=file,
            error=f"صيغة غير مدعومة: {fmt}",
        )


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
def convert_to_22000(pcapng_file: Path, output: Optional[Path] = None) -> ConversionResult:
    return HashConverter.to_22000(pcapng_file, output)


def convert_to_2500(cap_file: Path, output: Optional[Path] = None) -> ConversionResult:
    return HashConverter.to_2500(cap_file, output)


def auto_convert(file: Path) -> ConversionResult:
    return HashConverter.to_unified_hashcat(file)
