# ============================================================
# Alfa Commander - Injection Validator
# فحص الحقن وتكييف الهجمات
# ============================================================

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.constants import INJECTION_THRESHOLDS
from app.core.adapters.base_adapter import BaseAlfaAdapter
from app.core.tools import aireplay
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نتيجة الفحص
# ------------------------------------------------------------
@dataclass
class InjectionAssessment:
    interface: str
    ratio: int
    quality: str                          # excellent / good / weak / broken
    tested_at: datetime = field(default_factory=datetime.now)
    recommended_deauth_count: int = 0
    recommended_deauth_interval: int = 1
    recommended_attack: str = ""          # "handshake" / "pmkid" / "none"
    warnings: list[str] = field(default_factory=list)
    raw_output: str = ""

    def is_usable(self) -> bool:
        return self.ratio >= INJECTION_THRESHOLDS["weak"]

    def is_reliable(self) -> bool:
        return self.ratio >= INJECTION_THRESHOLDS["good"]

    def is_fresh(self, max_age_seconds: int = 300) -> bool:
        return (datetime.now() - self.tested_at) < timedelta(seconds=max_age_seconds)


# ------------------------------------------------------------
# المدقق
# ------------------------------------------------------------
class InjectionValidator:
    """
    يدير اختبار الحقن لكل محول، ويخزن النتائج مؤقتاً.
    """

    _instance: Optional["InjectionValidator"] = None

    def __new__(cls) -> "InjectionValidator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._cache: dict[str, InjectionAssessment] = {}
        self._lock = asyncio.Lock()

    # ============================================================
    # الفحص
    # ============================================================
    async def test(
        self,
        adapter: BaseAlfaAdapter,
        force: bool = False,
    ) -> InjectionAssessment:
        """
        اختبار الحقن على محول.
        يستخدم الذاكرة المؤقتة إذا كانت النتيجة حديثة (< 5 دقائق).
        """
        iface = adapter.get_active_interface()

        async with self._lock:
            if not force:
                cached = self._cache.get(iface)
                if cached and cached.is_fresh():
                    logger.debug(f"استخدام نتيجة حقن مخزّنة لـ {iface}: {cached.ratio}%")
                    return cached

            logger.info(f"اختبار الحقن على {iface}...")

            # تشغيل في executor لأن aireplay متزامن
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: aireplay.Aireplay.test_injection(iface, timeout=30),
            )

            assessment = self._build_assessment(adapter, iface, result)
            self._cache[iface] = assessment

            logger.info(
                f"نتيجة الحقن على {iface}: {assessment.ratio}% ({assessment.quality})"
            )

            return assessment

    # ============================================================
    # بناء التقييم
    # ============================================================
    def _build_assessment(
        self,
        adapter: BaseAlfaAdapter,
        iface: str,
        result: aireplay.InjectionTestResult,
    ) -> InjectionAssessment:
        ratio = result.ratio
        quality = result.quality

        # تصنيف الجودة
        if ratio >= INJECTION_THRESHOLDS["excellent"]:
            quality = "excellent"
        elif ratio >= INJECTION_THRESHOLDS["good"]:
            quality = "good"
        elif ratio >= INJECTION_THRESHOLDS["weak"]:
            quality = "weak"
        else:
            quality = "broken"

        # التوصيات
        deauth_count, deauth_interval = self._recommend_deauth(ratio, adapter)
        attack = self._recommend_attack(ratio, adapter)

        warnings = []
        if quality == "broken":
            warnings.append(
                f"الحقن لا يعمل على {adapter.MODEL}. "
                "تحقق من: التعريف، القناة، القرب من الهدف."
            )
        elif quality == "weak":
            warnings.append(
                f"الحقن ضعيف ({ratio}%). "
                "قد تحتاج هجمات متكررة أو الاقتراب من الهدف."
            )

        # تحذيرات خاصة بالشريحة
        if adapter.CHIPSET == "RTL8187L" and ratio < 50:
            warnings.append(
                "RTL8187L معروف بضعف الحقن. "
                "استخدم أعداد Deauth منخفضة."
            )

        return InjectionAssessment(
            interface=iface,
            ratio=ratio,
            quality=quality,
            recommended_deauth_count=deauth_count,
            recommended_deauth_interval=deauth_interval,
            recommended_attack=attack,
            warnings=warnings,
            raw_output=result.output,
        )

    def _recommend_deauth(self, ratio: int, adapter: BaseAlfaAdapter) -> tuple[int, int]:
        """
        يوصي بعدد Deauth وفاصل زمني بناءً على نسبة الحقن والشريحة.
        """
        chipset = adapter.CHIPSET

        # RTL8187L: يحتاج أعداداً منخفضة وفواصل طويلة
        if chipset == "RTL8187L":
            if ratio >= 50:
                return 5, 1
            if ratio >= 30:
                return 8, 2
            if ratio >= 15:
                return 12, 3
            return 0, 5

        # MT7921AUN: حقن ممتاز
        if chipset == "MT7921AUN":
            if ratio >= 50:
                return 3, 1
            if ratio >= 30:
                return 5, 1
            return 10, 2

        # الافتراضي لبقية الشرائح
        if ratio >= 70:
            return 3, 1
        if ratio >= 50:
            return 5, 1
        if ratio >= 30:
            return 8, 2
        if ratio >= 15:
            return 15, 3
        return 0, 5

    def _recommend_attack(self, ratio: int, adapter: BaseAlfaAdapter) -> str:
        """
        يوصي بنوع الهجوم الأمثل بناءً على المحول ونسبة الحقن.
        """
        # PMKID لا يحتاج Deauth في كثير من الحالات
        if ratio >= INJECTION_THRESHOLDS["weak"]:
            return "pmkid"
        if ratio >= INJECTION_THRESHOLDS["good"]:
            return "handshake"
        if ratio >= INJECTION_THRESHOLDS["weak"]:
            return "passive"
        return "none"

    # ============================================================
    # إدارة الذاكرة المؤقتة
    # ============================================================
    def get_cached(self, interface: str) -> Optional[InjectionAssessment]:
        return self._cache.get(interface)

    def invalidate(self, interface: Optional[str] = None):
        if interface:
            self._cache.pop(interface, None)
        else:
            self._cache.clear()

    def all_assessments(self) -> dict[str, InjectionAssessment]:
        return dict(self._cache)


# ------------------------------------------------------------
# الوصول العالمي
# ------------------------------------------------------------
_validator: Optional[InjectionValidator] = None


def get_injection_validator() -> InjectionValidator:
    global _validator
    if _validator is None:
        _validator = InjectionValidator()
    return _validator


async def validate_adapter(adapter: BaseAlfaAdapter, force: bool = False) -> InjectionAssessment:
    return await get_injection_validator().test(adapter, force=force)
