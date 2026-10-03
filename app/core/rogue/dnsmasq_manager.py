# ============================================================
# Alfa Commander - dnsmasq Manager
# DHCP + DNS لنقطة الوصول الشريرة
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.constants import EVIDENCE_DIR
from app.utils.shell import StreamingProcess, run, command_exists
from app.logger import get_logger

logger = get_logger()


DNSMASQ_TEMPLATE = """\
# Alfa Commander - dnsmasq Configuration
interface={interface}
bind-interfaces
except-interface=lo
dhcp-range={dhcp_start},{dhcp_end},12h
dhcp-option=3,{gateway}
dhcp-option=6,{gateway}
server={upstream_dns}
log-queries
log-dhcp
no-resolv
address=/#/{gateway}
"""


@dataclass
class DnsmasqOptions:
    interface: str
    gateway: str = "192.168.66.1"
    dhcp_start: str = "192.168.66.10"
    dhcp_end: str = "192.168.66.100"
    upstream_dns: str = "8.8.8.8"
    log_leases: bool = True


@dataclass
class DnsmasqSession:
    session_id: str
    interface: str
    config_file: Path
    lease_file: Path
    log_file: Path
    started_at: Optional[datetime] = None
    running: bool = False


class DnsmasqManager:
    BINARY = "dnsmasq"

    def __init__(self, opts: DnsmasqOptions):
        self.opts = opts
        sid = f"dnsmasq_{int(datetime.now().timestamp())}"
        self.session = DnsmasqSession(
            session_id=sid,
            interface=opts.interface,
            config_file=EVIDENCE_DIR / f"{sid}.conf",
            lease_file=EVIDENCE_DIR / f"{sid}.leases",
            log_file=EVIDENCE_DIR / f"{sid}.log",
        )
        self._process: Optional[StreamingProcess] = None

    @staticmethod
    def is_available() -> bool:
        return command_exists(DnsmasqManager.BINARY)

    def _generate_config(self) -> Path:
        config = DNSMASQ_TEMPLATE.format(
            interface=self.opts.interface,
            dhcp_start=self.opts.dhcp_start,
            dhcp_end=self.opts.dhcp_end,
            gateway=self.opts.gateway,
            upstream_dns=self.opts.upstream_dns,
        )
        config += f"\ndhcp-leasefile={self.session.lease_file}\n"
        config += f"log-facility={self.session.log_file}\n"

        self.session.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.session.config_file.write_text(config, encoding="utf-8")
        return self.session.config_file

    async def start(self) -> DnsmasqSession:
        if not self.is_available():
            raise RuntimeError("dnsmasq غير مثبت")

        config = self._generate_config()
        args = [self.BINARY, "-C", str(config), "-d"]

        self._process = StreamingProcess(
            args,
            on_stdout=self._handle_line,
            on_stderr=self._handle_line,
        )
        await self._process.start()

        self.session.started_at = datetime.now()
        self.session.running = True

        logger.info(f"بدء dnsmasq [{self.session.session_id}]")
        return self.session

    async def stop(self):
        if self._process and self._process.running:
            await self._process.stop()
        self.session.running = False
        logger.info(f"إيقاف dnsmasq [{self.session.session_id}]")

    def _handle_line(self, line: str):
        if "DHCPACK" in line or "DHCPDISCOVER" in line:
            logger.debug(f"dnsmasq: {line}")

    def get_connected_clients(self) -> list[dict]:
        """قراءة العملاء المتصلين من ملف leases."""
        clients = []
        if not self.session.lease_file.exists():
            return clients

        try:
            with open(self.session.lease_file, "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 5:
                        clients.append({
                            "mac": parts[1],
                            "ip": parts[2],
                            "hostname": parts[3] if parts[3] != "*" else "",
                            "lease_end": parts[0],
                        })
        except Exception as e:
            logger.exception(f"فشل قراءة leases: {e}")

        return clients


# ------------------------------------------------------------
# دالة مختصرة
# ------------------------------------------------------------
async def start_dnsmasq(
    interface: str,
    gateway: str = "192.168.66.1",
) -> DnsmasqSession:
    opts = DnsmasqOptions(interface=interface, gateway=gateway)
    manager = DnsmasqManager(opts)
    return await manager.start()
