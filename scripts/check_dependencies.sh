#!/bin/bash
# ============================================================
# Alfa Commander - Dependency Checker
# ============================================================

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo "🔍 فحص تبعيات Alfa Commander..."
echo

REQUIRED=(
    "airmon-ng"
    "airodump-ng"
    "aireplay-ng"
    "aircrack-ng"
    "hcxdumptool"
    "hcxpcapngtool"
    "mdk4"
    "reaver"
    "hostapd"
    "dnsmasq"
    "hashcat"
    "iw"
    "ip"
    "ifconfig"
    "lsusb"
    "rfkill"
)

OPTIONAL=(
    "bettercap"
    "wireshark"
    "tshark"
    "bully"
    "wash"
    "wifite"
    "cap2hccapx"
)

MISSING=()

echo "الأدوات المطلوبة:"
for tool in "${REQUIRED[@]}"; do
    if command -v "$tool" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $tool"
    else
        echo -e "  ${RED}✗${NC} $tool"
        MISSING+=("$tool")
    fi
done

echo
echo "الأدوات الاختيارية:"
for tool in "${OPTIONAL[@]}"; do
    if command -v "$tool" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $tool"
    else
        echo -e "  ${YELLOW}○${NC} $tool (اختياري)"
    fi
done

echo
if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "${RED}أدوات مفقودة:${NC} ${MISSING[*]}"
    echo
    echo "لتثبيتها:"
    echo "  sudo apt update"
    echo "  sudo apt install -y aircrack-ng hcxdumptool hcxtools mdk4 reaver hostapd dnsmasq hashcat iw net-tools usbutils rfkill"
    exit 1
else
    echo -e "${GREEN}✓ كل التبعيات متوفرة${NC}"
fi

echo
echo "فحص شرائح WiFi المدمجة:"
for module in rt2800usb rtl8187 rtl8xxxu mt7601u; do
    if modinfo "$module" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $module"
    else
        echo -e "  ${YELLOW}○${NC} $module (غير متوفر)"
    fi
done

echo
echo "فحص Python:"
python3 --version
python3 -c "import PyQt6; print('PyQt6 ✓')" 2>/dev/null || echo -e "${RED}PyQt6 ✗${NC}"
python3 -c "import scapy; print('Scapy ✓')" 2>/dev/null || echo -e "${YELLOW}Scapy ○${NC}"
