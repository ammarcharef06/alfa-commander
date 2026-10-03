# ============================================================
# Alfa Commander - Global State
# إدارة الحالة العامة للتطبيق
# ============================================================

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.constants import AdapterState, AttackState


# ------------------------------------------------------------
# نموذج بيانات محول
# ------------------------------------------------------------
@dataclass
class AdapterInfo:
    id: str                                # معرف فريد (MAC أو اسم الواجهة)
    model: str                             # AWUS036H, AWUS036ACH...
    chipset: str                           # RTL8187L, MT7610U...
    interface: str                         # wlan0
    monitor_interface: Optional[str] = None  # wlan0mon
    bands: list[str] = field(default_factory=list)   # ["2.4", "5"]
    driver: str = ""
    driver_type: str = ""                  # in-kernel / external
    max_standard: str = ""
    state: str = AdapterState.DISCONNECTED
    injection_ratio: int = 0               # %
    mac_address: str = ""
    usb_id: str = ""                       # 0bda:8187
    min_kernel: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------
# نموذج بيانات شبكة مكتشفة
# ------------------------------------------------------------
@dataclass
class NetworkInfo:
    bssid: str
    essid: str
    channel: int
    band: str                              # "2.4" / "5" / "6"
    encryption: str                        # WPA2 / WPA3 / OPEN...
    cipher: str = ""
    auth: str = ""
    power: int = 0                         # dBm (سالب عادة)
    beacons: int = 0
    data_frames: int = 0
    clients: list[str] = field(default_factory=list)
    wps: bool = False
    wps_version: str = ""
    hidden: bool = False
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    vendor: str = ""
    country: str = ""


# ------------------------------------------------------------
# نموذج هجوم
# ------------------------------------------------------------
@dataclass
class AttackInfo:
    id: str
    type: str                              # deauth / pmkid / handshake...
    target_bssid: str
    target_essid: str = ""
    adapter_id: str = ""
    state: str = AttackState.IDLE
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    progress: int = 0                      # 0-100
    log: list[str] = field(default_factory=list)
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


# ------------------------------------------------------------
# نموذج التصيد (Captive Portal)
# ------------------------------------------------------------
@dataclass
class CapturedCredential:
    ssid: str
    username: str
    password: str
    client_mac: str
    timestamp: datetime = field(default_factory=datetime.now)


# ------------------------------------------------------------
# الحالة العامة
# ------------------------------------------------------------
class AppState:
    """
    Singleton يحتفظ بكل حالة التطبيق.
    محمي بـ threading.RLock لأن الواجهة والخلفية تصلان إليه.
    """

    _instance: Optional["AppState"] = None

    def __new__(cls) -> "AppState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._lock = threading.RLock()

        # المحولات
        self.adapters: dict[str, AdapterInfo] = {}
        self.active_adapter_id: Optional[str] = None

        # الشبكات المكتشفة (BSSID -> NetworkInfo)
        self.networks: dict[str, NetworkInfo] = {}

        # الشبكات المختارة للهجوم
        self.targets: set[str] = set()

        # الهجمات الجارية (attack_id -> AttackInfo)
        self.attacks: dict[str, AttackInfo] = {}

        # بيانات التصيد
        self.credentials: list[CapturedCredential] = []

        # إحصائيات عامة
        self.stats: dict[str, Any] = {
            "networks_found": 0,
            "handshakes_captured": 0,
            "pmkids_captured": 0,
            "passwords_cracked": 0,
            "attacks_run": 0,
        }

        # حالة المسح
        self.scanning: bool = False

        # حالة النظام
        self.ready: bool = False
        self.dependencies_ok: bool = False

    # ----- المحولات -----
    def add_adapter(self, adapter: AdapterInfo):
        with self._lock:
            self.adapters[adapter.id] = adapter
            if self.active_adapter_id is None:
                self.active_adapter_id = adapter.id

    def remove_adapter(self, adapter_id: str):
        with self._lock:
            self.adapters.pop(adapter_id, None)
            if self.active_adapter_id == adapter_id:
                self.active_adapter_id = next(iter(self.adapters), None)

    def get_adapter(self, adapter_id: str) -> Optional[AdapterInfo]:
        with self._lock:
            return self.adapters.get(adapter_id)

    def get_active_adapter(self) -> Optional[AdapterInfo]:
        with self._lock:
            if self.active_adapter_id:
                return self.adapters.get(self.active_adapter_id)
            return None

    def set_active_adapter(self, adapter_id: str):
        with self._lock:
            if adapter_id in self.adapters:
                self.active_adapter_id = adapter_id

    # ----- الشبكات -----
    def upsert_network(self, network: NetworkInfo):
        with self._lock:
            old = self.networks.get(network.bssid)
            if old is None:
                self.networks[network.bssid] = network
                self.stats["networks_found"] += 1
            else:
                network.first_seen = old.first_seen
                self.networks[network.bssid] = network

    def clear_networks(self):
        with self._lock:
            self.networks.clear()
            self.targets.clear()

    def get_network(self, bssid: str) -> Optional[NetworkInfo]:
        with self._lock:
            return self.networks.get(bssid)

    def list_networks(self) -> list[NetworkInfo]:
        with self._lock:
            return list(self.networks.values())

    # ----- الأهداف -----
    def add_target(self, bssid: str):
        with self._lock:
            if bssid in self.networks:
                self.targets.add(bssid)

    def remove_target(self, bssid: str):
        with self._lock:
            self.targets.discard(bssid)

    def get_targets(self) -> list[NetworkInfo]:
        with self._lock:
            return [self.networks[b] for b in self.targets if b in self.networks]

    # ----- الهجمات -----
    def add_attack(self, attack: AttackInfo):
        with self._lock:
            self.attacks[attack.id] = attack
            self.stats["attacks_run"] += 1

    def update_attack(self, attack_id: str, **kwargs):
        with self._lock:
            attack = self.attacks.get(attack_id)
            if attack is None:
                return
            for key, value in kwargs.items():
                if hasattr(attack, key):
                    setattr(attack, key, value)

    def get_attack(self, attack_id: str) -> Optional[AttackInfo]:
        with self._lock:
            return self.attacks.get(attack_id)

    def list_attacks(self) -> list[AttackInfo]:
        with self._lock:
            return list(self.attacks.values())

    def remove_attack(self, attack_id: str):
        with self._lock:
            self.attacks.pop(attack_id, None)

    # ----- البيانات المخترقة -----
    def add_credential(self, cred: CapturedCredential):
        with self._lock:
            self.credentials.append(cred)

    def list_credentials(self) -> list[CapturedCredential]:
        with self._lock:
            return list(self.credentials)

    # ----- الإحصائيات -----
    def increment_stat(self, key: str, amount: int = 1):
        with self._lock:
            self.stats[key] = self.stats.get(key, 0) + amount

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.stats)

    # ----- مسح شامل -----
    def reset(self):
        with self._lock:
            self.adapters.clear()
            self.active_adapter_id = None
            self.networks.clear()
            self.targets.clear()
            self.attacks.clear()
            self.credentials.clear()
            self.scanning = False
            self.stats = {
                "networks_found": 0,
                "handshakes_captured": 0,
                "pmkids_captured": 0,
                "passwords_cracked": 0,
                "attacks_run": 0,
            }


# ------------------------------------------------------------
# الوصول العام
# ------------------------------------------------------------
_state: Optional[AppState] = None


def get_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state
