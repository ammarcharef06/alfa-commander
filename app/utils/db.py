# ============================================================
# Alfa Commander - Database Layer
# SQLite غير متزامن
# ============================================================

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from app.constants import DB_PATH
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# مخطط قاعدة البيانات
# ------------------------------------------------------------
SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS adapters (
    id TEXT PRIMARY KEY,
    model TEXT,
    chipset TEXT,
    interface TEXT,
    monitor_interface TEXT,
    bands TEXT,
    driver TEXT,
    driver_type TEXT,
    max_standard TEXT,
    mac_address TEXT,
    usb_id TEXT,
    injection_ratio INTEGER,
    first_seen TEXT,
    last_seen TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS networks (
    bssid TEXT PRIMARY KEY,
    essid TEXT,
    channel INTEGER,
    band TEXT,
    encryption TEXT,
    cipher TEXT,
    auth TEXT,
    power INTEGER,
    wps INTEGER,
    wps_version TEXT,
    hidden INTEGER,
    vendor TEXT,
    country TEXT,
    first_seen TEXT,
    last_seen TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bssid TEXT,
    client_mac TEXT,
    power INTEGER,
    first_seen TEXT,
    last_seen TEXT,
    vendor TEXT,
    UNIQUE(bssid, client_mac)
);

CREATE TABLE IF NOT EXISTS attacks (
    id TEXT PRIMARY KEY,
    type TEXT,
    target_bssid TEXT,
    target_essid TEXT,
    adapter_id TEXT,
    state TEXT,
    started_at TEXT,
    finished_at TEXT,
    progress INTEGER,
    result TEXT,
    error TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bssid TEXT,
    type TEXT,
    file_path TEXT,
    hashcat_path TEXT,
    captured_at TEXT,
    cracked INTEGER DEFAULT 0,
    password TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ssid TEXT,
    username TEXT,
    password TEXT,
    client_mac TEXT,
    captured_at TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    ended_at TEXT,
    adapter_id TEXT,
    networks_found INTEGER,
    attacks_run INTEGER,
    captures INTEGER,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_networks_essid ON networks(essid);
CREATE INDEX IF NOT EXISTS idx_networks_channel ON networks(channel);
CREATE INDEX IF NOT EXISTS idx_clients_bssid ON clients(bssid);
CREATE INDEX IF NOT EXISTS idx_attacks_target ON attacks(target_bssid);
CREATE INDEX IF NOT EXISTS idx_captures_bssid ON captures(bssid);
"""


# ------------------------------------------------------------
# مدير قاعدة البيانات
# ------------------------------------------------------------
class Database:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        if self.conn is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(str(self.path))
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()
        logger.info(f"تم الاتصال بقاعدة البيانات: {self.path}")

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.info("تم إغلاق قاعدة البيانات.")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    # ---------- المحولات ----------
    async def save_adapter(self, adapter: dict):
        await self._ensure()
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO adapters
            (id, model, chipset, interface, monitor_interface, bands,
             driver, driver_type, max_standard, mac_address, usb_id,
             injection_ratio, first_seen, last_seen, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                adapter.get("id"),
                adapter.get("model"),
                adapter.get("chipset"),
                adapter.get("interface"),
                adapter.get("monitor_interface"),
                json.dumps(adapter.get("bands", [])),
                adapter.get("driver"),
                adapter.get("driver_type"),
                adapter.get("max_standard"),
                adapter.get("mac_address"),
                adapter.get("usb_id"),
                adapter.get("injection_ratio", 0),
                adapter.get("first_seen", datetime.now().isoformat()),
                datetime.now().isoformat(),
                json.dumps(adapter.get("metadata", {})),
            ),
        )
        await self.conn.commit()

    async def list_adapters(self) -> list[dict]:
        await self._ensure()
        cursor = await self.conn.execute("SELECT * FROM adapters ORDER BY last_seen DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ---------- الشبكات ----------
    async def save_network(self, network: dict):
        await self._ensure()
        await self.conn.execute(
            """
            INSERT INTO networks
            (bssid, essid, channel, band, encryption, cipher, auth, power,
             wps, wps_version, hidden, vendor, country, first_seen, last_seen, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(bssid) DO UPDATE SET
                essid=excluded.essid,
                channel=excluded.channel,
                power=excluded.power,
                last_seen=excluded.last_seen,
                metadata=excluded.metadata
            """,
            (
                network.get("bssid"),
                network.get("essid", ""),
                network.get("channel", 0),
                network.get("band", ""),
                network.get("encryption", ""),
                network.get("cipher", ""),
                network.get("auth", ""),
                network.get("power", 0),
                int(network.get("wps", False)),
                network.get("wps_version", ""),
                int(network.get("hidden", False)),
                network.get("vendor", ""),
                network.get("country", ""),
                network.get("first_seen", datetime.now().isoformat()),
                datetime.now().isoformat(),
                json.dumps(network.get("metadata", {})),
            ),
        )
        await self.conn.commit()

    async def save_networks_bulk(self, networks: list[dict]):
        await self._ensure()
        for net in networks:
            await self.save_network(net)

    async def list_networks(self, limit: int = 1000) -> list[dict]:
        await self._ensure()
        cursor = await self.conn.execute(
            "SELECT * FROM networks ORDER BY last_seen DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_network(self, bssid: str) -> Optional[dict]:
        await self._ensure()
        cursor = await self.conn.execute(
            "SELECT * FROM networks WHERE bssid = ?", (bssid,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # ---------- العملاء ----------
    async def save_client(self, bssid: str, client_mac: str, power: int, vendor: str = ""):
        await self._ensure()
        now = datetime.now().isoformat()
        await self.conn.execute(
            """
            INSERT INTO clients (bssid, client_mac, power, first_seen, last_seen, vendor)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(bssid, client_mac) DO UPDATE SET
                power=excluded.power,
                last_seen=excluded.last_seen
            """,
            (bssid, client_mac, power, now, now, vendor),
        )
        await self.conn.commit()

    async def list_clients(self, bssid: str) -> list[dict]:
        await self._ensure()
        cursor = await self.conn.execute(
            "SELECT * FROM clients WHERE bssid = ?", (bssid,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ---------- الهجمات ----------
    async def save_attack(self, attack: dict):
        await self._ensure()
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO attacks
            (id, type, target_bssid, target_essid, adapter_id, state,
             started_at, finished_at, progress, result, error, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                attack.get("id"),
                attack.get("type"),
                attack.get("target_bssid"),
                attack.get("target_essid"),
                attack.get("adapter_id"),
                attack.get("state"),
                attack.get("started_at"),
                attack.get("finished_at"),
                attack.get("progress", 0),
                json.dumps(attack.get("result")) if attack.get("result") else None,
                attack.get("error"),
                json.dumps(attack.get("metadata", {})),
            ),
        )
        await self.conn.commit()

    async def list_attacks(self, limit: int = 200) -> list[dict]:
        await self._ensure()
        cursor = await self.conn.execute(
            "SELECT * FROM attacks ORDER BY started_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ---------- عمليات الالتقاط ----------
    async def save_capture(
        self,
        bssid: str,
        cap_type: str,
        file_path: str,
        hashcat_path: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        await self._ensure()
        cursor = await self.conn.execute(
            """
            INSERT INTO captures (bssid, type, file_path, hashcat_path, captured_at, metadata)
            VALUES (?,?,?,?,?,?)
            """,
            (
                bssid,
                cap_type,
                file_path,
                hashcat_path,
                datetime.now().isoformat(),
                json.dumps(metadata or {}),
            ),
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def mark_cracked(self, capture_id: int, password: str):
        await self._ensure()
        await self.conn.execute(
            "UPDATE captures SET cracked = 1, password = ? WHERE id = ?",
            (password, capture_id),
        )
        await self.conn.commit()

    async def list_captures(self, bssid: Optional[str] = None) -> list[dict]:
        await self._ensure()
        if bssid:
            cursor = await self.conn.execute(
                "SELECT * FROM captures WHERE bssid = ? ORDER BY captured_at DESC",
                (bssid,),
            )
        else:
            cursor = await self.conn.execute(
                "SELECT * FROM captures ORDER BY captured_at DESC"
            )
        return [dict(r) for r in await cursor.fetchall()]

    # ---------- بيانات الاعتماد ----------
    async def save_credential(
        self,
        ssid: str,
        username: str,
        password: str,
        client_mac: str,
        source: str = "captive_portal",
    ):
        await self._ensure()
        await self.conn.execute(
            """
            INSERT INTO credentials (ssid, username, password, client_mac, captured_at, source)
            VALUES (?,?,?,?,?,?)
            """,
            (ssid, username, password, client_mac, datetime.now().isoformat(), source),
        )
        await self.conn.commit()

    async def list_credentials(self) -> list[dict]:
        await self._ensure()
        cursor = await self.conn.execute(
            "SELECT * FROM credentials ORDER BY captured_at DESC"
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ---------- الجلسات ----------
    async def start_session(self, adapter_id: str) -> int:
        await self._ensure()
        cursor = await self.conn.execute(
            "INSERT INTO sessions (started_at, adapter_id) VALUES (?,?)",
            (datetime.now().isoformat(), adapter_id),
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def end_session(self, session_id: int, stats: dict):
        await self._ensure()
        await self.conn.execute(
            """
            UPDATE sessions SET
                ended_at = ?,
                networks_found = ?,
                attacks_run = ?,
                captures = ?
            WHERE id = ?
            """,
            (
                datetime.now().isoformat(),
                stats.get("networks_found", 0),
                stats.get("attacks_run", 0),
                stats.get("captures", 0),
                session_id,
            ),
        )
        await self.conn.commit()

    # ---------- أدوات داخلية ----------
    async def _ensure(self):
        if self.conn is None:
            await self.connect()


# ------------------------------------------------------------
# نسخة عالمية
# ------------------------------------------------------------
_db: Optional[Database] = None


async def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
    return _db


async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None
