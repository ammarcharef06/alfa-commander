# ============================================================
# Alfa Commander - Privileges Manager
# إدارة صلاحيات root و pkexec
# ============================================================

from __future__ import annotations

import os
import sys
import pwd
import grp
import subprocess
from typing import Optional

from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# التحقق من الصلاحيات
# ------------------------------------------------------------
def is_root() -> bool:
    """هل المستخدم الحالي root؟"""
    try:
        return os.geteuid() == 0
    except AttributeError:
        # غير مدعوم على Windows
        return False


def current_user() -> str:
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except Exception:
        return os.environ.get("USER", "unknown")


def real_user() -> str:
    """اسم المستخدم الأصلي (قبل sudo)."""
    return os.environ.get("SUDO_USER") or current_user()


def real_user_home() -> str:
    """مجلد المنزل للمستخدم الأصلي."""
    user = real_user()
    try:
        return pwd.getpwnam(user).pw_dir
    except KeyError:
        return os.path.expanduser("~")


# ------------------------------------------------------------
# المجموعات
# ------------------------------------------------------------
def user_groups(user: Optional[str] = None) -> list[str]:
    user = user or real_user()
    try:
        groups = [
            g.gr_name for g in grp.getgrall()
            if user in g.gr_mem
        ]
        primary = grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name
        if primary not in groups:
            groups.append(primary)
        return groups
    except Exception:
        return []


def is_in_group(group: str) -> bool:
    return group in user_groups()


# ------------------------------------------------------------
# رفع الصلاحيات
# ------------------------------------------------------------
def relaunch_as_root() -> None:
    """
    إعادة تشغيل البرنامج الحالي بصلاحيات root عبر sudo.
    لا تعود هذه الدالة؛ تستبدل العملية الحالية.
    """
    if is_root():
        return

    logger.info("جارٍ إعادة التشغيل بصلاحيات root...")
    script = os.path.abspath(sys.argv[0])
    args = [sys.executable, script] + sys.argv[1:]

    try:
        os.execvp("sudo", ["sudo"] + args)
    except Exception as e:
        logger.error(f"فشل رفع الصلاحيات: {e}")
        sys.exit(1)


def relaunch_with_pkexec() -> None:
    """
    إعادة تشغيل بصلاحيات مرتفعة عبر pkexec (رسومي).
    """
    if is_root():
        return

    script = os.path.abspath(sys.argv[0])
    args = [sys.executable, script] + sys.argv[1:]

    try:
        subprocess.Popen(["pkexec"] + args)
        sys.exit(0)
    except FileNotFoundError:
        logger.error("pkexec غير مثبت. استخدم sudo.")
        sys.exit(1)


# ------------------------------------------------------------
# التحقق الشامل قبل التنفيذ
# ------------------------------------------------------------
def ensure_root() -> None:
    if not is_root():
        raise PermissionError(
            "هذه العملية تتطلب صلاحيات root. "
            "أعد تشغيل البرنامج عبر sudo."
        )


def check_sudo_nopasswd() -> bool:
    """هل يستطيع المستخدم استخدام sudo دون كلمة مرور؟"""
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except Exception:
        return False


# ------------------------------------------------------------
# التحقق من قدرات النظام
# ------------------------------------------------------------
def check_capabilities() -> dict[str, bool]:
    """يرجع dict بحالة كل قدرة مهمة."""
    return {
        "is_root": is_root(),
        "has_sudo": bool(os.environ.get("SUDO_USER") or not is_root()),
        "sudo_nopasswd": check_sudo_nopasswd(),
        "in_netdev_group": is_in_group("netdev"),
        "in_sudo_group": is_in_group("sudo"),
    }


# ------------------------------------------------------------
# تنبيهات
# ------------------------------------------------------------
def warn_if_not_root():
    if not is_root():
        logger.warning(
            "البرنامج يعمل بدون صلاحيات root. "
            "بعض الوظائف (المراقبة، الحقن، تغيير الوضع) لن تعمل."
        )


def print_privileges_report() -> str:
    caps = check_capabilities()
    lines = [
        "تقرير الصلاحيات:",
        f"  المستخدم الحالي: {current_user()}",
        f"  المستخدم الأصلي: {real_user()}",
        f"  root: {'نعم' if caps['is_root'] else 'لا'}",
        f"  sudo بدون كلمة مرور: {'نعم' if caps['sudo_nopasswd'] else 'لا'}",
        f"  ضمن مجموعة netdev: {'نعم' if caps['in_netdev_group'] else 'لا'}",
        f"  ضمن مجموعة sudo: {'نعم' if caps['in_sudo_group'] else 'لا'}",
    ]
    return "\n".join(lines)
