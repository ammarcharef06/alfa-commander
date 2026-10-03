# ============================================================
# Alfa Commander - airodump-ng Wrapper
# المسح والالتقاط مع بث المخرجات
# ============================================================

from __future__ import annotations

import asyncio
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app.utils.shell import StreamingProcess, run, command_exists
from app.utils.validators import is_valid_mac, normalize_mac
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نماذج
# ------------------------------------------------------------
@dataclass
class AirodumpOptions:
    interface: str
    output_prefix: Optional[Path] = None
    channel: Optional[int] = None
    band: str = "bg"                # bg / a / abg
    bssid: Optional[str] = None
    essid: Optional[str] = None
    write_interval: int = 1
    write_format: str = "csv,pcap"
    show_ack: bool = False
    update_interval: int = 1
    encryption_filter: Optional[str] = None  # WEP / WPA / WPA2
    ignore_negative_one: bool = False         # مهم لـ RTL8187


@dataclass
class ScannedNetwork:
    bssid: str
    channel: int
    power: int
    privacy: str                    # OPN / WEP / WPA / WPA2 / WPA3
    cipher: str = ""
    auth: str = ""
    essid: str = ""
    beacons: int = 0
    data_frames: int = 0
    # التشفير الفعلي
    encryption_type: str = "OPEN"
    hidden: bool = False


@dataclass
class ScannedClient:
    mac: str
    station: str = ""               # BSSID الذي يتصل به
    power: int = 0
    packets: int = 0
    probed_essids: list[str] = field(default_factory=list)


# ------------------------------------------------------------
# الغلاف
# ------------------------------------------------------------
class Airodump:
    BINARY = "airodump-ng"

    @staticmethod
    def is_available() -> bool:
        return command_exists(Airodump.BINARY)

    # ---------- بناء الأمر ----------
    @staticmethod
    def build_command(opts: AirodumpOptions) -> list[str]:
        args = [Airodump.BINARY, opts.interface]

        if opts.channel:
            args.extend(["--channel", str(opts.channel)])
        elif opts.band:
            args.extend(["--band", opts.band])

        if opts.bssid:
            args.extend(["--bssid", normalize_mac(opts.bssid)])
        if opts.essid:
            args.extend(["--essid", opts.essid])

        if opts.output_prefix:
            args.extend(["--write", str(opts.output_prefix)])
            args.extend(["--output-format", opts.write_format])
            args.extend(["--write-interval", str(opts.write_interval)])

        if opts.encryption_filter:
            args.extend(["--encrypt", opts.encryption_filter])

        if opts.ignore_negative_one:
            args.append("--ignore-negative-one")

        if opts.show_ack:
            args.append("--showack")

        return args

    # ---------- التشغيل المتزامن (للمسح القصير) ----------
    @staticmethod
    def scan(opts: AirodumpOptions, duration: int = 30) -> tuple[list[ScannedNetwork], list[ScannedClient]]:
        """مسح قصير ويعيد النتائج."""
        args = Airodump.build_command(opts)
        logger.info(f"تشغيل المسح لمدة {duration} ثانية...")

        result = run(args, timeout=duration + 5)
        # airodump-ng لا يتوقف تلقائياً، لذا نستخدم القتل بمهلة
        # ملاحظة: run سيرفع TimeoutExpired، وهذا متوقع

        if opts.output_prefix:
            return Airodump.parse_csv(opts.output_prefix)

        return [], []

    # ---------- التشغيل غير المتزامن مع البث ----------
    @staticmethod
    async def scan_streaming(
        opts: AirodumpOptions,
        on_network: Optional[Callable[[ScannedNetwork], None]] = None,
        on_client: Optional[Callable[[ScannedClient], None]] = None,
        on_line: Optional[Callable[[str], None]] = None,
    ) -> StreamingProcess:
        """
        تشغيل المسح مع بث النتائج مباشرة.
        المستخدم مسؤول عن إيقاف العملية عبر proc.stop().
        """
        args = Airodump.build_command(opts)

        # سنقرأ ملف CSV بشكل دوري، وهذا أفضل من تحليل المخرجات
        process = StreamingProcess(
            args,
            on_stdout=on_line,
            on_stderr=on_line,
        )
        await process.start()

        # إذا كان هناك output_prefix، نبدأ مهمة قراءة دورية
        if opts.output_prefix and (on_network or on_client):
            asyncio.create_task(
                Airodump._poll_csv(
                    opts.output_prefix,
                    on_network,
                    on_client,
                )
            )

        return process

    @staticmethod
    async def _poll_csv(
        prefix: Path,
        on_network: Optional[Callable[[ScannedNetwork], None]],
        on_client: Optional[Callable[[ScannedClient], None]],
    ):
        """قراءة ملف CSV كل ثانية وإرسال التحديثات."""
        seen_networks: set[str] = set()
        seen_clients: set[str] = set()
        prefix = Path(prefix)

        while True:
            await asyncio.sleep(1)
            csv_file = prefix.parent / f"{prefix.name}-01.csv"
            if not csv_file.exists():
                continue

            try:
                networks, clients = Airodump._parse_csv_file(csv_file)
            except Exception as e:
                logger.debug(f"فشل قراءة CSV: {e}")
                continue

            for net in networks:
                if on_network and net.bssid not in seen_networks:
                    seen_networks.add(net.bssid)
                    on_network(net)

            for cli in clients:
                if on_client and cli.mac not in seen_clients:
                    seen_clients.add(cli.mac)
                    on_client(cli)

    # ---------- قراءة CSV ----------
    @staticmethod
    def parse_csv(prefix: Path) -> tuple[list[ScannedNetwork], list[ScannedClient]]:
        csv_file = Path(prefix).parent / f"{Path(prefix).name}-01.csv"
        if not csv_file.exists():
            return [], []
        return Airodump._parse_csv_file(csv_file)

    @staticmethod
    def _parse_csv_file(path: Path) -> tuple[list[ScannedNetwork], list[ScannedClient]]:
        networks: list[ScannedNetwork] = []
        clients: list[ScannedClient] = []

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # الملف مقسوم إلى قسمين: APs ثم Stations
        parts = re.split(r"\r?\n\r?\n", content, maxsplit=1)
        if not parts:
            return networks, clients

        # ---- قسم الشبكات ----
        ap_text = parts[0].strip()
        if ap_text:
            reader = csv.reader(ap_text.splitlines())
            try:
                header = next(reader)
            except StopIteration:
                header = []

            for row in reader:
                if len(row) < 14:
                    continue
                try:
                    bssid = row[0].strip()
                    if not is_valid_mac(bssid):
                        continue

                    essid = row[13].strip() if len(row) > 13 else ""
                    hidden = not essid or essid == "<length: 0>"

                    privacy = row[5].strip() if len(row) > 5 else ""
                    cipher = row[6].strip() if len(row) > 6 else ""
                    auth = row[7].strip() if len(row) > 7 else ""

                    encryption_type = Airodump._classify_encryption(privacy, auth)

                    net = ScannedNetwork(
                        bssid=bssid.upper(),
                        channel=int(row[3]) if row[3].strip().isdigit() else 0,
                        power=int(row[8]) if row[8].strip().lstrip("-").isdigit() else 0,
                        privacy=privacy,
                        cipher=cipher,
                        auth=auth,
                        essid=essid if not hidden else "",
                        beacons=int(row[9]) if row[9].strip().isdigit() else 0,
                        data_frames=int(row[10]) if row[10].strip().isdigit() else 0,
                        encryption_type=encryption_type,
                        hidden=hidden,
                    )
                    networks.append(net)
                except (ValueError, IndexError) as e:
                    logger.debug(f"خطأ في تحليل شبكة: {e}")
                    continue

        # ---- قسم العملاء ----
        if len(parts) > 1:
            sta_text = parts[1].strip()
            if sta_text:
                reader = csv.reader(sta_text.splitlines())
                try:
                    next(reader)  # تخطي العنوان
                except StopIteration:
                    pass

                for row in reader:
                    if len(row) < 6:
                        continue
                    try:
                        mac = row[0].strip()
                        if not is_valid_mac(mac):
                            continue

                        probed = [s.strip() for s in row[6:] if s.strip()] if len(row) > 6 else []

                        cli = ScannedClient(
                            mac=mac.upper(),
                            station=row[5].strip().upper() if len(row) > 5 else "",
                            power=int(row[3]) if row[3].strip().lstrip("-").isdigit() else 0,
                            packets=int(row[4]) if row[4].strip().isdigit() else 0,
                            probed_essids=probed,
                        )
                        clients.append(cli)
                    except (ValueError, IndexError):
                        continue

        return networks, clients

    # ---------- تصنيف التشفير ----------
    @staticmethod
    def _classify_encryption(privacy: str, auth: str) -> str:
        privacy = privacy.upper()
        auth = auth.upper()

        if "OPN" in privacy or privacy == "":
            return "OPEN"
        if "WEP" in privacy:
            return "WEP"
        if "WPA3" in auth or "SAE" in auth:
            return "WPA3"
        if "WPA2" in auth and "WPA3" in auth:
            return "WPA2/WPA3"
        if "WPA2" in auth or "PSK" in auth and "WPA2" in privacy:
            return "WPA2"
        if "WPA" in privacy:
            return "WPA"
        return "UNKNOWN"


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
async def start_scan(
    interface: str,
    output_prefix: Path,
    on_network: Optional[Callable[[ScannedNetwork], None]] = None,
    on_client: Optional[Callable[[ScannedClient], None]] = None,
    channel: Optional[int] = None,
    bssid: Optional[str] = None,
    ignore_negative_one: bool = True,
) -> StreamingProcess:
    opts = AirodumpOptions(
        interface=interface,
        output_prefix=output_prefix,
        channel=channel,
        bssid=bssid,
        ignore_negative_one=ignore_negative_one,
    )
    return await Airodump.scan_streaming(opts, on_network, on_client)


async def capture_handshake(
    interface: str,
    bssid: str,
    channel: int,
    output_prefix: Path,
    on_network: Optional[Callable[[ScannedNetwork], None]] = None,
    ignore_negative_one: bool = True,
) -> StreamingProcess:
    """التقاط مصافحة WPA على هدف محدد."""
    opts = AirodumpOptions(
        interface=interface,
        output_prefix=output_prefix,
        channel=channel,
        bssid=bssid,
        write_interval=1,
        ignore_negative_one=ignore_negative_one,
    )
    return await Airodump.scan_streaming(opts, on_network=on_network)


# ------------------------------------------------------------
# Module-level shortcuts
# ------------------------------------------------------------
def build_command(opts):
    return Airodump.build_command(opts)


def scan(opts, duration: int = 30):
    return Airodump.scan(opts, duration)


def scan_streaming(opts, on_network=None, on_client=None, on_line=None):
    return Airodump.scan_streaming(opts, on_network, on_client, on_line)


def parse_csv(prefix):
    return Airodump.parse_csv(prefix)

