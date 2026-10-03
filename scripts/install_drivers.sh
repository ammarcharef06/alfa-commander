#!/bin/bash
# ============================================================
# Alfa Commander - Driver Installer
# تثبيت التعريفات الخارجية لمحولات Alfa
# ============================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "يجب التشغيل كـ root: sudo bash $0"
    exit 1
fi

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo "📦 تثبيت متطلبات البناء..."
apt update
apt install -y git dkms build-essential linux-headers-$(uname -r)

echo
echo "🔍 فحص المحولات المتصلة..."
lsusb | grep -i "0bda\|0e8d" || echo "  لا يوجد محول Alfa"

echo
echo "خيارات التثبيت:"
echo "  1) RTL8812AU (AWUS036ACH/AC)"
echo "  2) RTL8814AU (AWUS1900)"
echo "  3) كل التعريفات"
echo "  4) خروج"
read -p "اختر [1-4]: " choice

install_8812au() {
    echo
    echo -e "${YELLOW}تثبيت RTL8812AU...${NC}"
    cd /tmp
    rm -rf rtl8812au
    git clone https://github.com/aircrack-ng/rtl8812au.git
    cd rtl8812au
    make dkms_install
    modprobe 8812au
    echo -e "${GREEN}✓ تم تثبيت 8812au${NC}"
}

install_8814au() {
    echo
    echo -e "${YELLOW}تثبيت RTL8814AU...${NC}"
    cd /tmp
    rm -rf rtl8814au
    git clone https://github.com/aircrack-ng/rtl8814au.git
    cd rtl8814au
    make dkms_install
    modprobe 8814au
    echo -e "${GREEN}✓ تم تثبيت 8814au${NC}"
}

case $choice in
    1) install_8812au ;;
    2) install_8814au ;;
    3) install_8812au; install_8814au ;;
    4) exit 0 ;;
    *) echo "خيار غير صالح"; exit 1 ;;
esac

echo
echo -e "${GREEN}✓ اكتمل التثبيت${NC}"
echo "أعد توصيل المحول الآن."
