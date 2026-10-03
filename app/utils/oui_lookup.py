# ============================================================
# Alfa Commander - OUI Lookup
# التعرف على الشركة المصنعة من MAC
# ============================================================

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from app.constants import OUI_DB_PATH
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# الشركات المعروفة (fallback مدمج)
# ------------------------------------------------------------
KNOWN_OUIS = {
    "00:1A:2B": "Alfa Network",
    "00:0C:43": "Alfa Network",
    "00:15:6D": "Alfa Network",
    "00:1F:1F": "Alfa Network",
    "00:C0:CA": "Alfa Network",
    "00:E0:4C": "Realtek",
    "00:1C:F0": "D-Link",
    "00:1E:58": "D-Link",
    "00:14:D1": "TRENDnet",
    "00:1D:7E": "Cisco-Linksys",
    "00:22:6B": "Cisco-Linksys",
    "00:1F:33": "Netgear",
    "00:24:B2": "Netgear",
    "00:26:F2": "Netgear",
    "00:25:9C": "Cisco",
    "00:1B:2F": "Netgear",
    "00:18:39": "Cisco-Linksys",
    "00:23:69": "Cisco-Linksys",
    "00:1C:10": "Cisco-Linksys",
    "00:1D:7E": "Cisco-Linksys",
    "F4:EC:38": "TP-Link",
    "50:C7:BF": "TP-Link",
    "A0:F3:C1": "TP-Link",
    "B0:4E:26": "TP-Link",
    "C0:25:E9": "TP-Link",
    "E8:DE:27": "TP-Link",
    "00:1E:58": "D-Link",
    "14:D6:4D": "D-Link",
    "28:10:7B": "D-Link",
    "84:C9:B2": "D-Link",
    "B8:A3:86": "D-Link",
    "FC:75:16": "D-Link",
    "00:0C:29": "VMware",
    "00:05:69": "VMware",
    "00:50:56": "VMware",
    "08:00:27": "VirtualBox",
    "00:16:3E": "Xen",
    "52:54:00": "QEMU",
    "00:1A:11": "Google",
    "3C:5A:B4": "Google",
    "F4:F5:D8": "Google",
    "00:17:88": "Philips",
    "B0:BE:76": "TP-Link",
    "DC:0C:5C": "Apple",
    "00:03:93": "Apple",
    "00:1B:63": "Apple",
    "00:1E:C2": "Apple",
    "00:23:DF": "Apple",
    "00:25:00": "Apple",
    "00:26:08": "Apple",
    "F0:18:98": "Apple",
    "F4:0F:24": "Apple",
    "AC:61:EA": "Apple",
    "28:CF:E9": "Apple",
    "3C:07:54": "Apple",
    # Ralink / MediaTek (بعد شراء Ralink من قبل MediaTek)
    "00:0C:43": "Ralink Technology",
    "00:0E:2E": "Ralink Technology",
    "00:11:6B": "Ralink Technology",
    "00:13:EF": "Ralink Technology",
    "00:15:6D": "Ralink Technology",
    "00:17:7C": "Ralink Technology",
    "00:1A:2B": "Ralink Technology",
    "00:1C:10": "Ralink Technology",
    "00:1F:1F": "Ralink Technology",
    "00:21:6A": "Ralink Technology",
    "00:23:CD": "Ralink Technology",
    "00:24:A5": "Ralink Technology",
    "00:26:5A": "Ralink Technology",
    "00:27:19": "Ralink Technology",
    "1C:BF:CE": "Ralink Technology",
    "28:2C:B2": "Ralink Technology",
    "38:83:45": "Ralink Technology",
    "4C:17:44": "Ralink Technology",
    "50:9E:76": "Ralink Technology",
    "70:F1:1C": "Ralink Technology",
    "7C:DD:90": "Ralink Technology",
    "9C:D2:1E": "Ralink Technology",
    "A0:F3:C1": "Ralink Technology",
    "B0:48:7A": "Ralink Technology",
    "C0:4A:00": "Ralink Technology",
    "D8:5D:4C": "Ralink Technology",
    "E0:46:9A": "Ralink Technology",
    "F4:EC:38": "Ralink Technology",
}


# ------------------------------------------------------------
# الشركة المصنعة
# ------------------------------------------------------------
def lookup(mac: str) -> str:
    """
    يرجع الشركة المصنعة لـ MAC.
    يبحث أولاً في قاعدة البيانات المحملة، ثم fallback.
    """
    if not mac:
        return "غير معروف"

    normalized = mac.replace("-", ":").upper()
    oui = ":".join(normalized.split(":")[:3])

    # القاعدة المحملة
    if _oui_cache is not None and oui in _oui_cache:
        return _oui_cache[oui]

    # fallback
    if oui in KNOWN_OUIS:
        return KNOWN_OUIS[oui]

    # محلي الإدارة؟
    try:
        first = int(normalized.split(":")[0], 16)
        if first & 0x02:
            return "محلي (عشوائي)"
    except Exception:
        pass

    return "غير معروف"


# ------------------------------------------------------------
# قاعدة بيانات OUI المحملة
# ------------------------------------------------------------
_oui_cache: Optional[dict[str, str]] = None


def load_oui_database(path: Optional[Path] = None) -> int:
    """
    يحمّل قاعدة بيانات OUI من ملف CSV.
    الصيغة المتوقعة: OUI,Vendor
    يرجع عدد السجلات المحملة.
    """
    global _oui_cache

    path = path or OUI_DB_PATH
    if not path.exists():
        logger.info(f"ملف OUI غير موجود: {path}، سيتم استخدام القاعدة المدمجة.")
        _oui_cache = {}
        return 0

    cache: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                oui = row[0].strip().upper().replace("-", ":")
                if not re.match(r"^[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}$", oui):
                    continue
                cache[oui] = row[1].strip()
    except Exception as e:
        logger.exception(f"فشل تحميل OUI: {e}")
        return 0

    _oui_cache = cache
    logger.info(f"تم تحميل {len(cache)} سجل OUI.")
    return len(cache)


def download_oui_database(url: Optional[str] = None, dest: Optional[Path] = None) -> bool:
    """
    يحمّل قاعدة بيانات OUI من الإنترنت.
    المصدر الافتراضي: IEEE OUI CSV.
    """
    import urllib.request

    url = url or "https://standards-oui.ieee.org/oui/oui.csv"
    dest = dest or OUI_DB_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        logger.info(f"جارٍ تحميل OUI من {url}...")
        urllib.request.urlretrieve(url, dest)
        logger.info(f"تم الحفظ في {dest}")
        return True
    except Exception as e:
        logger.exception(f"فشل التحميل: {e}")
        return False


def is_known_vendor(mac: str) -> bool:
    return lookup(mac) != "غير معروف"


def vendor_or_unknown(mac: str) -> str:
    return lookup(mac)
