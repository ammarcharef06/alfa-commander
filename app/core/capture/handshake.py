# ============================================================
# Alfa Commander - Handshake Capture
# التقاط مصافحة WPA/WPA2
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.constants import EVIDENCE_DIR
from app.core.tools import airodump
from app.core.capture.pcap_manager import PCAPManager
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


@dataclass
class HandshakeSession:
    session_id: str
    bssid: str
    channel: int
    prefix: Path
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    cap_file: Optional[Path] = None
    handshake_count: int = 0
    success: bool = False
    error: Optional[str] = None


class HandshakeCapture:
    """
    يدير التقاط مصافحة WPA/WPA2.
    """

    def __init__(
        self,
        interface: str,
        bssid: str,
        channel: int,
        on_handshake: Optional[Callable[[Path], None]] = None,
    ):
        self.interface = interface
        self.bssid = normalize_mac(bssid)
        self.channel = channel
        self.on_handshake = on_handshake

        safe_bssid = self.bssid.replace(":", "")
        self.session = HandshakeSession(
            session_id=f"hs_{int(datetime.now().timestamp())}",
            bssid=self.bssid,
            channel=channel,
            prefix=EVIDENCE_DIR / f"hs_{safe_bssid}_{int(datetime.now().timestamp())}",
        )
        self._process: Optional[airodump.StreamingProcess] = None

    async def start(self) -> HandshakeSession:
        opts = airodump.AirodumpOptions(
            interface=self.interface,
            output_prefix=self.session.prefix,
            channel=self.channel,
            bssid=self.bssid,
            write_interval=1,
            ignore_negative_one=True,
        )

        self._process = await airodump.Airodump.scan_streaming(opts)

        self.session.cap_file = Path(str(self.session.prefix) + "-01.cap")

        logger.info(
            f"بدء التقاط Handshake [{self.session.session_id}] "
            f"على {self.bssid} (CH {self.channel})"
        )
        return self.session

    async def stop(self) -> HandshakeSession:
        if self._process:
            await self._process.stop()

        self.session.finished_at = datetime.now()
        return await self.check()

    async def check(self) -> HandshakeSession:
        """فحص وجود مصافحة في الملف."""
        if not self.session.cap_file or not self.session.cap_file.exists():
            return self.session

        count = PCAPManager.get_handshake_count(self.session.cap_file)
        self.session.handshake_count = count
        self.session.success = count > 0

        if self.session.success and self.on_handshake:
            try:
                self.on_handshake(self.session.cap_file)
            except Exception as e:
                logger.exception(f"خطأ في on_handshake: {e}")

        if self.session.success:
            logger.info(
                f"تم التقاط {count} مصافحة على {self.bssid} "
                f"في {self.session.cap_file}"
            )
        else:
            logger.warning(f"لم يتم التقاط مصافحة على {self.bssid}")

        return self.session


async def capture_handshake(
    interface: str,
    bssid: str,
    channel: int,
    duration: int = 60,
    on_handshake: Optional[Callable] = None,
) -> HandshakeSession:
    import asyncio
    capture = HandshakeCapture(interface, bssid, channel, on_handshake)
    await capture.start()
    await asyncio.sleep(duration)
    return await capture.stop()
