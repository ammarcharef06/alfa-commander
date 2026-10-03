# ============================================================
# Alfa Commander - Channel Scheduler
# إدارة ذكية للقفز بين القنوات
# ============================================================

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.constants import BAND_2GHZ_CHANNELS, BAND_5GHZ_CHANNELS, BAND_6GHZ_CHANNELS
from app.core.tools import iw
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# استراتيجيات القفز
# ------------------------------------------------------------
class HopStrategy:
    """استراتيجيات مختلفة للقفز بين القنوات."""

    @staticmethod
    def fast_2ghz() -> list[int]:
        """قفز سريع على 2.4GHz."""
        return list(BAND_2GHZ_CHANNELS)

    @staticmethod
    def full_2ghz_5ghz() -> list[int]:
        """قفز شامل على 2.4 و 5GHz."""
        return list(BAND_2GHZ_CHANNELS) + list(BAND_5GHZ_CHANNELS)

    @staticmethod
    def popular_2ghz() -> list[int]:
        """القنوات الأكثر استخداماً على 2.4GHz."""
        return [1, 6, 11, 3, 9, 13]

    @staticmethod
    def full_all_bands() -> list[int]:
        """كل النطاقات المدعومة."""
        return (
            list(BAND_2GHZ_CHANNELS) +
            list(BAND_5GHZ_CHANNELS) +
            list(BAND_6GHZ_CHANNELS)
        )

    @staticmethod
    def for_adapter(adapter) -> list[int]:
        """يختار استراتيجية بناءً على قدرات المحول."""
        bands = adapter.DEFAULT_BANDS
        channels = []
        if "2.4" in bands:
            channels.extend(BAND_2GHZ_CHANNELS)
        if "5" in bands:
            channels.extend(BAND_5GHZ_CHANNELS)
        if "6" in bands:
            channels.extend(BAND_6GHZ_CHANNELS)
        return channels or list(BAND_2GHZ_CHANNELS)


# ------------------------------------------------------------
# المجدول
# ------------------------------------------------------------
@dataclass
class ChannelScheduler:
    """
    يتحكم بالقفز بين القنوات.
    عند مهاجمة هدف محدد، يجب استخدام pin() لتثبيت القناة.
    """
    interface: str
    channels: list[int] = field(default_factory=list)
    dwell_time: float = 0.3               # وقت البقاء على كل قناة
    current_index: int = 0
    current_channel: Optional[int] = None
    _task: Optional[asyncio.Task] = None
    _pinned: bool = False
    _pinned_channel: Optional[int] = None
    _running: bool = False
    _pause_event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self):
        if not self.channels:
            self.channels = HopStrategy.fast_2ghz()

    # ---------- بدء/إيقاف ----------
    async def start(self):
        if self._running:
            return
        self._running = True
        self._pause_event.set()
        self._task = asyncio.create_task(self._hop_loop())
        logger.info(f"بدء القفز بين {len(self.channels)} قناة على {self.interface}")

    async def stop(self):
        if not self._running:
            return
        self._running = False
        self._pause_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"إيقاف القفز على {self.interface}")

    # ---------- تثبيت القناة ----------
    async def pin(self, channel: int):
        """
        تثبيت القناة (للهجوم). يوقف القفز مؤقتاً.
        """
        self._pinned = True
        self._pinned_channel = channel
        self._pause_event.clear()
        # ننتظر دورة القفز الحالية لتنتهي
        await asyncio.sleep(self.dwell_time + 0.1)
        self._set_channel(channel)
        logger.info(f"تم تثبيت القناة {channel} على {self.interface}")

    async def unpin(self):
        """رفع التثبيت والعودة للقفز."""
        self._pinned = False
        self._pinned_channel = None
        self._pause_event.set()
        logger.info(f"تم رفع التثبيت على {self.interface}")

    # ---------- تغيير الاستراتيجية ----------
    def set_channels(self, channels: list[int]):
        self.channels = list(channels)
        self.current_index = 0
        logger.info(f"تم تحديث قائمة القنوات ({len(channels)})")

    def set_dwell_time(self, seconds: float):
        self.dwell_time = max(0.1, seconds)

    # ---------- حلقة القفز ----------
    async def _hop_loop(self):
        while self._running:
            try:
                await self._pause_event.wait()

                if not self._running:
                    break

                if not self.channels:
                    await asyncio.sleep(1)
                    continue

                channel = self.channels[self.current_index]
                self._set_channel(channel)
                self.current_index = (self.current_index + 1) % len(self.channels)

                await asyncio.sleep(self.dwell_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"خطأ في القفز: {e}")
                await asyncio.sleep(1)

    def _set_channel(self, channel: int):
        try:
            result = iw.IW.set_channel(self.interface, channel)
            if result.ok:
                self.current_channel = channel
            else:
                logger.debug(f"فشل تغيير القناة إلى {channel}")
        except Exception as e:
            logger.debug(f"خطأ في تغيير القناة: {e}")

    # ---------- معلومات ----------
    @property
    def is_pinned(self) -> bool:
        return self._pinned

    @property
    def is_running(self) -> bool:
        return self._running

    def current(self) -> Optional[int]:
        if self._pinned:
            return self._pinned_channel
        return self.current_channel


# ------------------------------------------------------------
# مدير المجدولات (لكل واجهة)
# ------------------------------------------------------------
class ChannelSchedulerManager:
    _instance: Optional["ChannelSchedulerManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._schedulers: dict[str, ChannelScheduler] = {}
        self._lock = asyncio.Lock()

    async def get_scheduler(
        self,
        interface: str,
        channels: Optional[list[int]] = None,
        dwell: float = 0.3,
    ) -> ChannelScheduler:
        async with self._lock:
            if interface not in self._schedulers:
                self._schedulers[interface] = ChannelScheduler(
                    interface=interface,
                    channels=channels or HopStrategy.fast_2ghz(),
                    dwell_time=dwell,
                )
            return self._schedulers[interface]

    async def stop_all(self):
        for scheduler in self._schedulers.values():
            await scheduler.stop()
        self._schedulers.clear()

    def list_active(self) -> list[str]:
        return [iface for iface, s in self._schedulers.items() if s.is_running]


# ------------------------------------------------------------
# الوصول العالمي
# ------------------------------------------------------------
_manager: Optional[ChannelSchedulerManager] = None


def get_channel_manager() -> ChannelSchedulerManager:
    global _manager
    if _manager is None:
        _manager = ChannelSchedulerManager()
    return _manager


async def start_hopping(
    interface: str,
    channels: Optional[list[int]] = None,
    dwell: float = 0.3,
) -> ChannelScheduler:
    mgr = get_channel_manager()
    scheduler = await mgr.get_scheduler(interface, channels, dwell)
    await scheduler.start()
    return scheduler


async def pin_channel(interface: str, channel: int):
    mgr = get_channel_manager()
    scheduler = await mgr.get_scheduler(interface)
    await scheduler.pin(channel)


async def unpin_channel(interface: str):
    mgr = get_channel_manager()
    scheduler = await mgr.get_scheduler(interface)
    await scheduler.unpin()
