#!/bin/bash
# ============================================================
# Alfa Commander - Fix UI Issues (v2)
# يستخدم str.replace بدلاً من re.sub لتجنب مشاكل Python 3.14
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "============================================================"
echo "  Alfa Commander - Fix UI Issues (v2)"
echo "============================================================"
echo

# ------------------------------------------------------------
# 1) orchestrator.py - منع تكرار البطاقات
# ------------------------------------------------------------
echo "[1/4] إصلاح orchestrator.py..."

python3 << 'PYEOF'
from pathlib import Path

path = Path("app/core/orchestrator.py")
content = path.read_text(encoding="utf-8")

# ابحث عن كتلة التسجيل داخل initialize
import re

# النمط 1: مع self.adapters.clear()
if "self.adapters.clear()" not in content.split("def refresh_adapters")[0]:
    # ابحث عن كتلة initialize واستبدل
    old_block_variants = [
        '''        for adapter in detected:
            adapter_id = adapter.interface
            self.adapters[adapter_id] = adapter
            if adapter.mac:
                self.adapters[adapter.mac] = adapter
            logger.info(f"تسجيل المحول: {adapter_id} -> {adapter.MODEL}")

            self.state.add_adapter(self._adapter_to_state(adapter, adapter_id))''',
        '''        for adapter in detected:
            adapter_id = adapter.mac or adapter.interface
            self.adapters[adapter_id] = adapter

            self.state.add_adapter(self._adapter_to_state(adapter, adapter_id))''',
        '''        for adapter in detected:
            adapter_id = adapter.interface
            self.adapters[adapter_id] = adapter
            logger.info(f"تسجيل المحول: {adapter_id} -> {adapter.MODEL}")

            self.state.add_adapter(self._adapter_to_state(adapter, adapter_id))''',
    ]

    new_block = '''        # امسح القديم لتجنب التكرار
        self.adapters.clear()

        for adapter in detected:
            # استخدم الواجهة كمعرّف وحيد
            adapter_id = adapter.interface
            self.adapters[adapter_id] = adapter
            logger.info(f"تسجيل المحول: {adapter_id} -> {adapter.MODEL}")

            self.state.add_adapter(self._adapter_to_state(adapter, adapter_id))'''

    replaced = False
    for old in old_block_variants:
        if old in content:
            content = content.replace(old, new_block)
            print("  ✓ initialize: تم منع التكرار")
            replaced = True
            break

    if not replaced:
        print("  ○ initialize: النمط غير موجود — تخطي")
else:
    print("  ○ initialize: محدّث مسبقاً")

# refresh_adapters
old_refresh = '''    def refresh_adapters(self) -> int:
        """يعيد اكتشاف المحولات ويسجلها. يعيد العدد."""
        from app.core.adapters import detect_adapters
        
        detected = detect_adapters()
        
        for adapter in detected:
            adapter_id = adapter.interface
            self.adapters[adapter_id] = adapter
            if adapter.mac:
                self.adapters[adapter.mac] = adapter
            logger.info(f"تسجيل: {adapter_id} -> {adapter.MODEL}")
        
        return len(detected)'''

new_refresh = '''    def refresh_adapters(self) -> int:
        """يعيد اكتشاف المحولات ويسجلها. يعيد العدد."""
        from app.core.adapters import detect_adapters

        detected = detect_adapters()

        # امسح القديم
        self.adapters.clear()

        for adapter in detected:
            adapter_id = adapter.interface
            self.adapters[adapter_id] = adapter
            logger.info(f"تسجيل: {adapter_id} -> {adapter.MODEL}")

        return len(detected)'''

if old_refresh in content:
    content = content.replace(old_refresh, new_refresh)
    print("  ✓ refresh_adapters: محدّث")
else:
    print("  ○ refresh_adapters: محدّث مسبقاً أو غير موجود")

path.write_text(content, encoding="utf-8")
PYEOF

# ------------------------------------------------------------
# 2) aireplay.py - مهلة أطول + تفعيل monitor تلقائياً
# ------------------------------------------------------------
echo
echo "[2/4] إصلاح aireplay.py..."

python3 << 'PYEOF'
from pathlib import Path
import re

path = Path("app/core/tools/aireplay.py")
content = path.read_text(encoding="utf-8")

# ابحث عن دالة test_injection القديمة واستبدلها
# سنستخدم split لتفادي مشاكل re.sub

marker_start = "    @staticmethod\n    def test_injection("
marker_end = "    # ---------- هجوم Deauth ----------"

start_idx = content.find(marker_start)
end_idx = content.find(marker_end)

if start_idx == -1 or end_idx == -1:
    print("  ○ test_injection: النمط غير موجود")
else:
    new_test = '''    @staticmethod
    def test_injection(interface: str, timeout: int = 60) -> InjectionTestResult:
        """
        اختبار حقن الحزم مع تحضير تلقائي للواجهة.
        """
        from app.utils.shell import run
        import time

        logger.info(f"اختبار الحقن على {interface} (مهلة {timeout}s)...")

        # 1) تأكد من أن الواجهة موجودة
        check = run(["ip", "link", "show", interface])
        if not check.ok:
            logger.error(f"الواجهة {interface} غير موجودة")
            return InjectionTestResult(
                success=False, ratio=0, quality="broken",
                output=f"الواجهة {interface} غير موجودة"
            )

        # 2) تأكد من أن الواجهة في وضع monitor
        iw_info = run(["iw", "dev", interface, "info"])
        is_monitor = "monitor" in iw_info.stdout.lower()

        if not is_monitor:
            logger.warning(f"الواجهة {interface} ليست في وضع monitor — محاولة التفعيل...")
            run(["ip", "link", "set", interface, "down"])
            run(["iw", interface, "set", "type", "monitor"])
            run(["ip", "link", "set", interface, "up"])
            time.sleep(2)

        # 3) شغّل aireplay-ng -9
        result = run(
            [Aireplay.BINARY, "-9", "--ignore-negative-one", interface],
            timeout=timeout,
        )
        output = result.stdout + result.stderr

        logger.debug(f"aireplay-ng -9 output:\\n{output}")

        # 4) تحليل النتيجة
        ratio_match = re.search(r"(\\d+)/(\\d+)\\s*\\((\\d+(?:\\.\\d+)?)%\\)", output)
        answered = 0
        total = 0
        ratio = 0.0
        if ratio_match:
            answered = int(ratio_match.group(1))
            total = int(ratio_match.group(2))
            ratio = float(ratio_match.group(3))

        # 5) تصنيف الجودة
        from app.constants import INJECTION_THRESHOLDS
        if ratio >= INJECTION_THRESHOLDS["excellent"]:
            quality = "excellent"
        elif ratio >= INJECTION_THRESHOLDS["good"]:
            quality = "good"
        elif ratio >= INJECTION_THRESHOLDS["weak"]:
            quality = "weak"
        else:
            quality = "broken"

        success = "Injection is working" in output or ratio > 0

        if success:
            logger.info(f"الحقن يعمل: {ratio}% ({quality})")
        else:
            logger.warning(f"الحقن لا يعمل: {ratio}% — راجع المخرجات")

        return InjectionTestResult(
            success=success,
            ratio=int(ratio),
            answered=answered,
            total=total,
            quality=quality,
            output=output,
        )

'''
    content = content[:start_idx] + new_test + content[end_idx:]
    print("  ✓ test_injection: محدّث")

path.write_text(content, encoding="utf-8")
PYEOF

# ------------------------------------------------------------
# 3) hardware_tab.py - إزالة التكرار + عرض تفاصيل
# ------------------------------------------------------------
echo
echo "[3/4] إصلاح hardware_tab.py..."

python3 << 'PYEOF'
from pathlib import Path

path = Path("app/gui/tabs/hardware_tab.py")
content = path.read_text(encoding="utf-8")

# ---- استبدل _render_cards لإزالة التكرار ----
# ابحث عن بداية ونهاية الدالة
start = content.find("    def _render_cards(self, adapters")
if start != -1:
    # ابحث عن "# ===" التالي بعد _render_cards
    next_marker = content.find("    # ==", start + 10)
    if next_marker == -1:
        next_marker = content.find("    def ", start + 10)
    
    if next_marker != -1:
        new_render = '''    def _render_cards(self, adapters: list[dict]):
        # إزالة البطاقات القديمة
        for card in self.cards.values():
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()

        # إزالة كل عناصر التخطيط
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not adapters:
            self.summary_label.setText("0 محول")
            self.empty_label.setVisible(True)
            self.scroll.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.scroll.setVisible(True)

        # إزالة التكرار بناءً على (model, interface)
        seen = set()
        unique_adapters = []
        for info in adapters:
            key = (info.get("model"), info.get("interface"))
            if key not in seen:
                seen.add(key)
                unique_adapters.append(info)

        cols = 3
        for i, info in enumerate(unique_adapters):
            card = AdapterCard(info)
            card.test_requested.connect(self._on_test_injection)
            card.prepare_requested.connect(self._on_prepare)
            card.release_requested.connect(self._on_release)
            card.selected.connect(self._on_select)

            row = i // cols
            col = i % cols
            self.cards_layout.addWidget(card, row, col)
            self.cards[info.get("id", str(i))] = card

        self.summary_label.setText(f"{len(unique_adapters)} محول")

'''
        content = content[:start] + new_render + content[next_marker:]
        print("  ✓ _render_cards: محدّث")

path.write_text(content, encoding="utf-8")
PYEOF

# ------------------------------------------------------------
# 4) rt3070.py - تحسين اكتشاف الحقن
# ------------------------------------------------------------
echo
echo "[4/4] إصلاح rt3070.py..."

python3 << 'PYEOF'
from pathlib import Path

path = Path("app/core/adapters/rt3070.py")
content = path.read_text(encoding="utf-8")

# ابحث عن validate_injection واستبدلها
start = content.find("    def validate_injection(self) -> int:")
if start != -1:
    # نهاية الدالة: "        return ratio\n"
    end = content.find("        return ratio\n", start)
    if end != -1:
        end += len("        return ratio\n")
        
        new_validate = '''    def validate_injection(self) -> int:
        """
        اختبار الحقن.
        RT3070 معروف بنسب حقن ممتازة (غالباً > 80%).
        """
        logger.info(f"[{self.MODEL}] اختبار الحقن...")

        # تأكد من أن الواجهة في وضع monitor
        iface = self.get_active_interface()
        if "mon" not in iface and not self.is_monitor():
            logger.warning(f"[{self.MODEL}] الواجهة ليست monitor — تفعيل تلقائي")
            if not self.enter_monitor_mode():
                logger.error(f"[{self.MODEL}] فشل تفعيل المراقبة")
                return 0
            iface = self.get_active_interface()

        ratio = self._run_injection_test()

        if ratio >= 80:
            logger.info(f"[{self.MODEL}] الحقن ممتاز: {ratio}%")
        elif ratio >= 50:
            logger.info(f"[{self.MODEL}] الحقن جيد: {ratio}%")
        elif ratio >= 15:
            logger.warning(f"[{self.MODEL}] الحقن ضعيف: {ratio}%")
            if "ضعف الحقن" not in " ".join(self.warnings):
                self.warnings.append(
                    f"نسبة الحقن منخفضة ({ratio}%). "
                    "قد تحتاج الاقتراب من الهدف."
                )
        else:
            logger.error(f"[{self.MODEL}] الحقن معطل: {ratio}%")
            self.warnings.append(
                "الحقن لا يعمل. راجع مخرجات aireplay-ng --test. "
                "على VMware، قد لا يعمل الحقن بشكل كامل."
            )

        return ratio
'''
        content = content[:start] + new_validate + content[end:]
        print("  ✓ validate_injection: محدّث")

path.write_text(content, encoding="utf-8")
PYEOF

# ------------------------------------------------------------
# التحقق النهائي
# ------------------------------------------------------------
echo
echo "============================================================"
echo "  التحقق النهائي"
echo "============================================================"

python3 << 'PYEOF'
import ast
import sys

files = [
    "app/core/orchestrator.py",
    "app/core/tools/aireplay.py",
    "app/core/adapters/rt3070.py",
    "app/gui/tabs/hardware_tab.py",
]

errors = []
for f in files:
    try:
        ast.parse(open(f).read())
        print(f"  ✓ {f}")
    except SyntaxError as e:
        errors.append(f"  ✗ {f}: {e}")

if errors:
    print()
    for e in errors:
        print(e)
    sys.exit(1)

print()
print("✓ كل الملفات صحيحة نحوياً")
PYEOF

echo
echo "============================================================"
echo "  اكتملت الإصلاحات!"
echo "============================================================"
echo
echo "شغّل البرنامج الآن:"
echo "  sudo .venv/bin/python3 main.py"
echo
echo "ثم:"
echo "  1) اضغط 🔄 تحديث (يجب أن يظهر محول واحد فقط)"
echo "  2) اضغط 🧪 فحص الحقن"
echo "  3) اضغط ▶ تجهيز"
