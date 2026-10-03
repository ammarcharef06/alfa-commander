# ============================================================
# Alfa Commander - Validators
# التحقق من صحة المدخلات
# ============================================================

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from app.constants import BAND_2GHZ_CHANNELS, BAND_5GHZ_CHANNELS, BAND_6GHZ_CHANNELS


# ------------------------------------------------------------
# أنماط Regex
# ------------------------------------------------------------
MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
MAC_DASH_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}$")
INTERFACE_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\-]{1,14}$")
SSID_MAX_LEN = 32
WPA_PASSWORD_MIN = 8
WPA_PASSWORD_MAX = 63


# ------------------------------------------------------------
# MAC / BSSID
# ------------------------------------------------------------
def is_valid_mac(value: str) -> bool:
    if not value:
        return False
    return bool(MAC_PATTERN.match(value)) or bool(MAC_DASH_PATTERN.match(value))


def normalize_mac(value: str) -> str:
    """توحيد MAC إلى صيغة AA:BB:CC:DD:EE:FF."""
    if not is_valid_mac(value):
        raise ValueError(f"MAC غير صالح: {value}")
    return value.replace("-", ":").upper()


def validate_mac(value: str) -> bool:
    return is_valid_mac(value)


def validate_bssid(value: str) -> bool:
    return is_valid_mac(value)


def is_broadcast_mac(value: str) -> bool:
    return value.upper() in ("FF:FF:FF:FF:FF:FF", "FF-FF-FF-FF-FF-FF")


def is_multicast_mac(value: str) -> bool:
    if not is_valid_mac(value):
        return False
    first_octet = int(value.replace("-", ":").split(":")[0], 16)
    return bool(first_octet & 0x01)


def is_locally_administered(value: str) -> bool:
    """هل MAC محلي الإدارة (bit 1 من البايت الأول = 1)؟"""
    if not is_valid_mac(value):
        return False
    first_octet = int(value.replace("-", ":").split(":")[0], 16)
    return bool(first_octet & 0x02)


# ------------------------------------------------------------
# الواجهات
# ------------------------------------------------------------
def is_valid_interface(name: str) -> bool:
    if not name:
        return False
    if not INTERFACE_PATTERN.match(name):
        return False
    # التحقق من وجود الواجهة فعلياً
    return Path(f"/sys/class/net/{name}").exists()


def interface_exists(name: str) -> bool:
    return Path(f"/sys/class/net/{name}").exists()


# ------------------------------------------------------------
# SSID
# ------------------------------------------------------------
def is_valid_ssid(ssid: str, allow_empty: bool = True) -> bool:
    if ssid is None:
        return allow_empty
    if len(ssid) > SSID_MAX_LEN:
        return False
    if not allow_empty and len(ssid) == 0:
        return False
    return True


def is_hidden_ssid(ssid: str) -> bool:
    return not ssid or ssid.strip() == "" or ssid == "<length: 0>"


# ------------------------------------------------------------
# كلمات المرور
# ------------------------------------------------------------
def is_valid_wpa_password(password: str) -> bool:
    if not password:
        return False
    return WPA_PASSWORD_MIN <= len(password) <= WPA_PASSWORD_MAX


def is_valid_wep_key(key: str) -> bool:
    if not key:
        return False
    # WEP: 5/13 حرف ASCII أو 10/26 خانة hex
    if len(key) in (5, 13):
        return True
    if len(key) in (10, 26) and all(c in "0123456789abcdefABCDEF" for c in key):
        return True
    return False


# ------------------------------------------------------------
# القنوات
# ------------------------------------------------------------
def is_valid_channel(channel: int, band: Optional[str] = None) -> bool:
    if band == "2.4" or band is None:
        if channel in BAND_2GHZ_CHANNELS:
            return True
    if band == "5" or band is None:
        if channel in BAND_5GHZ_CHANNELS:
            return True
    if band == "6":
        if channel in BAND_6GHZ_CHANNELS:
            return True
    return False


def band_from_channel(channel: int) -> Optional[str]:
    if channel in BAND_2GHZ_CHANNELS:
        return "2.4"
    if channel in BAND_5GHZ_CHANNELS:
        return "5"
    if channel in BAND_6GHZ_CHANNELS:
        return "6"
    return None


def channel_to_frequency(channel: int) -> Optional[int]:
    band = band_from_channel(channel)
    if band == "2.4":
        return 2407 + channel * 5
    if band == "5":
        return 5000 + channel * 5
    return None


# ------------------------------------------------------------
# المسارات
# ------------------------------------------------------------
def is_valid_path(path: str | Path, must_exist: bool = False) -> bool:
    p = Path(path)
    if must_exist:
        return p.exists()
    return True


def is_writable_dir(path: str | Path) -> bool:
    p = Path(path)
    return p.is_dir() and os.access(p, os.W_OK)


def is_readable_file(path: str | Path) -> bool:
    p = Path(path)
    return p.is_file() and os.access(p, os.R_OK)


# ------------------------------------------------------------
# BSSID:WPA*02 في hashcat
# ------------------------------------------------------------
HASHCAT_22000_PATTERN = re.compile(r"^WPA\*02\*[0-9a-fA-F]{12}\*[0-9a-fA-F]{12}\*.*$")


def is_valid_hashcat_22000(line: str) -> bool:
    return bool(HASHCAT_22000_PATTERN.match(line))


# ------------------------------------------------------------
# رفع الاستثناءات
# ------------------------------------------------------------
def validate_or_raise(value: str, validator, message: str = "قيمة غير صالحة"):
    if not validator(value):
        raise ValueError(f"{message}: {value}")
    return value
