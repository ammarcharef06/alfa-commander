#!/bin/bash
# ============================================================
# Alfa Commander - Integration Fix Script
# يصلح كل الملفات اللازمة لدعم RT3070 وأي شريحة جديدة
# ============================================================

set -e

# ألوان
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "============================================================"
echo "  Alfa Commander - Integration Fix"
echo "  المسار: $PROJECT_ROOT"
echo "============================================================"
echo

# ------------------------------------------------------------
# دالة مساعدة: التحقق من وجود نص في ملف
# ------------------------------------------------------------
has_text() {
    grep -qF "$1" "$2" 2>/dev/null
}

# ------------------------------------------------------------
# دالة مساعدة: إضافة نص في نهاية ملف إذا لم يكن موجوداً
# ------------------------------------------------------------
append_if_missing() {
    local file="$1"
    local marker="$2"
    local content="$3"
    
    if ! has_text "$marker" "$file"; then
        echo "$content" >> "$file"
        echo -e "  ${GREEN}✓${NC} أُضيف إلى: $file"
    else
        echo -e "  ${YELLOW}○${NC} موجود مسبقاً: $file"
    fi
}

# ============================================================
# 1) registry.py - إضافة RT3070Adapter
# ============================================================
echo "[1/10] تعديل registry.py..."

REGISTRY="app/core/adapters/registry.py"

if ! has_text "from app.core.adapters.rt3070 import RT3070Adapter" "$REGISTRY"; then
    # أضف الاستيراد بعد آخر استيراد موجود
    sed -i '/from app.core.adapters.mt7921aun import MT7921AUNAdapter/a from app.core.adapters.rt3070 import RT3070Adapter' "$REGISTRY"
    echo -e "  ${GREEN}✓${NC} أُضيف استيراد RT3070Adapter"
fi

if ! has_text '"148f:3070": RT3070Adapter' "$REGISTRY"; then
    # أضف RT3070 إلى ADAPTER_REGISTRY قبل آخر }
    python3 << 'PYEOF'
import re
from pathlib import Path

path = Path("app/core/adapters/registry.py")
content = path.read_text(encoding="utf-8")

# أضف RT3070 إلى ADAPTER_REGISTRY
if "148f:3070" not in content:
    rt_entries = '''
    # Ralink RT2870/RT3070/RT3572
    "148f:3070": RT3070Adapter,
    "148f:2870": RT3070Adapter,
    "148f:3572": RT3070Adapter,
    "148f:3071": RT3070Adapter,
'''
    # ابحث عن إغلاق ADAPTER_REGISTRY (أول } بعد ADAPTER_REGISTRY)
    pattern = r'(ADAPTER_REGISTRY[^}]+)(\})'
    match = re.search(pattern, content)
    if match:
        content = content[:match.end(1)] + rt_entries + content[match.end(1):]

# أضف RT3070 إلى MODEL_REGISTRY
if '"AWUS036NH"' not in content:
    model_entries = '''    # Ralink
    "AWUS036NH": RT3070Adapter,
    "AWUS036NEH": RT3070Adapter,
    "AWUS051NH": RT3070Adapter,
    "RT3070": RT3070Adapter,
    "RT2870": RT3070Adapter,
    "RT3572": RT3070Adapter,
'''
    pattern = r'(MODEL_REGISTRY[^}]+)(\})'
    match = re.search(pattern, content)
    if match:
        content = content[:match.end(1)] + model_entries + content[match.end(1):]

path.write_text(content, encoding="utf-8")
print("  ✓ registry.py محدث")
PYEOF
fi

# ============================================================
# 2) __init__.py - تصدير RT3070Adapter
# ============================================================
echo "[2/10] تعديل adapters/__init__.py..."

INIT="app/core/adapters/__init__.py"

if ! has_text "from app.core.adapters.rt3070 import RT3070Adapter" "$INIT"; then
    sed -i '/from app.core.adapters.mt7921aun import MT7921AUNAdapter/a from app.core.adapters.rt3070 import RT3070Adapter' "$INIT"
    echo -e "  ${GREEN}✓${NC} أُضيف استيراد"
fi

if ! has_text '"RT3070Adapter"' "$INIT"; then
    sed -i 's/"MT7921AUNAdapter",/"MT7921AUNAdapter",\n    "RT3070Adapter",/' "$INIT"
    echo -e "  ${GREEN}✓${NC} أُضيف إلى __all__"
fi

# ============================================================
# 3) iw.py - دوال module-level
# ============================================================
echo "[3/10] تعديل iw.py..."

append_if_missing "app/core/tools/iw.py" \
    "# Module-level shortcuts" \
    '

# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def list_interfaces() -> list[str]:
    return IW.list_interfaces()


def list_wireless_interfaces() -> list[str]:
    return IW.list_interfaces()


def get_info(iface: str):
    return IW.get_interface_info(iface)


def get_phy_info(phy: str):
    return IW.get_phy_info(phy)


def set_mode(iface: str, mode: str):
    return IW.set_mode(iface, mode)


def set_monitor_mode(iface: str):
    return IW.set_monitor_mode(iface)


def set_managed_mode(iface: str):
    return IW.set_managed_mode(iface)


def set_channel(iface: str, channel: int):
    return IW.set_channel(iface, channel)


def get_channel(iface: str):
    return IW.get_channel(iface)


def set_interface_up(iface: str):
    return IW.set_interface_up(iface)


def set_interface_down(iface: str):
    return IW.set_interface_down(iface)


def set_txpower(iface: str, dbm: int):
    return IW.set_txpower(iface, dbm)


def scan(iface: str, timeout: int = 15):
    return IW.scan(iface, timeout)


def get_regulatory_domain() -> str:
    return IW.get_regulatory_domain()


def set_regulatory_domain(country: str):
    return IW.set_regulatory_domain(country)


def enable_monitor(iface: str):
    return IW.set_monitor_mode(iface)


def disable_monitor(iface: str):
    return IW.set_managed_mode(iface)
'

# ============================================================
# 4) airmon.py - دوال module-level
# ============================================================
echo "[4/10] تعديل airmon.py..."

append_if_missing "app/core/tools/airmon.py" \
    "# Module-level shortcuts" \
    '

# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def check():
    return Airmon.check()


def check_kill():
    return Airmon.check_kill()


def start(iface: str, channel=None):
    return Airmon.start(iface, channel)


def stop(monitor_iface: str):
    return Airmon.stop(monitor_iface)


def list_interfaces():
    return Airmon.list_interfaces()
'

# ============================================================
# 5) aireplay.py - دوال module-level
# ============================================================
echo "[5/10] تعديل aireplay.py..."

append_if_missing "app/core/tools/aireplay.py" \
    "# Module-level shortcuts" \
    '

# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def test_injection(iface: str, timeout: int = 30):
    return Aireplay.test_injection(iface, timeout)


def deauth(opts, timeout=None):
    return Aireplay.deauth(opts, timeout)


def fake_auth(iface: str, bssid: str, delay: int = 1):
    return Aireplay.fake_auth(iface, bssid, delay)


def arp_replay(iface: str, bssid: str, count: int = 0):
    return Aireplay.arp_replay(iface, bssid, count)


def chopchop(iface: str, bssid: str):
    return Aireplay.chopchop(iface, bssid)


def fragmentation(iface: str, bssid: str):
    return Aireplay.fragmentation(iface, bssid)


def interactive(iface: str):
    return Aireplay.interactive(iface)


def reason_name(code: int) -> str:
    return Aireplay.reason_name(code)
'

# ============================================================
# 6) airodump.py - دوال module-level
# ============================================================
echo "[6/10] تعديل airodump.py..."

append_if_missing "app/core/tools/airodump.py" \
    "# Module-level shortcuts" \
    '

# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def build_command(opts):
    return Airodump.build_command(opts)


def scan(opts, duration: int = 30):
    return Airodump.scan(opts, duration)


def scan_streaming(opts, on_network=None, on_client=None, on_line=None):
    return Airodump.scan_streaming(opts, on_network, on_client, on_line)


def parse_csv(prefix):
    return Airodump.parse_csv(prefix)
'

# ============================================================
# 7) mdk4.py - دوال module-level
# ============================================================
echo "[7/10] تعديل mdk4.py..."

append_if_missing "app/core/tools/mdk4.py" \
    "# Module-level shortcuts" \
    '

# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def build_command(mode: str, interface: str, extra: list):
    return MDK4.build_command(mode, interface, extra)


def beacon_flood(opts):
    return MDK4.beacon_flood(opts)


def auth_flood(opts):
    return MDK4.auth_flood(opts)


def deauth_flood(opts):
    return MDK4.deauth_flood(opts)


def eapol_logoff(interface: str, bssid: str, client=None):
    return MDK4.eapol_logoff(interface, bssid, client)


def probe_flood(interface: str, ssid_list_file=None):
    return MDK4.probe_flood(interface, ssid_list_file)


def wids_confusion(interface: str, bssid: str, count: int = 0):
    return MDK4.wids_confusion(interface, bssid, count)


def michael_shutdown(interface: str, bssid: str):
    return MDK4.michael_shutdown(interface, bssid)


def amok(interface: str, channel: int = 1):
    return MDK4.amok(interface, channel)
'

# ============================================================
# 8) hcxdumptool.py - دوال module-level
# ============================================================
echo "[8/10] تعديل hcxdumptool.py..."

append_if_missing "app/core/tools/hcxdumptool.py" \
    "# Module-level shortcuts" \
    '

# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def build_command(opts):
    return HCXDumptool.build_command(opts)


def capture(opts):
    return HCXDumptool.capture(opts)


def convert_to_hashcat(pcapng_file, output_file=None):
    return HCXDumptool.convert_to_hashcat(pcapng_file, output_file)


def parse_capture_results(pcapng_file):
    return HCXDumptool.parse_capture_results(pcapng_file)


def capture_and_convert(opts, timeout: int = 120):
    return HCXDumptool.capture_and_convert(opts, timeout)
'

# ============================================================
# 9) reaver.py - دوال module-level
# ============================================================
echo "[9/10] تعديل reaver.py..."

append_if_missing "app/core/tools/reaver.py" \
    "# Module-level shortcuts" \
    '

# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def build_command(opts):
    return Reaver.build_command(opts)


def attack(opts):
    return Reaver.attack(opts)


def parse_output(output: str):
    return Reaver.parse_output(output)


def wash_scan(iface: str, timeout: int = 30):
    return Reaver.wash_scan(iface, timeout)


def parse_wash_output(output: str):
    return Reaver.parse_wash_output(output)
'

# ============================================================
# 10) oui_lookup.py - إضافة Ralink
# ============================================================
echo "[10/10] تعديل oui_lookup.py..."

if ! has_text "Ralink Technology" "app/utils/oui_lookup.py"; then
    python3 << 'PYEOF'
import re
from pathlib import Path

path = Path("app/utils/oui_lookup.py")
content = path.read_text(encoding="utf-8")

ralink_entries = '''    # Ralink Technology (RT2870/RT3070/RT3572)
    "00:0E:2E": "Ralink Technology",
    "00:11:6B": "Ralink Technology",
    "00:13:EF": "Ralink Technology",
    "00:17:7C": "Ralink Technology",
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
    "B0:48:7A": "Ralink Technology",
    "C0:4A:00": "Ralink Technology",
    "D8:5D:4C": "Ralink Technology",
    "E0:46:9A": "Ralink Technology",
    # MediaTek
    "00:0C:E7": "MediaTek",
    "00:0E:8E": "MediaTek",
'''

# أضف قبل إغلاق KNOWN_OUIS
pattern = r'(KNOWN_OUIS\s*=\s*\{[^}]+)(\})'
match = re.search(pattern, content)
if match:
    content = content[:match.end(1)] + ralink_entries + content[match.end(1):]
    path.write_text(content, encoding="utf-8")
    print("  ✓ oui_lookup.py محدث")
PYEOF
else
    echo -e "  ${YELLOW}○${NC} موجود مسبقاً"
fi

# ============================================================
# التحقق النهائي
# ============================================================
echo
echo "============================================================"
echo "  التحقق من التعديلات"
echo "============================================================"
echo

python3 << 'PYEOF'
import sys
errors = []

# 1) اختبار استيراد كل شيء
try:
    from app.core.adapters import RT3070Adapter, detect_adapters
    print("  ✓ RT3070Adapter مستورد")
except Exception as e:
    errors.append(f"  ✗ RT3070Adapter: {e}")

try:
    from app.core.adapters.registry import ADAPTER_REGISTRY, MODEL_REGISTRY
    assert "148f:3070" in ADAPTER_REGISTRY, "148f:3070 غير موجود في ADAPTER_REGISTRY"
    assert "AWUS036NH" in MODEL_REGISTRY, "AWUS036NH غير موجود في MODEL_REGISTRY"
    print(f"  ✓ registry.py: {len(ADAPTER_REGISTRY)} محول مسجل")
except Exception as e:
    errors.append(f"  ✗ registry: {e}")

# 2) اختبار module-level
tools_check = {
    "iw": ["get_info", "list_interfaces"],
    "ip": ["get_interface_mac"],
    "airmon": ["start", "stop"],
    "aireplay": ["test_injection"],
    "airodump": ["scan", "scan_streaming"],
    "mdk4": ["beacon_flood"],
    "hcxdumptool": ["capture"],
    "reaver": ["attack"],
}

for tool, funcs in tools_check.items():
    try:
        mod = __import__(f"app.core.tools.{tool}", fromlist=[tool])
        for f in funcs:
            if not hasattr(mod, f):
                errors.append(f"  ✗ {tool}.{f} غير موجود")
        print(f"  ✓ {tool}: دوال module-level موجودة")
    except Exception as e:
        errors.append(f"  ✗ {tool}: {e}")

# 3) اختبار OUI lookup
try:
    from app.utils.oui_lookup import lookup
    result = lookup("00:0E:2E:11:22:33")
    assert result == "Ralink Technology", f"lookup أعاد: {result}"
    print(f"  ✓ oui_lookup: Ralink")
except Exception as e:
    errors.append(f"  ✗ oui_lookup: {e}")

# 4) اختبار اكتشاف المحولات الفعلي
try:
    adapters = detect_adapters()
    print(f"  ✓ اكتشاف المحولات: {len(adapters)} محول")
    for a in adapters:
        print(f"      → {a.MODEL} ({a.CHIPSET}) على {a.interface}")
except Exception as e:
    errors.append(f"  ✗ detect_adapters: {e}")

# النتيجة النهائية
print()
if errors:
    print("⚠ يوجد أخطاء:")
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("✓ كل التعديلات نجحت")
PYEOF

echo
echo "============================================================"
echo "  تشغيل البرنامج الآن:"
echo "    sudo bash scripts/run.sh"
echo "============================================================"
