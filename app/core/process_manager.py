# ============================================================
# Alfa Commander - Process Manager
# إدارة موحدة لكل العمليات الخلفية
# ============================================================

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from app.utils.shell import StreamingProcess
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نموذج عملية مُدارة
# ------------------------------------------------------------
class ProcessKind(str, Enum):
    SCAN = "scan"
    DEAUTH = "deauth"
    HANDSHAKE = "handshake"
    PMKID = "pmkid"
    BEACON_FLOOD = "beacon_flood"
    AUTH_FLOOD = "auth_flood"
    WPS = "wps"
    ROGUE_AP = "rogue_ap"
    CRACK = "crack"
    CUSTOM = "custom"


@dataclass
class ManagedProcess:
    id: str
    kind: ProcessKind
    process: StreamingProcess
    adapter_id: Optional[str] = None
    target_bssid: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    stopped_at: Optional[datetime] = None
    on_exit: Optional[Callable[[int], None]] = None
    metadata: dict = field(default_factory=dict)

    @property
    def running(self) -> bool:
        return self.process.running

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid


# ------------------------------------------------------------
# المدير
# ------------------------------------------------------------
class ProcessManager:
    """
    Singleton يدير كل العمليات الخلفية.
    يمنع تشغيل عمليتين متعارضتين على نفس الواجهة.
    """

    _instance: Optional["ProcessManager"] = None

    def __new__(cls) -> "ProcessManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._lock = asyncio.Lock()
        self.processes: dict[str, ManagedProcess] = {}
        self._watchers: list[asyncio.Task] = []

    # ============================================================
    # بدء عملية
    # ============================================================
    async def start(
        self,
        process: StreamingProcess,
        kind: ProcessKind,
        adapter_id: Optional[str] = None,
        target_bssid: Optional[str] = None,
        on_exit: Optional[Callable[[int], None]] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        يبدأ عملية ويسجلها. يعيد معرف العملية.
        """
        # فحص التعارض
        if adapter_id:
            conflict = self._find_conflicting_process(adapter_id, kind)
            if conflict:
                raise RuntimeError(
                    f"يوجد تعارض: العملية {conflict.id} ({conflict.kind}) "
                    f"تعمل حالياً على نفس المحول"
                )

        proc_id = str(uuid.uuid4())[:8]

        # تغليف on_exit لتنظيف السجل
        def wrapped_exit(rc: int):
            self._handle_exit(proc_id, rc)
            if on_exit:
                try:
                    on_exit(rc)
                except Exception:
                    logger.exception("خطأ في on_exit")

        process.on_exit = wrapped_exit

        managed = ManagedProcess(
            id=proc_id,
            kind=kind,
            process=process,
            adapter_id=adapter_id,
            target_bssid=target_bssid,
            on_exit=on_exit,
            metadata=metadata or {},
        )

        async with self._lock:
            self.processes[proc_id] = managed

        await process.start()
        logger.info(
            f"بدء عملية [{proc_id}] نوع={kind.value} "
            f"محول={adapter_id} هدف={target_bssid}"
        )

        return proc_id

    # ============================================================
    # إيقاف عملية
    # ============================================================
    async def stop(self, proc_id: str, timeout: float = 5.0) -> bool:
        managed = self.processes.get(proc_id)
        if not managed:
            logger.warning(f"محاولة إيقاف عملية غير موجودة: {proc_id}")
            return False

        logger.info(f"إيقاف عملية [{proc_id}] ({managed.kind.value})")
        await managed.process.stop(timeout=timeout)
        managed.stopped_at = datetime.now()
        return True

    async def stop_all(self, timeout: float = 5.0):
        """إيقاف كل العمليات."""
        logger.info(f"إيقاف {len(self.processes)} عملية...")
        tasks = [self.stop(pid, timeout) for pid in list(self.processes.keys())]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_by_kind(self, kind: ProcessKind, timeout: float = 5.0):
        targets = [pid for pid, m in self.processes.items() if m.kind == kind]
        for pid in targets:
            await self.stop(pid, timeout)

    async def stop_by_adapter(self, adapter_id: str, timeout: float = 5.0):
        targets = [
            pid for pid, m in self.processes.items()
            if m.adapter_id == adapter_id
        ]
        for pid in targets:
            await self.stop(pid, timeout)

    async def stop_by_target(self, bssid: str, timeout: float = 5.0):
        targets = [
            pid for pid, m in self.processes.items()
            if m.target_bssid and m.target_bssid.upper() == bssid.upper()
        ]
        for pid in targets:
            await self.stop(pid, timeout)

    # ============================================================
    # الاستعلام
    # ============================================================
    def get(self, proc_id: str) -> Optional[ManagedProcess]:
        return self.processes.get(proc_id)

    def list_all(self) -> list[ManagedProcess]:
        return list(self.processes.values())

    def list_running(self) -> list[ManagedProcess]:
        return [m for m in self.processes.values() if m.running]

    def list_by_kind(self, kind: ProcessKind) -> list[ManagedProcess]:
        return [m for m in self.processes.values() if m.kind == kind]

    def list_by_adapter(self, adapter_id: str) -> list[ManagedProcess]:
        return [m for m in self.processes.values() if m.adapter_id == adapter_id]

    def is_adapter_busy(self, adapter_id: str) -> bool:
        return any(m.running for m in self.list_by_adapter(adapter_id))

    def is_target_busy(self, bssid: str) -> bool:
        bssid = bssid.upper()
        return any(
            m.running and m.target_bssid and m.target_bssid.upper() == bssid
            for m in self.processes.values()
        )

    # ============================================================
    # أدوات داخلية
    # ============================================================
    def _find_conflicting_process(self, adapter_id: str, kind: ProcessKind) -> Optional[ManagedProcess]:
        """
        فحص التعارض: بعض العمليات لا يمكن تشغيلها معاً على نفس المحول.
        """
        # عمليات حصرية (تستحوذ على المحول)
        exclusive = {
            ProcessKind.SCAN,
            ProcessKind.HANDSHAKE,
            ProcessKind.PMKID,
            ProcessKind.ROGUE_AP,
        }

        existing = [
            m for m in self.processes.values()
            if m.adapter_id == adapter_id and m.running
        ]

        if not existing:
            return None

        # إذا كانت العملية الجديدة حصرية، أو كانت هناك عملية حصرية
        if kind in exclusive:
            for m in existing:
                if m.kind in exclusive:
                    return m
        # عمليات الحقن يمكن أن تتشارك مع بعضها (deauth مع beacon_flood مثلاً)
        return None

    def _handle_exit(self, proc_id: str, rc: int):
        managed = self.processes.get(proc_id)
        if managed:
            managed.stopped_at = datetime.now()
            logger.info(f"انتهت العملية [{proc_id}] برمز {rc}")

    def cleanup_finished(self):
        """حذف العمليات المنتهية من السجل."""
        finished = [pid for pid, m in self.processes.items() if not m.running]
        for pid in finished:
            del self.processes[pid]
        if finished:
            logger.debug(f"تم حذف {len(finished)} عملية منتهية من السجل")


# ------------------------------------------------------------
# الوصول العالمي
# ------------------------------------------------------------
_manager: Optional[ProcessManager] = None


def get_process_manager() -> ProcessManager:
    global _manager
    if _manager is None:
        _manager = ProcessManager()
    return _manager
