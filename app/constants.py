# ============================================================
# Alfa Commander - Constants
# كل الثوابت المركزية للمشروع
# ============================================================

from pathlib import Path

# ------------------------------------------------------------
# معلومات المشروع
# ------------------------------------------------------------
APP_NAME = "Alfa Commander"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Alfa Commander Project"
APP_DESCRIPTION = "منصة اختبار اختراق لاسلكي متكاملة لمحولات Alfa"
APP_HOME = Path.home() / ".alfa-commander"

# ------------------------------------------------------------
# المسارات الأساسية
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "app" / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
EVIDENCE_DIR = DATA_DIR / "evidence"
LOGS_DIR = DATA_DIR / "logs"
DB_DIR = DATA_DIR / "db"
PROFILES_DIR = DATA_DIR / "profiles"
WORDLISTS_DIR = DATA_DIR / "wordlists"
TEMPLATES_DIR = DATA_DIR / "templates"
RESOURCES_DIR = PROJECT_ROOT / "app" / "gui" / "resources"

# إنشاء المجلدات عند الاستيراد
for _dir in (DATA_DIR, EVIDENCE_DIR, LOGS_DIR, DB_DIR,
             PROFILES_DIR, WORDLISTS_DIR, TEMPLATES_DIR, APP_HOME):
    _dir.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "alfa.db"
LOG_FILE = LOGS_DIR / "alfa.log"
CONFIG_FILE = CONFIG_DIR / "adapters.yaml"

# ------------------------------------------------------------
# معرّفات USB لمحولات Alfa (VID:PID)
# ------------------------------------------------------------
ALFA_USB_IDS = {
    # الجيل الكلاسيكي
    "0bda:8187": {
        "model": "AWUS036H",
        "chipset": "RTL8187L",
        "bands": ["2.4"],
        "driver": "rtl8187",
        "driver_type": "in-kernel",
        "max_standard": "802.11g",
    },
    "0bda:8189": {
        "model": "AWUS036H (variant)",
        "chipset": "RTL8187B",
        "bands": ["2.4"],
        "driver": "rtl8187",
        "driver_type": "in-kernel",
        "max_standard": "802.11g",
    },

    # الجيل الانتقالي (يحتاج تعريف خارجي)
    "0bda:8812": {
        "model": "AWUS036ACH",
        "chipset": "RTL8812AU",
        "bands": ["2.4", "5"],
        "driver": "8812au",
        "driver_type": "external",
        "max_standard": "802.11ac",
    },
    "0bda:8813": {
        "model": "AWUS036AC",
        "chipset": "RTL8812AU",
        "bands": ["2.4", "5"],
        "driver": "8812au",
        "driver_type": "external",
        "max_standard": "802.11ac",
    },
    "0bda:8814": {
        "model": "AWUS1900",
        "chipset": "RTL8814AU",
        "bands": ["2.4", "5"],
        "driver": "8814au",
        "driver_type": "external",
        "max_standard": "802.11ac",
    },

    # الجيل الحديث
    "0e8d:7610": {
        "model": "AWUS036ACHM",
        "chipset": "MT7610U",
        "bands": ["2.4", "5"],
        "driver": "mt76x0u",
        "driver_type": "in-kernel",
        "max_standard": "802.11ac",
    },
    "0e8d:7612": {
        "model": "AWUS036ACM",
        "chipset": "MT7612U",
        "bands": ["2.4", "5"],
        "driver": "mt76x2u",
        "driver_type": "in-kernel",
        "max_standard": "802.11ac",
    },

    # الجيل الأحدث (WiFi 6)
    "0e8d:7961": {
        "model": "AWUS036AXM",
        "chipset": "MT7921AUN",
        "bands": ["2.4", "5", "6"],
        "driver": "mt7921u",
        "driver_type": "in-kernel",
        "max_standard": "802.11ax",
        "min_kernel": "5.18",
    },
    "0e8d:7962": {
        "model": "AWUS036AXML",
        "chipset": "MT7921AUN",
        "bands": ["2.4", "5", "6"],
        "driver": "mt7921u",
        "driver_type": "in-kernel",
        "max_standard": "802.11ax",
        "min_kernel": "5.18",
    },

    # ============================================================
    # Ralink RT2870/RT3070 (شائعة في محولات Alfa AWUS036NH)
    # ============================================================
    "148f:3070": {
        "model": "AWUS036NH",
        "chipset": "RT3070",
        "bands": ["2.4"],
        "driver": "rt2800usb",
        "driver_type": "in-kernel",
        "max_standard": "802.11n",
    },
    "148f:2870": {
        "model": "AWUS036NH (RT2870)",
        "chipset": "RT2870",
        "bands": ["2.4"],
        "driver": "rt2800usb",
        "driver_type": "in-kernel",
        "max_standard": "802.11n",
    },
    "148f:3572": {
        "model": "AWUS036NEH",
        "chipset": "RT3572",
        "bands": ["2.4", "5"],
        "driver": "rt2800usb",
        "driver_type": "in-kernel",
        "max_standard": "802.11n",
    },
    "148f:3071": {
        "model": "RT3071",
        "chipset": "RT3071",
        "bands": ["2.4"],
        "driver": "rt2800usb",
        "driver_type": "in-kernel",
        "max_standard": "802.11n",
    },
}

# ------------------------------------------------------------
# النطاقات والقنوات
# ------------------------------------------------------------
BAND_2GHZ_CHANNELS = list(range(1, 15))          # 1-14
BAND_5GHZ_CHANNELS = [
    36, 40, 44, 48, 52, 56, 60, 64,
    100, 104, 108, 112, 116, 120, 124, 128,
    132, 136, 140, 144, 149, 153, 157, 161, 165
]
BAND_6GHZ_CHANNELS = list(range(1, 234, 4))       # تقريبي

BAND_FREQUENCIES = {
    "2.4": {ch: 2407 + ch * 5 for ch in BAND_2GHZ_CHANNELS},
    "5":   {ch: 5000 + ch * 5 for ch in BAND_5GHZ_CHANNELS},
}

# ------------------------------------------------------------
# أنماط التشفير
# ------------------------------------------------------------
ENCRYPTION_TYPES = {
    "OPEN": "مفتوح",
    "WEP": "WEP",
    "WPA": "WPA",
    "WPA2": "WPA2",
    "WPA3": "WPA3",
    "WPA2/WPA3": "WPA2/WPA3 (مختلط)",
    "WPS": "WPS مفعّل",
}

# ------------------------------------------------------------
# حالات المحول
# ------------------------------------------------------------
class AdapterState:
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    MANAGED = "managed"
    MONITOR = "monitor"
    INJECTING = "injecting"
    AP_MODE = "ap_mode"
    ERROR = "error"

# ------------------------------------------------------------
# حالات الهجوم
# ------------------------------------------------------------
class AttackState:
    IDLE = "idle"
    PREPARING = "preparing"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

# ------------------------------------------------------------
# أنواع الهجمات
# ------------------------------------------------------------
class AttackType:
    DEAUTH = "deauth"
    BEACON_FLOOD = "beacon_flood"
    AUTH_FLOOD = "auth_flood"
    PMKID = "pmkid"
    HANDSHAKE = "handshake"
    WPS_PIN = "wps_pin"
    WPS_PIXIE = "wps_pixie"
    EVIL_TWIN = "evil_twin"
    KRACK = "krack"
    FRAGMENTATION = "fragmentation"

# ------------------------------------------------------------
# مستويات التسجيل
# ------------------------------------------------------------
class LogLevel:
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

# ------------------------------------------------------------
# نتائج اختبار الحقن
# ------------------------------------------------------------
INJECTION_THRESHOLDS = {
    "excellent": 50,   # نسبة مئوية
    "good": 30,
    "weak": 15,
    "broken": 0,
}

# ------------------------------------------------------------
# OUI Lookup - مسار قاعدة البيانات المحلية
# ------------------------------------------------------------
OUI_DB_PATH = DATA_DIR / "oui.csv"

# ------------------------------------------------------------
# قوالب بوابة التصيد
# ------------------------------------------------------------
CAPTIVE_PORTAL_TEMPLATES = {
    "generic": TEMPLATES_DIR / "generic.html",
    "router_tplink": TEMPLATES_DIR / "tplink.html",
    "router_netgear": TEMPLATES_DIR / "netgear.html",
    "router_huawei": TEMPLATES_DIR / "huawei.html",
}

# ------------------------------------------------------------
# أوامر النظام (للتحقق من وجودها)
# ------------------------------------------------------------
REQUIRED_TOOLS = [
    "airmon-ng",
    "airodump-ng",
    "aireplay-ng",
    "aircrack-ng",
    "hcxdumptool",
    "hcxpcapngtool",
    "mdk4",
    "reaver",
    "hostapd",
    "dnsmasq",
    "hashcat",
    "iw",
    "ip",
    "ifconfig",
    "lsusb",
    "rfkill",
]

OPTIONAL_TOOLS = [
    "bettercap",
    "wireshark",
    "tshark",
    "bully",
    "wash",
    "wifite",
]
