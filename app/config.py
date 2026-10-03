# ============================================================
# Alfa Commander - Configuration Manager
# إدارة الإعدادات القابلة للتخصيص
# ============================================================

from __future__ import annotations

import os
import yaml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from app.constants import (
    CONFIG_DIR, DATA_DIR, LOGS_DIR, EVIDENCE_DIR,
    DB_PATH, LOG_FILE, APP_HOME
)


# ------------------------------------------------------------
# نموذج الإعدادات الرئيسي
# ------------------------------------------------------------
@dataclass
class UIConfig:
    theme: str = "dark"                # dark / light
    language: str = "ar"
    font_family: str = "Cairo"
    font_size: int = 11
    window_width: int = 1400
    window_height: int = 900
    remember_window_state: bool = True
    animations_enabled: bool = True


@dataclass
class ScanConfig:
    default_duration: int = 30         # ثواني
    write_interval: int = 1            # ثواني
    hop_channels: bool = True
    band_2ghz: bool = True
    band_5ghz: bool = True
    band_6ghz: bool = False
    show_hidden: bool = True
    sort_by: str = "power"             # power / channel / essid


@dataclass
class AttackConfig:
    deauth_count: int = 0              # 0 = لانهائي
    deauth_interval: int = 1
    deauth_reason: int = 7             # 7 = Class 3 frame from nonassociated STA
    auto_check_injection: bool = True
    min_injection_ratio: int = 15      # %
    auto_adjust_on_weak: bool = True
    max_concurrent_attacks: int = 3


@dataclass
class CaptureConfig:
    output_format: str = "pcap"        # pcap / pcapng / cap
    auto_convert_to_hashcat: bool = True
    hashcat_format: int = 22000
    auto_start_crack: bool = False
    keep_pcap: bool = True


@dataclass
class CrackConfig:
    default_wordlist: str = "/usr/share/wordlists/rockyou.txt"
    rules: list[str] = field(default_factory=list)
    use_gpu: bool = True
    workload_profile: int = 2          # 1=low, 2=default, 3=high, 4=nightmare
    timeout: int = 0                   # 0 = بدون حد
    hashcat_binary: str = "hashcat"
    aircrack_binary: str = "aircrack-ng"


@dataclass
class RogueConfig:
    interface_for_ap: str = "auto"
    gateway_ip: str = "192.168.66.1"
    dhcp_range_start: str = "192.168.66.10"
    dhcp_range_end: str = "192.168.66.100"
    dns_servers: list[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    captive_portal_template: str = "generic"
    log_credentials: bool = True


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file_enabled: bool = True
    console_enabled: bool = True
    max_bytes: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5
    log_commands: bool = True


@dataclass
class DatabaseConfig:
    path: str = str(DB_PATH)
    auto_backup: bool = True
    backup_interval_hours: int = 24


@dataclass
class GeneralConfig:
    auto_check_dependencies: bool = True
    auto_check_updates: bool = False
    evidence_dir: str = str(EVIDENCE_DIR)
    profiles_dir: str = str(APP_HOME / "profiles")
    telemetry: bool = False


# ------------------------------------------------------------
# المكون الرئيسي للإعدادات
# ------------------------------------------------------------
@dataclass
class AppConfig:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    attack: AttackConfig = field(default_factory=AttackConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    crack: CrackConfig = field(default_factory=CrackConfig)
    rogue: RogueConfig = field(default_factory=RogueConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)


# ------------------------------------------------------------
# مدير الإعدادات
# ------------------------------------------------------------
class ConfigManager:
    """
    يدير تحميل وحفظ الإعدادات.
    - يقرأ من config/*.yaml
    - يحفظ في APP_HOME/config.yaml
    - يعطي قيم افتراضية عند غياب الملف
    """

    MAIN_CONFIG = APP_HOME / "config.yaml"

    def __init__(self):
        self.config = AppConfig()
        self._load()

    def _load(self):
        # تحميل الإعدادات من ملف المستخدم إن وُجد
        if self.MAIN_CONFIG.exists():
            try:
                with open(self.MAIN_CONFIG, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._apply_dict(data)
            except Exception as e:
                print(f"[ConfigManager] فشل تحميل الإعدادات: {e}")

        # تحميل إضافي من مجلد config/ إن وُجدت ملفات
        for yaml_file in CONFIG_DIR.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._apply_dict(data)
            except Exception as e:
                print(f"[ConfigManager] فشل تحميل {yaml_file.name}: {e}")

    def _apply_dict(self, data: dict[str, Any]):
        for section_name, section_values in data.items():
            section = getattr(self.config, section_name, None)
            if section is None or not isinstance(section_values, dict):
                continue
            for key, value in section_values.items():
                if hasattr(section, key):
                    setattr(section, key, value)

    def save(self):
        self.MAIN_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        with open(self.MAIN_CONFIG, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                asdict(self.config),
                f,
                allow_unicode=True,
                sort_keys=False,
            )

    def reset(self):
        self.config = AppConfig()
        if self.MAIN_CONFIG.exists():
            self.MAIN_CONFIG.unlink()

    def get(self, section: str) -> Any:
        return getattr(self.config, section, None)

    def to_dict(self) -> dict:
        return asdict(self.config)


# ------------------------------------------------------------
# نسخة عالمية واحدة (Singleton)
# ------------------------------------------------------------
_config_instance: ConfigManager | None = None


def get_config() -> ConfigManager:
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
