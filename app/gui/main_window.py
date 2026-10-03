# ============================================================
# Alfa Commander - Main Window
# النافذة الرئيسية
# ============================================================

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize, QMetaObject, Q_ARG
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QCloseEvent
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QMessageBox, QToolBar, QMenuBar, QFileDialog,
    QStatusBar, QSplitter, QApplication,
)

from app.constants import APP_NAME, APP_VERSION, DATA_DIR, EVIDENCE_DIR
from app.config import get_config
from app.gui.signal_bus import get_signal_bus, emit_threadsafe
from app.gui.widgets.status_bar import StatusBarWidget
from app.gui.widgets.log_console import LogConsole
from app.logger import get_logger, attach_gui_callback

logger = get_logger()


# ------------------------------------------------------------
# حلقة asyncio في خيط منفصل
# ------------------------------------------------------------
class AsyncWorker:
    """يدير حلقة asyncio في خيط منفصل."""

    _instance: Optional["AsyncWorker"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self._started = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self._started.wait(timeout=5)

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._started.set()
        self.loop.run_forever()

    def stop(self):
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

    def run_coroutine(self, coro, callback=None):
        """
        تشغيل coroutine وإرسال النتيجة عبر callback.
        الـ callback يُنفّذ في خيط asyncio — يجب أن يكون آمناً للـ threads.
        """
        if not self.loop:
            return None

        future = asyncio.run_coroutine_threadsafe(coro, self.loop)

        if callback:
            def _done(fut):
                try:
                    result = fut.result(timeout=300)
                    callback(result, None)
                except Exception as e:
                    callback(None, e)
            future.add_done_callback(_done)

        return future


# ------------------------------------------------------------
# النافذة الرئيسية
# ------------------------------------------------------------
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.bus = get_signal_bus()
        self.async_worker = AsyncWorker()
        self.async_worker.start()

        # ربط السجلات بالواجهة
        attach_gui_callback(self._gui_log_callback)

        self._setup_window()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_tabs()
        self._setup_status_bar()
        self._connect_signals()

        # تهيئة المنسق في الخلفية
        QTimer.singleShot(500, self._initialize_orchestrator)

        logger.info(f"تم تشغيل {APP_NAME} v{APP_VERSION}")

    # ============================================================
    # الإعداد الأولي
    # ============================================================
    def _setup_window(self):
        cfg = get_config().config.ui
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(cfg.window_width, cfg.window_height)
        self.setMinimumSize(1200, 750)

    def _setup_menu(self):
        menubar = self.menuBar()

        # ---- ملف ----
        file_menu = menubar.addMenu("ملف")

        act_new = QAction("جلسة جديدة", self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(self._new_session)
        file_menu.addAction(act_new)

        act_export = QAction("تصدير النتائج...", self)
        act_export.triggered.connect(self._export_results)
        file_menu.addAction(act_export)

        file_menu.addSeparator()

        act_exit = QAction("خروج", self)
        act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # ---- عرض ----
        view_menu = menubar.addMenu("عرض")

        act_theme_dark = QAction("ثيم داكن", self)
        act_theme_dark.triggered.connect(lambda: self._change_theme("dark"))
        view_menu.addAction(act_theme_dark)

        act_theme_light = QAction("ثيم فاتح", self)
        act_theme_light.triggered.connect(lambda: self._change_theme("light"))
        view_menu.addAction(act_theme_light)

        view_menu.addSeparator()

        act_fullscreen = QAction("ملء الشاشة", self)
        act_fullscreen.setShortcut("F11")
        act_fullscreen.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(act_fullscreen)

        # ---- أدوات ----
        tools_menu = menubar.addMenu("أدوات")

        act_check_env = QAction("فحص البيئة", self)
        act_check_env.triggered.connect(self._check_environment)
        tools_menu.addAction(act_check_env)

        act_install_rockyou = QAction("تحضير rockyou", self)
        act_install_rockyou.triggered.connect(self._prepare_rockyou)
        tools_menu.addAction(act_install_rockyou)

        tools_menu.addSeparator()

        act_cleanup = QAction("تنظيف الملفات القديمة", self)
        act_cleanup.triggered.connect(self._cleanup_files)
        tools_menu.addAction(act_cleanup)

        # ---- مساعدة ----
        help_menu = menubar.addMenu("مساعدة")

        act_about = QAction("حول البرنامج", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

        act_docs = QAction("الوثائق", self)
        act_docs.triggered.connect(self._show_docs)
        help_menu.addAction(act_docs)

    def _setup_toolbar(self):
        toolbar = QToolBar("الرئيسي")
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.act_check_all = QAction("🔍 فحص المحولات", self)
        self.act_check_all.triggered.connect(self._check_adapters)
        toolbar.addAction(self.act_check_all)

        toolbar.addSeparator()

        self.act_scan = QAction("▶ بدء المسح", self)
        self.act_scan.triggered.connect(self._toggle_scan)
        self.act_scan.setCheckable(True)
        toolbar.addAction(self.act_scan)

        toolbar.addSeparator()

        self.act_stop_all = QAction("⏹ إيقاف الكل", self)
        self.act_stop_all.triggered.connect(self._stop_all)
        toolbar.addAction(self.act_stop_all)

        toolbar.addSeparator()

        self.act_show_log = QAction("📋 عرض السجل", self)
        self.act_show_log.triggered.connect(
            lambda: self.tabs.setCurrentIndex(self._log_tab_index)
        )
        toolbar.addAction(self.act_show_log)

    def _setup_tabs(self):
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)

        self._load_tabs()

        self.main_splitter.addWidget(self.tabs)

        self.log_console = LogConsole()
        self.log_console.setMaximumHeight(250)
        self.main_splitter.addWidget(self.log_console)

        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 1)

        self.setCentralWidget(self.main_splitter)

    def _load_tabs(self):
        try:
            from app.gui.tabs.hardware_tab import HardwareTab
            self.hardware_tab = HardwareTab()
            self.tabs.addTab(self.hardware_tab, "🔧 المحولات")
        except ImportError as e:
            logger.warning(f"HardwareTab غير متوفر: {e}")
            self.hardware_tab = None

        try:
            from app.gui.tabs.scan_tab import ScanTab
            self.scan_tab = ScanTab()
            self.tabs.addTab(self.scan_tab, "📡 المسح")
        except ImportError as e:
            logger.warning(f"ScanTab غير متوفر: {e}")
            self.scan_tab = None

        try:
            from app.gui.tabs.attack_tab import AttackTab
            self.attack_tab = AttackTab()
            self.tabs.addTab(self.attack_tab, "⚔ الهجوم")
        except ImportError as e:
            logger.warning(f"AttackTab غير متوفر: {e}")
            self.attack_tab = None

        try:
            from app.gui.tabs.capture_tab import CaptureTab
            self.capture_tab = CaptureTab()
            self.tabs.addTab(self.capture_tab, "🎯 الالتقاط")
        except ImportError as e:
            logger.warning(f"CaptureTab غير متوفر: {e}")
            self.capture_tab = None

        try:
            from app.gui.tabs.rogue_tab import RogueTab
            self.rogue_tab = RogueTab()
            self.tabs.addTab(self.rogue_tab, "🎭 Evil Twin")
        except ImportError as e:
            logger.warning(f"RogueTab غير متوفر: {e}")
            self.rogue_tab = None

        try:
            from app.gui.tabs.crack_tab import CrackTab
            self.crack_tab = CrackTab()
            self.tabs.addTab(self.crack_tab, "🔓 الكسر")
        except ImportError as e:
            logger.warning(f"CrackTab غير متوفر: {e}")
            self.crack_tab = None

        try:
            from app.gui.tabs.console_tab import ConsoleTab
            self.console_tab = ConsoleTab()
            self.tabs.addTab(self.console_tab, "💻 الطرفية")
        except ImportError as e:
            logger.warning(f"ConsoleTab غير متوفر: {e}")
            self.console_tab = None

        try:
            from app.gui.tabs.settings_tab import SettingsTab
            self.settings_tab = SettingsTab()
            self.tabs.addTab(self.settings_tab, "⚙ الإعدادات")
        except ImportError as e:
            logger.warning(f"SettingsTab غير متوفر: {e}")
            self.settings_tab = None

        self._log_tab_index = 0

    def _setup_status_bar(self):
        self.status_bar = StatusBarWidget()
        self.setStatusBar(self.status_bar)

    def _connect_signals(self):
        self.bus.switch_tab.connect(self._switch_to_tab)
        self.bus.error_occurred.connect(self._show_error)
        self.bus.network_found.connect(self._update_stats)
        self.bus.handshake_captured.connect(self._update_stats)
        self.bus.crack_succeeded.connect(self._update_stats)

    # ============================================================
    # تهيئة المنسق
    # ============================================================
    def _initialize_orchestrator(self):
        """تهيئة المنسق في الخلفية."""
        self.log_console.append_log("INFO", "جارٍ تهيئة النظام...")

        from app.core import get_orchestrator

        def _on_ready(result, error):
            # ⚠ هذا callback يعمل في خيط asyncio — يجب تحويله إلى main thread
            def _do_update():
                if error:
                    self.log_console.append_log(
                        "ERROR", f"فشل التهيئة: {error}"
                    )
                    return

                report = result or {}
                self.log_console.append_log(
                    "INFO",
                    f"تم اكتشاف {report.get('adapters_found', 0)} محول، "
                    f"{report.get('adapters_ready', 0)} جاهز"
                )

                # ربط أحداث المنسق بناقل الإشارات
                orch = get_orchestrator()
                self._wire_orchestrator_events(orch)

                # تحديث الحالة
                self.status_bar.set_state("جاهز", "success")

            # استخدم QTimer.singleShot(0, ...) لنقل التنفيذ إلى main thread
            QTimer.singleShot(0, _do_update)

        coro = self._async_initialize()
        self.async_worker.run_coroutine(coro, _on_ready)

    async def _async_initialize(self):
        from app.core import get_orchestrator
        orch = get_orchestrator()
        return await orch.initialize()

    def _wire_orchestrator_events(self, orch):
        """
        ربط أحداث المنسق بإشارات الواجهة.
        يستخدم emit_threadsafe لضمان نقل الإشارات إلى main thread.
        """
        from app.core.orchestrator import EventType

        def _make_handler(signal):
            def _handler(event_type, data):
                # نقل الإشارة إلى main thread بأمان
                emit_threadsafe(signal, data)
            return _handler

        orch.subscribe(EventType.NETWORK_FOUND, _make_handler(self.bus.network_found))
        orch.subscribe(EventType.CLIENT_FOUND, _make_handler(self.bus.client_found))
        orch.subscribe(EventType.INJECTION_TESTED, _make_handler(self.bus.injection_tested))
        orch.subscribe(EventType.ATTACK_STARTED, _make_handler(self.bus.attack_started))
        orch.subscribe(EventType.ATTACK_FINISHED, _make_handler(self.bus.attack_finished))
        orch.subscribe(EventType.CAPTURE_SAVED, _make_handler(self.bus.capture_saved))
        orch.subscribe(EventType.ADAPTER_READY, _make_handler(self.bus.adapter_ready))
        orch.subscribe(EventType.ADAPTER_FAILED, _make_handler(self.bus.adapter_failed))

        # تبويب المحولات يستمع لتحديثات المحولات
        if self.hardware_tab:
            # نؤجل التحديث ليعمل في main thread
            QTimer.singleShot(0, self.hardware_tab.refresh)

    # ============================================================
    # إجراءات القائمة
    # ============================================================
    def _new_session(self):
        reply = QMessageBox.question(
            self, "جلسة جديدة",
            "هل أنت متأكد؟ سيتم مسح كل البيانات الحالية.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from app.state import get_state
            get_state().reset()
            self.bus.scan_cleared.emit()
            self.log_console.append_log("INFO", "بدأت جلسة جديدة")

    def _export_results(self):
        folder = QFileDialog.getExistingDirectory(
            self, "اختر مجلد التصدير",
            str(EVIDENCE_DIR)
        )
        if not folder:
            return
        self.log_console.append_log("INFO", f"تصدير إلى: {folder}")

    def _change_theme(self, theme: str):
        from app.gui.theme_manager import ThemeManager
        app = QApplication.instance()
        ThemeManager.apply_theme(app, theme)
        cfg = get_config()
        cfg.config.ui.theme = theme
        cfg.save()
        self.log_console.append_log("INFO", f"تم تغيير الثيم إلى: {theme}")

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _check_environment(self):
        from app.utils.shell import missing_tools
        from app.constants import REQUIRED_TOOLS, OPTIONAL_TOOLS

        missing = missing_tools(REQUIRED_TOOLS)
        missing_opt = missing_tools(OPTIONAL_TOOLS)

        msg = "الأدوات المطلوبة:\n"
        if missing:
            msg += f"  ✗ مفقودة: {', '.join(missing)}\n"
        else:
            msg += "  ✓ كل الأدوات متوفرة\n"

        msg += "\nالأدوات الاختيارية:\n"
        if missing_opt:
            msg += f"  - مفقودة: {', '.join(missing_opt)}\n"
        else:
            msg += "  ✓ كل الأدوات متوفرة\n"

        QMessageBox.information(self, "فحص البيئة", msg)

    def _prepare_rockyou(self):
        from app.core.crack import get_rockyou
        path = get_rockyou()
        if path:
            QMessageBox.information(self, "تم", f"rockyou متوفر:\n{path}")
        else:
            QMessageBox.warning(
                self, "غير متوفر",
                "rockyou غير موجود. ثبته عبر:\n"
                "sudo apt install wordlists\n"
                "sudo gunzip /usr/share/wordlists/rockyou.txt.gz"
            )

    def _cleanup_files(self):
        from app.core.capture import PCAPManager
        deleted = PCAPManager.cleanup_old_captures(days=30)
        QMessageBox.information(
            self, "تنظيف",
            f"تم حذف {deleted} ملف قديم."
        )

    def _show_about(self):
        QMessageBox.about(
            self,
            f"حول {APP_NAME}",
            f"<h2>{APP_NAME}</h2>"
            f"<p>الإصدار: {APP_VERSION}</p>"
            "<p>منصة اختبار اختراق لاسلكي متكاملة</p>"
            "<p>لمحولات Alfa (من 036H إلى AXML).</p>"
            "<hr>"
            "<p><b>تحذير:</b> هذه الأداة للاستخدام التعليمي فقط. "
            "لا تستخدمها ضد شبكات لا تملكها أو لا تملك تصريحاً باختبارها.</p>"
        )

    def _show_docs(self):
        QMessageBox.information(
            self, "الوثائق",
            "راجع مجلد docs/ في المشروع."
        )

    # ============================================================
    # شريط الأدوات
    # ============================================================
    def _check_adapters(self):
        if self.hardware_tab:
            self.tabs.setCurrentWidget(self.hardware_tab)
            self.hardware_tab.refresh()

    def _toggle_scan(self, checked: bool):
        if checked:
            self.act_scan.setText("⏹ إيقاف المسح")
            self.bus.request_scan_start.emit("")
            self.status_bar.set_state("جارٍ المسح...", "info")
        else:
            self.act_scan.setText("▶ بدء المسح")
            self.bus.request_scan_stop.emit()
            self.status_bar.set_state("متوقف", "warning")

    def _stop_all(self):
        reply = QMessageBox.question(
            self, "إيقاف الكل",
            "هل تريد إيقاف كل العمليات الجارية؟",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.log_console.append_log("WARNING", "إيقاف كل العمليات...")
        self.bus.request_stop_all.emit()

        if self.act_scan.isChecked():
            self.act_scan.setChecked(False)
            self._toggle_scan(False)

    # ============================================================
    # إشارات
    # ============================================================
    def _switch_to_tab(self, tab_name: str):
        for i in range(self.tabs.count()):
            if tab_name.lower() in self.tabs.tabText(i).lower():
                self.tabs.setCurrentIndex(i)
                return

    def _show_error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def _update_stats(self, _data=None):
        from app.state import get_state
        state = get_state()
        stats = state.get_stats()
        self.status_bar.set_stats(
            stats.get("networks_found", 0),
            stats.get("handshakes_captured", 0),
            stats.get("passwords_cracked", 0),
        )

    def _gui_log_callback(self, level: str, message: str):
        """
        يُستدعى من نظام التسجيل (قد يكون في أي thread).
        نُحوّل الإشارة إلى main thread بأمان.
        """
        try:
            emit_threadsafe(self.bus.log_message, level, message)
        except Exception:
            pass

    # ============================================================
    # الإغلاق
    # ============================================================
    def closeEvent(self, event: QCloseEvent):
        reply = QMessageBox.question(
            self, "إغلاق",
            "هل تريد إغلاق البرنامج؟ سيتم إيقاف كل العمليات.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            event.ignore()
            return

        self.log_console.append_log("INFO", "جارٍ الإغلاق...")

        # إيقاف المنسق
        try:
            from app.core import get_orchestrator
            orch = get_orchestrator()

            def _shutdown_done(_, __):
                # ننقل الإيقاف إلى main thread
                QTimer.singleShot(0, self.async_worker.stop)

            coro = orch.shutdown()
            self.async_worker.run_coroutine(coro, _shutdown_done)
        except Exception as e:
            logger.exception(f"فشل إيقاف المنسق: {e}")

        # حفظ إعدادات الواجهة
        try:
            cfg = get_config()
            cfg.config.ui.window_width = self.width()
            cfg.config.ui.window_height = self.height()
            cfg.save()
        except Exception:
            pass

        event.accept()
