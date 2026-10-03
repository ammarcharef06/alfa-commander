# ============================================================
# Alfa Commander - Wordlist Manager
# إدارة قوائم الكلمات والقواعد
# ============================================================

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.utils.shell import run
from app.logger import get_logger

logger = get_logger()


@dataclass
class WordlistInfo:
    path: Path
    name: str
    size_bytes: int = 0
    lines: int = 0
    description: str = ""
    category: str = ""

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


# ------------------------------------------------------------
# مسارات شائعة
# ------------------------------------------------------------
COMMON_PATHS = [
    Path("/usr/share/wordlists"),
    Path("/usr/share/seclists"),
    Path.home() / "wordlists",
    Path.cwd() / "wordlists",
]


class WordlistManager:
    """
    يكتشف ويدير قوائم الكلمات على النظام.
    """

    @staticmethod
    def list_available() -> list[WordlistInfo]:
        """قائمة بكل قوائم الكلمات المتوفرة."""
        wordlists = []
        seen = set()

        for base_dir in COMMON_PATHS:
            if not base_dir.exists():
                continue

            for path in base_dir.rglob("*.txt"):
                if path in seen:
                    continue
                seen.add(path)

                # تجاهل الملفات الصغيرة جداً
                try:
                    size = path.stat().st_size
                    if size < 1024:  # أقل من 1KB
                        continue
                except Exception:
                    continue

                info = WordlistInfo(
                    path=path,
                    name=path.name,
                    size_bytes=size,
                    description=WordlistManager._guess_description(path),
                    category=WordlistManager._guess_category(path),
                )
                wordlists.append(info)

            # ملفات .gz
            for path in base_dir.rglob("*.txt.gz"):
                if path in seen:
                    continue
                seen.add(path)
                try:
                    size = path.stat().st_size
                except Exception:
                    continue
                info = WordlistInfo(
                    path=path,
                    name=path.name,
                    size_bytes=size,
                    description="ملف مضغوط (يحتاج gunzip)",
                    category="compressed",
                )
                wordlists.append(info)

        # ترتيب حسب الحجم
        wordlists.sort(key=lambda w: w.size_bytes, reverse=True)
        return wordlists

    @staticmethod
    def _guess_description(path: Path) -> str:
        name = path.name.lower()
        if "rockyou" in name:
            return "rockyou - قائمة اختراق شائعة"
        if "top" in name and "1000" in name:
            return "أشهر 1000 كلمة مرور"
        if "top" in name and "10000" in name:
            return "أشهر 10000 كلمة مرور"
        if "wpa" in name:
            return "قائمة مخصصة لـ WPA"
        if "wifi" in name:
            return "قائمة WiFi"
        if "dark" in name:
            return "Dark Web - قائمة ضخمة"
        return ""

    @staticmethod
    def _guess_category(path: Path) -> str:
        parts = path.parts
        if "seclists" in parts:
            for p in parts:
                if p.startswith("Passwords"):
                    return "seclists/passwords"
                if p.startswith("Usernames"):
                    return "seclists/usernames"
            return "seclists"
        if "wordlists" in parts:
            return "wordlists"
        return "other"

    @staticmethod
    def count_lines(wordlist: Path) -> int:
        """عد أسطر قائمة الكلمات."""
        if not wordlist.exists():
            return 0

        # إذا كانت مضغوطة
        if wordlist.suffix == ".gz":
            result = run(["zcat", str(wordlist)], timeout=60, capture=False)
            # لن نستخدم هذا، نستخدم wc
            result = run(f"zcat {wordlist} | wc -l", timeout=120)
            if result.ok:
                try:
                    return int(result.stdout.strip())
                except ValueError:
                    return 0

        result = run(["wc", "-l", str(wordlist)], timeout=60)
        if result.ok:
            try:
                return int(result.stdout.split()[0])
            except (ValueError, IndexError):
                return 0
        return 0

    @staticmethod
    def get_default_wordlists() -> list[WordlistInfo]:
        """قوائم كلمات موصى بها بشكل افتراضي."""
        defaults = []
        all_lists = WordlistManager.list_available()

        # قائمة rockyou أولاً
        for w in all_lists:
            if "rockyou" in w.name.lower() and not w.name.endswith(".gz"):
                defaults.append(w)
                break

        # ثم top 10000
        for w in all_lists:
            if "10000" in w.name and w not in defaults:
                defaults.append(w)
                break

        # ثم أول 5 من القوائم الكبيرة
        for w in all_lists[:5]:
            if w not in defaults:
                defaults.append(w)

        return defaults

    @staticmethod
    def ensure_rockyou() -> Optional[Path]:
        """التأكد من وجود rockyou، وإلا نحاول فك الضغط."""
        rockyou_txt = Path("/usr/share/wordlists/rockyou.txt")
        rockyou_gz = Path("/usr/share/wordlists/rockyou.txt.gz")

        if rockyou_txt.exists():
            return rockyou_txt

        if rockyou_gz.exists():
            logger.info("فك ضغط rockyou.txt.gz...")
            result = run(["gunzip", "-k", str(rockyou_gz)], timeout=120)
            if result.ok and rockyou_txt.exists():
                return rockyou_txt

        return None

    @staticmethod
    def search(keyword: str) -> list[WordlistInfo]:
        """البحث في قوائم الكلمات بالاسم."""
        keyword = keyword.lower()
        return [
            w for w in WordlistManager.list_available()
            if keyword in w.name.lower() or keyword in w.description.lower()
        ]


# ------------------------------------------------------------
# قوائم قواعد hashcat
# ------------------------------------------------------------
@dataclass
class RuleInfo:
    path: Path
    name: str
    description: str = ""


class RuleManager:
    """إدارة قواعد hashcat."""

    COMMON_DIRS = [
        Path("/usr/share/hashcat/rules"),
        Path("/usr/share/doc/hashcat/rules"),
        Path("/opt/hashcat/rules"),
    ]

    @staticmethod
    def list_available() -> list[RuleInfo]:
        rules = []
        for base in RuleManager.COMMON_DIRS:
            if not base.exists():
                continue
            for path in base.glob("*.rule"):
                rules.append(RuleInfo(
                    path=path,
                    name=path.name,
                    description=RuleManager._describe(path.name),
                ))
        return rules

    @staticmethod
    def _describe(name: str) -> str:
        name_lower = name.lower()
        if "best64" in name_lower:
            return "best64 - أفضل 64 قاعدة"
        if "rockyou" in name_lower:
            return "rockyou rules"
        if "dive" in name_lower:
            return "dive - قواعد متقدمة"
        if "toggles" in name_lower:
            return "toggles - تبديل حالة الأحرف"
        if "leetspeak" in name_lower:
            return "leetspeak - تحويل الأحرف لأرقام"
        return ""


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
def list_wordlists() -> list[WordlistInfo]:
    return WordlistManager.list_available()


def list_rules() -> list[RuleInfo]:
    return RuleManager.list_available()


def get_rockyou() -> Optional[Path]:
    return WordlistManager.ensure_rockyou()
