# ============================================================
# Alfa Commander - Scanner Logic
# منطق المسح المتقدم
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.constants import EVIDENCE_DIR
from app.core.tools import airodump
from app.logger import get_logger

logger = get_logger()


@dataclass
class ScanSession:
    session_id: str
    interface: str
    prefix: Path
    started_at: datetime = field(default_factory=datetime.now)
    stopped_at: Optional[datetime] = None
    networks_found: int = 0
    clients_found: int = 0
    running: bool = False


class Scanner:
    """
    يدير جلسة مسح مستمرة مع حفظ البيانات.
    """

    def __init__(
        self,
        interface: str,
        channels: Optional[list[int]] = None,
        dwell: float = 0.3,
        on_network: Optional[Callable[[airodump.ScannedNetwork], None]] = None,
        on_client: Optional[Callable[[airodump.ScannedClient], None]] = None,
    ):
        self.interface = interface
        self.channels = channels
        self.dwell = dwell
        self.on_network = on_network
        self.on_client = on_client

        self.session = ScanSession(
            session_id=f"scan_{int(datetime.now().timestamp())}",
            interface=interface,
            prefix=EVIDENCE_DIR / f"scan_{int(datetime.now().timestamp())}",
        )

        self._process: Optional[airodump.StreamingProcess] = None
        self._seen_networks: set[str] = set()
        self._seen_clients: set[str] = set()

    async def start(self) -> ScanSession:
        """بدء المسح."""
        opts = airodump.AirodumpOptions(
            interface=self.interface,
            output_prefix=self.session.prefix,
            ignore_negative_one=True,
            write_interval=1,
        )

        def _on_network(net: airodump.ScannedNetwork):
            if net.bssid not in self._seen_networks:
                self._seen_networks.add(net.bssid)
                self.session.networks_found += 1
            if self.on_network:
                self.on_network(net)

        def _on_client(cli: airodump.ScannedClient):
            if cli.mac not in self._seen_clients:
                self._seen_clients.add(cli.mac)
                self.session.clients_found += 1
            if self.on_client:
                self.on_client(cli)

        self._process = await airodump.Airodump.scan_streaming(
            opts,
            on_network=_on_network,
            on_client=_on_client,
        )

        self.session.running = True
        logger.info(f"بدء المسح [{self.session.session_id}] على {self.interface}")
        return self.session

    async def stop(self) -> ScanSession:
        if self._process:
            await self._process.stop()
        self.session.running = False
        self.session.stopped_at = datetime.now()
        logger.info(
            f"انتهى المسح [{self.session.session_id}]: "
            f"{self.session.networks_found} شبكة، {self.session.clients_found} عميل"
        )
        return self.session

    def get_networks(self) -> list[airodump.ScannedNetwork]:
        networks, _ = airodump.Airodump.parse_csv(self.session.prefix)
        return networks

    def get_clients(self) -> list[airodump.ScannedClient]:
        _, clients = airodump.Airodump.parse_csv(self.session.prefix)
        return clients


async def scan_networks(
    interface: str,
    duration: int = 30,
    channels: Optional[list[int]] = None,
    on_network: Optional[Callable] = None,
) -> tuple[ScanSession, list[airodump.ScannedNetwork]]:
    """مسح سريع لمدة محددة."""
    import asyncio
    scanner = Scanner(interface, channels=channels, on_network=on_network)
    await scanner.start()
    await asyncio.sleep(duration)
    session = await scanner.stop()
    networks = scanner.get_networks()
    return session, networks
