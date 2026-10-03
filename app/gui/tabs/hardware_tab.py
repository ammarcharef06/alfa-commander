# ============================================================
# Alfa Commander - Hardware Tab
# تبويب إدارة محولات Alfa
# ============================================================

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QMessageBox, QFrame,
    QGridLayout, QSizePolicy,
)

from app.gui.signal_bus import get_signal_bus
from app.gui.widgets.adapter_card import AdapterCard
from app.logger import get_logger

logger = get_logger()


class HardwareTab(QWidget):
    """تبويب عرض وإدارة محولات Alfa المتصلة."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = get_signal_bus()
        self.cards: dict[str, AdapterCard] = {}

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- الرأس ----
        header = QHBoxLayout()

        title = QLabel("🔧 محولات Alfa المتصلة")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        self.summary_label = QLabel("جارٍ الفحص...")
        self.summary_label.setObjectName("subtitle")
        header.addWidget(self.summary_label)

        self.refresh_btn = QPushButton("🔄 تحديث")
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)

        layout.addLayout(header)

        # ---- خط فاصل ----
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #313244;")
        layout.addWidget(line)

        # ---- منطقة البطاقات ----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; }")

        self.container = QWidget()
        self.cards_layout = QGridLayout(self.container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

        # ---- رسالة "لا محولات" ----
        self.empty_label = QLabel(
            "لا يوجد محول Alfa متصل.\n"
            "تأكد من توصيل المحول ثم اضغط 'تحديث'."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            "color: #6c7086; font-size: 13pt; padding: 40px;"
        )
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        # ---- شريط الحالة السفلي ----
        bottom = QHBoxLayout()

        self.driver_btn = QPushButton("📦 تثبيت التعريفات المفقودة")
        self.driver_btn.clicked.connect(self._install_drivers)
        bottom.addWidget(self.driver_btn)

        bottom.addStretch()

        self.details_btn = QPushButton("ℹ تفاصيل")
        self.details_btn.clicked.connect(self._show_details)
        bottom.addWidget(self.details_btn)

        layout.addLayout(bottom)

    def _connect_signals(self):
        self.bus.adapter_ready.connect(lambda _: self.refresh())
        self.bus.adapter_failed.connect(lambda _: self.refresh())
        self.bus.adapter_changed.connect(lambda _: self.refresh())

    # ============================================================
    # التحديث
    # ============================================================
    @pyqtSlot()
    def refresh(self):
        """إعادة قراءة المحولات المتصلة."""
        self.refresh_btn.setEnabled(False)
        self.summary_label.setText("جارٍ الفحص...")

        QTimer.singleShot(50, self._do_refresh)

    def _do_refresh(self):
        try:
            from app.core import get_orchestrator
            orch = get_orchestrator()

            # إذا كان المنسق مهيأً
            if orch.adapters:
                adapters_info = [
                    a.describe() for a in orch.adapters.values()
                ]
            else:
                # تهيئة سريعة بدون حقن
                from app.core.adapters import detect_adapters
                detected = detect_adapters()
                adapters_info = [a.describe() for a in detected]

            self._render_cards(adapters_info)

        except Exception as e:
            logger.exception(f"فشل التحديث: {e}")
            self.summary_label.setText("خطأ في التحديث")
        finally:
            self.refresh_btn.setEnabled(True)

    def _render_cards(self, adapters: list[dict]):
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

    # ============================================================
    # إجراءات البطاقات
    # ============================================================
    def _on_select(self, adapter_id: str):
        from app.state import get_state
        get_state().set_active_adapter(adapter_id)
        self.bus.adapter_changed.emit(adapter_id)

    def _find_adapter(self, adapter_id: str):
        """يبحث عن المحول بعدة طرق."""
        from app.core import get_orchestrator
        orch = get_orchestrator()
        
        # 0) إذا فارغة، أعد الاكتشاف
        if not orch.adapters:
            try:
                orch.refresh_adapters()
            except Exception as e:
                logger.exception(f"فشل refresh: {e}")
        
        # 1) بحث مباشر
        adapter = orch.get_adapter(adapter_id)
        if adapter:
            for k, v in orch.adapters.items():
                if v is adapter:
                    return adapter, k
        
        # 2) بحث مرن
        aid = adapter_id.upper()
        for key, a in orch.adapters.items():
            if not a:
                continue
            if (a.mac and a.mac.upper() == aid) or \
               (a.interface and a.interface.upper() == aid) or \
               (a.monitor_interface and a.monitor_interface.upper() == aid):
                return a, key
        
        # 3) إذا واحد فقط، استخدمه
        unique = {id(v): (k, v) for k, v in orch.adapters.items() if v}
        if len(unique) == 1:
            k, a = next(iter(unique.values()))
            return a, k
        
        return None, None

    def _on_test_injection(self, adapter_id: str):
        from app.core import get_orchestrator
        orch = get_orchestrator()

        adapter, real_id = self._find_adapter(adapter_id)
        if not adapter:
            QMessageBox.warning(
                self, "خطأ",
                f"المحول غير معروف: {adapter_id}\n"
                f"المتاح: {list(orch.adapters.keys())}"
            )
            return

        self.summary_label.setText(f"فحص الحقن على {adapter.MODEL}...")

        def _done(result, error):
            if error:
                self.summary_label.setText(f"فشل الفحص: {error}")
                return
            ratio = result.ratio if result else 0
            self.summary_label.setText(
                f"نسبة الحقن على {adapter.MODEL}: {ratio}%"
            )
            # تحديث البطاقة
            if adapter_id in self.cards:
                self.cards[adapter_id].set_injection_ratio(ratio)

        coro = orch.prepare_adapter(real_id, test_injection=True)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)
        else:
            QMessageBox.warning(self, "خطأ", "لا يمكن تشغيل الفحص.")

    def _on_prepare(self, adapter_id: str):
        from app.core import get_orchestrator
        orch = get_orchestrator()

        adapter, real_id = self._find_adapter(adapter_id)
        if not adapter:
            QMessageBox.warning(self, "خطأ", f"المحول غير معروف: {adapter_id}")
            return

        self.summary_label.setText("جارٍ تجهيز المحول...")

        def _done(result, error):
            if error:
                QMessageBox.critical(self, "فشل", str(error))
                self.summary_label.setText("فشل التجهيز")
                return

            ratio = result.ratio if result else 0
            self.summary_label.setText(f"جاهز (حقن: {ratio}%)")

            if adapter_id in self.cards:
                self.cards[adapter_id].set_state("monitor")
                self.cards[adapter_id].set_injection_ratio(ratio)

            QMessageBox.information(
                self, "جاهز",
                f"تم تجهيز المحول.\nنسبة الحقن: {ratio}%\n"
                f"التوصية: {result.recommended_attack if result else '—'}"
            )

        coro = orch.prepare_adapter(real_id, test_injection=True)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    def _on_release(self, adapter_id: str):
        from app.core import get_orchestrator
        orch = get_orchestrator()

        adapter, real_id = self._find_adapter(adapter_id)
        if not adapter:
            return

        def _done(_, error):
            if error:
                QMessageBox.critical(self, "فشل", str(error))
                return
            if adapter_id in self.cards:
                self.cards[adapter_id].set_state("managed")
            self.summary_label.setText("تم التحرير")

        coro = orch.release_adapter(real_id)
        win = self.window()
        if hasattr(win, "async_worker"):
            win.async_worker.run_coroutine(coro, _done)

    # ============================================================
    # أدوات إضافية
    # ============================================================
    def _install_drivers(self):
        QMessageBox.information(
            self, "تثبيت التعريفات",
            "افتح طرفية و شغّل:\n\n"
            "sudo bash scripts/install_drivers.sh"
        )

    def _show_details(self):
        from app.core.adapters import list_supported_models

        models = list_supported_models()
        text = "<h3>المحولات المدعومة:</h3><ul>"
        for m in models:
            text += (
                f"<li><b>{m['model']}</b> ({m['chipset']}) — "
                f"{', '.join(m['bands'])}GHz — {m['max_standard']}"
                f"</li>"
            )
        text += "</ul>"

        box = QMessageBox(self)
        box.setWindowTitle("تفاصيل")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(text)
        box.exec()
