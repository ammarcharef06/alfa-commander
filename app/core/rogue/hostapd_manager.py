# ============================================================
# Alfa Commander - hostapd Manager
# إدارة نقطة الوصول الشريرة
# ============================================================

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.constants import EVIDENCE_DIR
from app.utils.shell import StreamingProcess, run, command_exists
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# قالب hostapd.conf
# ------------------------------------------------------------
HOSTAPD_TEMPLATE = """\
# Alfa Commander - Rogue AP Configuration
interface={interface}
driver=nl80211
ssid={ssid}
hw_mode={hw_mode}
channel={channel}
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid={hidden}

# WPA/WPA2 (فارغ = مفتوح)
{wpa_config}

# Country
country_code={country}
ieee80211d=1

# Logging
logger_syslog=-1
logger_syslog_level=2
logger_stdout=-1
logger_stdout_level=2
"""

WPA_CONFIG_TEMPLATE = """\
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""


@dataclass
class RogueAPOptions:
    interface: str
    ssid: str
    channel: int = 6
    password: Optional[str] = None          # None = مفتوح
    hidden: bool = False
    hw_mode: str = "g"                      # g = 2.4GHz, a = 5GHz
    country: str = "US"
    bssid: Optional[str] = None             # لنسخ BSSID الهدف


@dataclass
class RogueAPSession:
    session_id: str
    interface: str
    ssid: str
    channel: int
    config_file: Path
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    running: bool = False
    clients_connected: int = 0
    error: Optional[str] = None


class HostapdManager:
    BINARY = "hostapd"

    def __init__(
        self,
        opts: RogueAPOptions,
        on_client_connect: Optional[callable] = None,
    ):
        self.opts = opts
        self.on_client_connect = on_client_connect

        self.session = RogueAPSession(
            session_id=f"rogue_{int(datetime.now().timestamp())}",
            interface=opts.interface,
            ssid=opts.ssid,
            channel=opts.channel,
            config_file=EVIDENCE_DIR / f"hostapd_{int(datetime.now().timestamp())}.conf",
        )
        self._process: Optional[StreamingProcess] = None

    @staticmethod
    def is_available() -> bool:
        return command_exists(HostapdManager.BINARY)

    # ---------- توليد ملف الإعدادات ----------
    def _generate_config(self) -> Path:
        wpa_config = ""
        if self.opts.password:
            wpa_config = WPA_CONFIG_TEMPLATE.format(password=self.opts.password)

        config = HOSTAPD_TEMPLATE.format(
            interface=self.opts.interface,
            ssid=self.opts.ssid,
            hw_mode=self.opts.hw_mode,
            channel=self.opts.channel,
            hidden=1 if self.opts.hidden else 0,
            wpa_config=wpa_config,
            country=self.opts.country,
        )

        # إضافة BSSID إن وُجد
        if self.opts.bssid:
            config += f"\nbssid={normalize_mac(self.opts.bssid)}\n"

        self.session.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.session.config_file.write_text(config, encoding="utf-8")
        return self.session.config_file

    # ---------- التشغيل ----------
    async def start(self) -> RogueAPSession:
        if not self.is_available():
            raise RuntimeError("hostapd غير مثبت")

        config = self._generate_config()

        # تجهيز الواجهة: فلاش IP
        from app.core.tools import ip
        ip.IP.flush_ip(self.opts.interface)
        ip.IP.link_up(self.opts.interface)

        args = [self.BINARY, str(config)]

        self._process = StreamingProcess(
            args,
            on_stdout=self._handle_line,
            on_stderr=self._handle_line,
            on_exit=self._handle_exit,
        )
        await self._process.start()

        self.session.started_at = datetime.now()
        self.session.running = True

        logger.info(
            f"بدء Rogue AP [{self.session.session_id}]: "
            f"SSID={self.opts.ssid} CH={self.opts.channel}"
        )
        return self.session

    async def stop(self):
        if self._process and self._process.running:
            await self._process.stop()

        self.session.running = False
        self.session.stopped_at = datetime.now()

        # إيقاف الخدمات المرتبطة
        run(["pkill", "-f", "dnsmasq"])
        run(["pkill", "-f", "hostapd"])

        logger.info(f"إيقاف Rogue AP [{self.session.session_id}]")

    # ---------- تحليل المخرجات ----------
    def _handle_line(self, line: str):
        if not line:
            return

        # "AP-STA-CONNECTED xx:xx:xx:xx:xx:xx"
        if "AP-STA-CONNECTED" in line:
            self.session.clients_connected += 1
            logger.info(f"عميل جديد اتصل بـ Rogue AP: {line}")
            if self.on_client_connect:
                try:
                    mac = line.split("AP-STA-CONNECTED")[-1].strip().split()[0]
                    self.on_client_connect(mac)
                except Exception:
                    pass

        # "AP-STA-DISCONNECTED"
        if "AP-STA-DISCONNECTED" in line:
            logger.info(f"عميل断开: {line}")

    def _handle_exit(self, rc: int):
        self.session.running = False
        if rc != 0 and not self.session.error:
            self.session.error = f"hostapd انتهى برمز {rc}"
        logger.info(f"انتهى hostapd برمز {rc}")


# ------------------------------------------------------------
# دالة مختصرة
# ------------------------------------------------------------
async def start_rogue_ap(
    interface: str,
    ssid: str,
    channel: int = 6,
    password: Optional[str] = None,
) -> RogueAPSession:
    opts = RogueAPOptions(
        interface=interface,
        ssid=ssid,
        channel=channel,
        password=password,
    )
    manager = HostapdManager(opts)
    return await manager.start()
