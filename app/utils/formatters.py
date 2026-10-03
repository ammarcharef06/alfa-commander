# ============================================================
# Alfa Commander - Formatters
# تنسيق القيم للعرض
# ============================================================

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


# ------------------------------------------------------------
# قوة الإشارة
# ------------------------------------------------------------
def format_power(dbm: int) -> str:
    """تنسيق dBm إلى نص مع رمز بصري."""
    if dbm >= -50:
        return f"{dbm} dBm ▂▄▆█"
    if dbm >= -60:
        return f"{dbm} dBm ▂▄▆_"
    if dbm >= -70:
        return f"{dbm} dBm ▂▄__"
    if dbm >= -80:
        return f"{dbm} dBm ▂___"
    return f"{dbm} dBm ____"


def power_to_percent(dbm: int) -> int:
    """تحويل dBm إلى نسبة 0-100 (تقريبي)."""
    if dbm >= -30:
        return 100
    if dbm <= -100:
        return 0
    # من -100 إلى -30
    return int((dbm + 100) * 100 / 70)


def power_color(dbm: int) -> str:
    """لون CSS حسب القوة."""
    if dbm >= -50:
        return "#00ff88"
    if dbm >= -65:
        return "#88ff00"
    if dbm >= -75:
        return "#ffcc00"
    if dbm >= -85:
        return "#ff8800"
    return "#ff3333"


def signal_bars(dbm: int) -> int:
    """عدد الأعمدة 0-4."""
    if dbm >= -55:
        return 4
    if dbm >= -65:
        return 3
    if dbm >= -75:
        return 2
    if dbm >= -85:
        return 1
    return 0


# ------------------------------------------------------------
# الحجم
# ------------------------------------------------------------
def format_bytes(size: int | float, precision: int = 2) -> str:
    if size < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    value = float(size)
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{value:.{precision}f} {units[idx]}"


def format_bitrate(kbps: int) -> str:
    if kbps < 1000:
        return f"{kbps} Kbps"
    if kbps < 1_000_000:
        return f"{kbps / 1000:.1f} Mbps"
    return f"{kbps / 1_000_000:.2f} Gbps"


# ------------------------------------------------------------
# الوقت
# ------------------------------------------------------------
def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{int(seconds * 1000)} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    if seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"


def format_eta(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    return format_duration(seconds)


def format_timestamp(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_time_only(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%H:%M:%S")


def format_relative(dt: datetime) -> str:
    delta = datetime.now() - dt
    if delta < timedelta(seconds=10):
        return "الآن"
    if delta < timedelta(minutes=1):
        return f"قبل {int(delta.total_seconds())} ثانية"
    if delta < timedelta(hours=1):
        return f"قبل {int(delta.total_seconds() // 60)} دقيقة"
    if delta < timedelta(days=1):
        return f"قبل {int(delta.total_seconds() // 3600)} ساعة"
    return f"قبل {delta.days} يوم"


# ------------------------------------------------------------
# النسب
# ------------------------------------------------------------
def format_percent(value: float, precision: int = 1) -> str:
    return f"{value:.{precision}f}%"


def format_ratio(value: float, total: float) -> str:
    if total <= 0:
        return "0%"
    return format_percent(value / total * 100)


# ------------------------------------------------------------
# السرعة (hashcat)
# ------------------------------------------------------------
def format_hashrate(hps: int) -> str:
    if hps < 1000:
        return f"{hps} H/s"
    if hps < 1_000_000:
        return f"{hps / 1000:.1f} kH/s"
    if hps < 1_000_000_000:
        return f"{hps / 1_000_000:.2f} MH/s"
    return f"{hps / 1_000_000_000:.2f} GH/s"


# ------------------------------------------------------------
# النص
# ------------------------------------------------------------
def truncate(text: str, max_len: int = 40, suffix: str = "…") -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def safe_ssid(ssid: str) -> str:
    if not ssid or ssid.strip() == "":
        return "<مخفي>"
    return ssid


# ------------------------------------------------------------
# MAC
# ------------------------------------------------------------
def format_mac(mac: str, uppercase: bool = True, sep: str = ":") -> str:
    if not mac:
        return ""
    normalized = mac.replace("-", ":").replace(".", "")
    parts = normalized.split(":")
    result = sep.join(parts)
    return result.upper() if uppercase else result.lower()


def short_mac(mac: str) -> str:
    """يعرض آخر 3 بايتات فقط."""
    normalized = mac.replace("-", ":").upper()
    parts = normalized.split(":")
    if len(parts) == 6:
        return ":".join(parts[3:])
    return mac


# ------------------------------------------------------------
# قنوات
# ------------------------------------------------------------
def format_channel(channel: int, band: Optional[str] = None) -> str:
    if band:
        return f"CH {channel} ({band}GHz)"
    return f"CH {channel}"


# ------------------------------------------------------------
# OUI
# ------------------------------------------------------------
def format_vendor(vendor: str, max_len: int = 20) -> str:
    if not vendor:
        return "غير معروف"
    return truncate(vendor, max_len)
