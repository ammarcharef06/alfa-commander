#!/bin/bash
# إعداد udev لمحولات Alfa
set -e

if [ "$EUID" -ne 0 ]; then
    echo "sudo bash $0"; exit 1
fi

cat > /etc/udev/rules.d/70-alfa-wifi.rules << 'EOF'
# Alfa Commander - udev rules
# RTL8187L
SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="8187", MODE="0666", GROUP="netdev"
# RTL8812AU
SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="8812", MODE="0666", GROUP="netdev"
# RTL8814AU
SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="8814", MODE="0666", GROUP="netdev"
# MT7610U
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="7610", MODE="0666", GROUP="netdev"
# MT7921AUN
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="7961", MODE="0666", GROUP="netdev"
EOF

udevadm control --reload-rules
udevadm trigger

echo "✓ تم إعداد udev"
echo "قد يحتاج المستخدم أن يكون ضمن مجموعة netdev:"
echo "  sudo usermod -aG netdev \$USER"
