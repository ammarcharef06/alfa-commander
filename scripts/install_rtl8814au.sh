#!/bin/bash
# تثبيت RTL8814AU فقط
set -e

if [ "$EUID" -ne 0 ]; then
    echo "sudo bash $0"; exit 1
fi

apt install -y git dkms build-essential linux-headers-$(uname -r)
cd /tmp
rm -rf rtl8814au
git clone https://github.com/aircrack-ng/rtl8814au.git
cd rtl8814au
make dkms_install
modprobe 8814au
echo "✓ 8814au installed"
