#!/bin/bash
# ============================================================
# Alfa Commander - Launch Script
# ============================================================

cd "$(dirname "$0")/.."

if [ "$EUID" -ne 0 ]; then
    echo "⚠ البرنامج يحتاج صلاحيات root."
    echo "سيُطلب منك كلمة المرور..."
    exec sudo -E python3 main.py "$@"
fi

exec python3 main.py "$@"
