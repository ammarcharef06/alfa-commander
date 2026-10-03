# ============================================================
# Alfa Commander - PCAP Manager
# إدارة ملفات الالتقاط
# ============================================================

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.constants import EVIDENCE_DIR
from app.utils.shell import run, command_exists
from app.logger import get_logger

logger = get_logger()


@dataclass
class CaptureFile:
    path: Path
    bssid: str = ""
    type: str = "unknown"            # handshake / pmkid / scan / other
    size_bytes: int = 0
    created_at: datetime = None
    has_handshake: bool = False
    has_pmkid: bool = False
    hashcat_file: Optional[Path] = None
    metadata: dict = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}
        if self.path.exists():
            self.size_bytes = self.path.stat().st_size


class PCAPManager:
    """
    يدير ملفات الالتقاط: البحث، التحقق، التحويل، والحذف.
    """

    @staticmethod
    def list_captures(directory: Optional[Path] = None) -> list[CaptureFile]:
        """قائمة بكل ملفات الالتقاط."""
        directory = directory or EVIDENCE_DIR
        if not directory.exists():
            return []

        captures = []
        for ext in ("*.cap", "*.pcap", "*.pcapng"):
            for file in directory.glob(ext):
                cap = CaptureFile(path=file)
                cap.type = PCAPManager._classify(file)
                if cap.type == "handshake":
                    cap.has_handshake = PCAPManager.check_handshake(file)
                elif cap.type == "pmkid":
                    cap.has_pmkid = PCAPManager.check_pmkid(file)
                captures.append(cap)

        captures.sort(key=lambda c: c.created_at, reverse=True)
        return captures

    @staticmethod
    def _classify(path: Path) -> str:
        name = path.stem.lower()
        if name.startswith("hs_"):
            return "handshake"
        if name.startswith("pmkid_"):
            return "pmkid"
        if name.startswith("scan_"):
            return "scan"
        return "other"

    @staticmethod
    def check_handshake(cap_file: Path) -> bool:
        """
        فحص وجود مصافحة WPA/WPA2 في ملف cap.
        يستخدم aircrack-ng.
        """
        if not cap_file.exists() or not command_exists("aircrack-ng"):
            return False

        result = run(["aircrack-ng", str(cap_file)], timeout=15)
        output = result.stdout.lower()

        # "1 handshake" أو "WPA (1 handshake)"
        import re
        if re.search(r"\b(\d+)\s+handshake", output):
            count = int(re.search(r"\b(\d+)\s+handshake", output).group(1))
            return count > 0

        return False

    @staticmethod
    def check_pmkid(pcapng_file: Path) -> bool:
        """
        فحص وجود PMKID في ملف pcapng.
        يستخدم hcxpcapngtool.
        """
        if not pcapng_file.exists() or not command_exists("hcxpcapngtool"):
            return False

        result = run(
            ["hcxpcapngtool", "--all", "-o", "/dev/null", str(pcapng_file)],
            timeout=30,
        )
        output = result.stdout + result.stderr
        return "PMKID" in output and "0" not in output.split("PMKID")[-1][:10]

    @staticmethod
    def get_handshake_count(cap_file: Path) -> int:
        """عدد المصافحات في الملف."""
        if not command_exists("aircrack-ng"):
            return 0
        result = run(["aircrack-ng", str(cap_file)], timeout=15)
        import re
        m = re.search(r"(\d+)\s+handshake", result.stdout.lower())
        return int(m.group(1)) if m else 0

    @staticmethod
    def convert_cap_to_pcapng(cap_file: Path, output: Optional[Path] = None) -> Optional[Path]:
        """تحويل cap إلى pcapng."""
        if not command_exists("editcap"):
            logger.warning("editcap غير مثبت")
            return None

        output = output or cap_file.with_suffix(".pcapng")
        result = run(["editcap", "-F", "pcapng", str(cap_file), str(output)], timeout=30)
        if result.ok and output.exists():
            return output
        return None

    @staticmethod
    def convert_pcapng_to_hashcat_22000(
        pcapng_file: Path,
        output: Optional[Path] = None,
    ) -> Optional[Path]:
        """تحويل pcapng إلى hashcat 22000."""
        if not command_exists("hcxpcapngtool"):
            logger.error("hcxpcapngtool غير مثبت")
            return None

        output = output or pcapng_file.with_suffix(".22000")
        result = run(
            ["hcxpcapngtool", "-o", str(output), str(pcapng_file)],
            timeout=60,
        )

        if result.ok and output.exists():
            logger.info(f"تم التحويل: {output}")
            return output

        logger.warning(f"فشل التحويل: {result.stderr}")
        return None

    @staticmethod
    def delete_capture(cap_file: Path) -> bool:
        try:
            cap_file.unlink()
            logger.info(f"تم حذف {cap_file}")
            return True
        except Exception as e:
            logger.exception(f"فشل حذف {cap_file}: {e}")
            return False

    @staticmethod
    def cleanup_old_captures(days: int = 30) -> int:
        """حذف الملفات الأقدم من عدد أيام."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0
        for cap in PCAPManager.list_captures():
            if cap.created_at < cutoff:
                if PCAPManager.delete_capture(cap.path):
                    deleted += 1
        return deleted

    @staticmethod
    def export_capture(cap_file: Path, dest: Path) -> bool:
        """تصدير ملف إلى مكان آخر."""
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cap_file, dest)
            return True
        except Exception as e:
            logger.exception(f"فشل التصدير: {e}")
            return False
