# Alfa Commander

> منصة اختبار اختراق لاسلكي متكاملة، مبنية خصيصاً لمحولات Alfa.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## ⚠️ تحذير قانوني

هذه الأداة للاستخدام **التعليمي والأخلاقي** فقط.
لا تستخدمها ضد أي شبكة لا تملكها أو لا تملك تصريحاً كتابياً باختبارها.
استخدامها ضد شبكات الآخرين **جريمة إلكترونية** في معظم دول العالم.

## المميزات

- ✅ دعم كل محولات Alfa (من AWUS036H الكلاسيكي إلى AXML الحديث)
- ✅ كشف تلقائي للشرائح والقدرات
- ✅ مسح متقدم مع قفز ذكي بين القنوات
- ✅ هجمات Deauth, Beacon Flood, Auth Flood, WPS
- ✅ التقاط Handshake و PMKID تلقائياً
- ✅ كسر عبر hashcat و aircrack-ng
- ✅ Evil Twin مع بوابة تصيد
- ✅ واجهة رسومية كاملة (PyQt6)
- ✅ دعم RTL (العربية)

## المتطلبات

- Kali Linux 2023+ أو أي توزيعة debian-based
- Python 3.11+
- محول Alfa (036H, ACH, 1900, ACHM, AXM...)
- صلاحيات root

## التثبيت

```bash
# 1) استنساخ المشروع
git clone <repo>
cd alfa-commander

# 2) تثبيت التبعيات
sudo bash scripts/check_dependencies.sh
sudo bash scripts/install_drivers.sh   # لـ ACH و 1900

# 3) بيئة Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4) التشغيل
sudo bash scripts/run.sh
