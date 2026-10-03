#!/usr/bin/env python3
# ============================================================
# Alfa Commander - Main Entry Point
# نقطة الدخول الرئيسية
# ============================================================

from __future__ import annotations

import os
import sys
import signal
import argparse

# إضافة جذر المشروع إلى sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="alfa-commander",
        description="منصة اختبار اختراق لاسلكي متكاملة لمحولات Alfa",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="تفعيل وضع التصحيح (سجلات مفصلة)",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="تشغيل بدون واجهة رسومية (وضع الطرفية فقط)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="فحص البيئة والتبعيات والخروج",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="طباعة الإصدار والخروج",
    )
    return parser.parse_args()


def print_banner():
    from app.constants import APP_NAME, APP_VERSION
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   █████╗ ██╗     ███████╗ █████╗                            ║
║  ██╔══██╗██║     ██╔════╝██╔══██╗                           ║
║  ███████║██║     █████╗  ███████║                           ║
║  ██╔══██║██║     ██╔══╝  ██╔══██║                           ║
║  ██║  ██║███████╗██║     ██║  ██║                           ║
║  ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝                           ║
║                                                              ║
║  {APP_NAME} v{APP_VERSION}                                    ║
║  منصة اختبار اختراق لاسلكي متكاملة لمحولات Alfa             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def check_root() -> bool:
    """التحقق من أن المستخدم root."""
    return os.geteuid() == 0


def check_environment() -> bool:
    """فحص سريع للبيئة."""
    from app.utils.shell import command_exists
    from app.constants import REQUIRED_TOOLS
    from app.logger import info, warning, error

    info("جارٍ فحص البيئة والتبعيات...")

    missing = []
    for tool in REQUIRED_TOOLS:
        if not command_exists(tool):
            missing.append(tool)

    if missing:
        warning(f"أدوات مفقودة: {', '.join(missing)}")
        warning("يمكنك تثبيتها عبر: sudo apt install <tool>")
        return False

    info("جميع الأدوات الأساسية متوفرة.")
    return True


def signal_handler(signum, frame):
    from app.logger import info
    info(f"تم استقبال الإشارة {signum}، جارٍ الإغلاق...")
    sys.exit(0)


def main() -> int:
    args = parse_args()

    # الإصدار
    if args.version:
        from app.constants import APP_NAME, APP_VERSION
        print(f"{APP_NAME} v{APP_VERSION}")
        return 0

    # البانر
    print_banner()

    # التحقق من الصلاحيات
    if not check_root():
        print("[!] هذا البرنامج يحتاج صلاحيات root.")
        print("    شغّله عبر: sudo python3 main.py")
        return 1

    # إعداد التسجيل
    from app.logger import setup_logger, info, warning, error
    setup_logger()

    if args.debug:
        import logging
        from app.logger import get_logger
        get_logger().setLevel(logging.DEBUG)
        info("تم تفعيل وضع التصحيح.")

    # تحميل الإعدادات
    from app.config import get_config
    config = get_config()
    info("تم تحميل الإعدادات.")

    # التحقق من البيئة
    if args.check:
        ok = check_environment()
        return 0 if ok else 1

    if config.config.general.auto_check_dependencies:
        check_environment()

    # إشارات النظام
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # تشغيل الوضع المناسب
    if args.no_gui:
        info("وضع الطرفية غير مدعوم بعد. استخدم الواجهة الرسومية.")
        return 0

    try:
        # الواجهة الرسومية (ستُبنى في المرحلة 7)
        try:
            from app.gui.main_window import MainWindow
            from PyQt6.QtWidgets import QApplication

            info("جارٍ تشغيل الواجهة الرسومية...")
            app = QApplication(sys.argv)
            app.setApplicationName("Alfa Commander")
            app.setApplicationVersion("1.0.0")

            window = MainWindow()
            window.show()

            exit_code = app.exec()
            info("تم إغلاق البرنامج بشكل طبيعي.")
            return exit_code

        except ImportError as e:
            error(f"لم يتم العثور على الواجهة الرسومية: {e}")
            warning("المرحلة 7 من المشروع لم تكتمل بعد.")
            warning("يمكنك تشغيل --check للتحقق من البيئة.")
            return 1

    except KeyboardInterrupt:
        info("تم الإيقاف بواسطة المستخدم.")
        return 130
    except Exception as e:
        from app.logger import exception
        exception(f"خطأ غير متوقع: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
