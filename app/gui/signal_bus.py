# ============================================================
# Alfa Commander - Signal Bus
# ناقل الإشارات المركزي للواجهة
# ============================================================

from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QApplication


class SignalBus(QObject):
    """
    ناقل إشارات مركزي.
    كل التبويبات تتصل به بدلاً من التواصل المباشر.
    Singleton.
    """

    _instance: Optional["SignalBus"] = None

    def __new__(cls) -> "SignalBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ---------- المحولات ----------
    adapter_detected = pyqtSignal(dict)
    adapter_ready = pyqtSignal(dict)
    adapter_failed = pyqtSignal(dict)
    adapter_changed = pyqtSignal(str)
    adapter_released = pyqtSignal(str)

    # ---------- المسح ----------
    scan_started = pyqtSignal(dict)
    scan_stopped = pyqtSignal()
    network_found = pyqtSignal(dict)
    network_updated = pyqtSignal(dict)
    client_found = pyqtSignal(dict)
    scan_cleared = pyqtSignal()

    # ---------- الهجمات ----------
    attack_started = pyqtSignal(dict)
    attack_progress = pyqtSignal(dict)
    attack_finished = pyqtSignal(dict)
    attack_failed = pyqtSignal(dict)
    injection_tested = pyqtSignal(dict)

    # ---------- الالتقاط ----------
    capture_saved = pyqtSignal(dict)
    handshake_captured = pyqtSignal(dict)
    pmkid_captured = pyqtSignal(dict)

    # ---------- الكسر ----------
    crack_started = pyqtSignal(dict)
    crack_progress = pyqtSignal(dict)
    crack_succeeded = pyqtSignal(dict)
    crack_finished = pyqtSignal(dict)

    # ---------- Evil Twin ----------
    rogue_ap_started = pyqtSignal(dict)
    rogue_ap_stopped = pyqtSignal(dict)
    credential_captured = pyqtSignal(dict)

    # ---------- السجلات ----------
    log_message = pyqtSignal(str, str)

    # ---------- الحالة ----------
    status_update = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str, str)

    # ---------- الطلب من التبويبات ----------
    request_scan_start = pyqtSignal(str)
    request_scan_stop = pyqtSignal()
    request_attack = pyqtSignal(str, dict)
    request_stop_all = pyqtSignal()

    # ---------- التبويبات ----------
    switch_tab = pyqtSignal(str)


# ------------------------------------------------------------
# الوصول العالمي
# ------------------------------------------------------------
_bus: Optional[SignalBus] = None


def get_signal_bus() -> SignalBus:
    global _bus
    if _bus is None:
        _bus = SignalBus()
    return _bus


# ------------------------------------------------------------
# إرسال آمن من أي thread
# ------------------------------------------------------------
def emit_threadsafe(signal, *args):
    """
    إرسال إشارة Qt بأمان من أي thread.

    - إذا كنا في main thread: يُرسل مباشرة.
    - إذا كنا في thread آخر: نستخدم QTimer.singleShot(0, ...) الذي
      ينقل التنفيذ إلى main thread event loop.

    هذا ضروري لأن Qt signals المرتبطة بـ QObjects التي تعيش في main
    thread لا يمكن emit من threads أخرى مباشرة، وإلا يحدث Segfault.
    """
    try:
        app = QApplication.instance()

        # إذا لم يكن هناك QApplication (بيئة غير رسومية)، أرسل مباشرة
        if app is None:
            signal.emit(*args)
            return

        # التحقق من الـ thread الحالي
        if QThread.currentThread() == app.thread():
            # نحن في main thread — إرسال مباشر
            signal.emit(*args)
        else:
            # نحن في thread آخر — ننقل إلى main thread
            # استخدام QTimer.singleShot لنقل التنفيذ
            # ملاحظة: args تُحفظ في closure
            QTimer.singleShot(0, lambda: signal.emit(*args))

    except Exception:
        # في حالة فشل غير متوقع، نحاول emit مباشرة
        try:
            signal.emit(*args)
        except Exception:
            pass


def is_main_thread() -> bool:
    """هل نحن في main thread؟"""
    app = QApplication.instance()
    if app is None:
        return True
    return QThread.currentThread() == app.thread()
