# ============================================================
# Alfa Commander - CSV Parser
# تحليل ملفات CSV الخاصة بـ airodump-ng
# ============================================================

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.tools.airodump import ScannedNetwork, ScannedClient
from app.utils.validators import is_valid_mac
from app.utils.oui_lookup import lookup as oui_lookup
from app.logger import get_logger

logger = get_logger()


@dataclass
class ParsedScanResult:
    networks: list[ScannedNetwork] = field(default_factory=list)
    clients: list[ScannedClient] = field(default_factory=list)
    parsed_at: datetime = field(default_factory=datetime.now)
    total_networks: int = 0
    total_clients: int = 0
    encrypted_networks: int = 0
    hidden_networks: int = 0


class CSVParser:
    """
    يحلل ملفات CSV الناتجة عن airodump-ng.
    يدعم كلا القسمين: APs و Stations.
    """

    @staticmethod
    def parse(csv_file: Path) -> ParsedScanResult:
        result = ParsedScanResult()

        if not csv_file.exists():
            logger.warning(f"ملف CSV غير موجود: {csv_file}")
            return result

        try:
            with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            logger.exception(f"فشل قراءة CSV: {e}")
            return result

        parts = re.split(r"\r?\n\r?\n", content, maxsplit=1)

        # قسم الشبكات
        if parts:
            result.networks = CSVParser._parse_networks_section(parts[0])

        # قسم العملاء
        if len(parts) > 1:
            result.clients = CSVParser._parse_clients_section(parts[1])

        result.total_networks = len(result.networks)
        result.total_clients = len(result.clients)
        result.encrypted_networks = sum(
            1 for n in result.networks if n.encryption_type not in ("OPEN", "UNKNOWN")
        )
        result.hidden_networks = sum(1 for n in result.networks if n.hidden)

        return result

    @staticmethod
    def _parse_networks_section(text: str) -> list[ScannedNetwork]:
        networks = []
        text = text.strip()
        if not text:
            return networks

        reader = csv.reader(text.splitlines())
        try:
            next(reader)  # header
        except StopIteration:
            return networks

        for row in reader:
            if len(row) < 14:
                continue
            try:
                bssid = row[0].strip()
                if not is_valid_mac(bssid):
                    continue

                essid = row[13].strip() if len(row) > 13 else ""
                hidden = not essid or essid == "<length: 0>" or essid == ""

                privacy = row[5].strip() if len(row) > 5 else ""
                cipher = row[6].strip() if len(row) > 6 else ""
                auth = row[7].strip() if len(row) > 7 else ""

                encryption_type = CSVParser._classify_encryption(privacy, auth)

                net = ScannedNetwork(
                    bssid=bssid.upper(),
                    channel=CSVParser._to_int(row[3], 0),
                    power=CSVParser._to_int(row[8], -100),
                    privacy=privacy,
                    cipher=cipher,
                    auth=auth,
                    essid=essid if not hidden else "",
                    beacons=CSVParser._to_int(row[9], 0),
                    data_frames=CSVParser._to_int(row[10], 0),
                    encryption_type=encryption_type,
                    hidden=hidden,
                )
                networks.append(net)
            except (ValueError, IndexError) as e:
                logger.debug(f"خطأ في تحليل صف: {e}")
                continue

        return networks

    @staticmethod
    def _parse_clients_section(text: str) -> list[ScannedClient]:
        clients = []
        text = text.strip()
        if not text:
            return clients

        reader = csv.reader(text.splitlines())
        try:
            next(reader)  # header
        except StopIteration:
            return clients

        for row in reader:
            if len(row) < 6:
                continue
            try:
                mac = row[0].strip()
                if not is_valid_mac(mac):
                    continue

                probed = []
                if len(row) > 6:
                    probed = [s.strip() for s in row[6:] if s.strip()]

                cli = ScannedClient(
                    mac=mac.upper(),
                    station=row[5].strip().upper() if len(row) > 5 else "",
                    power=CSVParser._to_int(row[3], -100),
                    packets=CSVParser._to_int(row[4], 0),
                    probed_essids=probed,
                )
                clients.append(cli)
            except (ValueError, IndexError):
                continue

        return clients

    @staticmethod
    def _to_int(value: str, default: int = 0) -> int:
        value = value.strip()
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            try:
                return int(float(value))
            except ValueError:
                return default

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
        if "WPA2" in auth or "WPA2" in privacy:
            return "WPA2"
        if "WPA" in privacy:
            return "WPA"
        return "UNKNOWN"


# ------------------------------------------------------------
# دالة مختصرة
# ------------------------------------------------------------
def parse_csv(csv_file: Path) -> ParsedScanResult:
    return CSVParser.parse(csv_file)


def parse_networks_only(csv_file: Path) -> list[ScannedNetwork]:
    return CSVParser.parse(csv_file).networks


def parse_clients_only(csv_file: Path) -> list[ScannedClient]:
    return CSVParser.parse(csv_file).clients
