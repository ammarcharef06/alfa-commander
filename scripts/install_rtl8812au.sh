#!/bin/bash
# تثبيت RTL8812AU فقط
set -e

if [ "$EUID" -ne 0 ]; then
    echo "sudo bash $0"; exit 1
fi

apt install -y git dkms build-essential linux-headers-$(uname -r)
cd /tmp
rm -rf rtl8812au
git clone https://github.com/aircrack-ng/rtl8812au.git
cd rtl8812au
make dkms_install
modprobe 8812au
echo "✓ 8812au installed"
