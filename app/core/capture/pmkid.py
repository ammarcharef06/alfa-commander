# ============================================================
# Alfa Commander - PMKID Capture
# التقاط PMKID باستخدام hcxdumptool
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.constants import EVIDENCE_DIR
from app.core.tools import hcxdumptool
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


@dataclass
class PMKIDCaptureSession:
    session_id: str
    bssid: Optional[str]
    interface: str
    pcapng_file: Path
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    hashcat_file: Optional[Path] = None
    pmkid_count: int = 0
    eapol_count: int = 0
    success: bool = False
    error: Optional[str] = None


class PMKIDCapture:
    def __init__(
        self,
        interface: str,
        bssid: Optional[str] = None,
        duration: int = 120,
        active_attack: bool = True,
        on_capture: Optional[Callable[[Path, Path], None]] = None,
    ):
        self.interface = interface
        self.bssid = normalize_mac(bssid) if bssid else None
        self.duration = duration
        self.active_attack = active_attack
        self.on_capture = on_capture

        safe = self.bssid.replace(":", "") if self.bssid else "all"
        pcapng = EVIDENCE_DIR / f"pmkid_{safe}_{int(datetime.now().timestamp())}.pcapng"

        self.session = PMKIDCaptureSession(
            session_id=f"pmkid_{int(datetime.now().timestamp())}",
            bssid=self.bssid,
            interface=interface,
            pcapng_file=pcapng,
        )
        self._process: Optional[hcxdumptool.StreamingProcess] = None

    async def start(self) -> PMKIDCaptureSession:
        opts = hcxdumptool.HCXDumpOptions(
            interface=self.interface,
            output_file=self.session.pcapng_file,
            bssid_filter=[self.bssid] if self.bssid else None,
            active_attack=self.active_attack,
            duration=self.duration,
        )
        self._process = await hcxdumptool.HCXDumptool.capture(opts)
        logger.info(f"بدء PMKID Capture [{self.session.session_id}]")
        return self.session

    async def stop(self) -> PMKIDCaptureSession:
        import asyncio
        if self._process:
            await self._process.stop()
        await asyncio.sleep(1)

        self.session.finished_at = datetime.now()

        if not self.session.pcapng_file.exists():
            self.session.error = "لم يتم إنشاء ملف الالتقاط"
            return self.session

        result = hcxdumptool.HCXDumptool.parse_capture_results(self.session.pcapng_file)
        self.session.pmkid_count = result.pmkid_count
        self.session.eapol_count = result.eapol_count
        self.session.success = result.success

        if result.success:
            hc_file = self.session.pcapng_file.with_suffix(".22000")
            hcxdumptool.HCXDumptool.convert_to_hashcat(
                self.session.pcapng_file, hc_file
            )
            if hc_file.exists():
                self.session.hashcat_file = hc_file

            if self.on_capture:
                try:
                    self.on_capture(self.session.pcapng_file, hc_file)
                except Exception as e:
                    logger.exception(f"خطأ في on_capture: {e}")

        return self.session
