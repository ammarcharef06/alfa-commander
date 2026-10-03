# ============================================================
# Alfa Commander - Aircrack-ng Runner
# كسر WPA/WPA2 عبر aircrack-ng
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.utils.shell import StreamingProcess, command_exists
from app.logger import get_logger

logger = get_logger()


@dataclass
class AircrackProgress:
    status: str = "running"
    keys_tested: int = 0
    keys_per_second: int = 0
    progress_percent: float = 0.0
    password: Optional[str] = None
    bssid: Optional[str] = None
    ssid: Optional[str] = None
    raw_line: str = ""


class AircrackRunner:
    BINARY = "aircrack-ng"

    def __init__(
        self,
        cap_file: Path,
        wordlist: Path,
        bssid: Optional[str] = None,
        essid: Optional[str] = None,
        on_progress: Optional[Callable[[AircrackProgress], None]] = None,
        on_cracked: Optional[Callable[[str], None]] = None,
    ):
        self.cap_file = cap_file
        self.wordlist = wordlist
        self.bssid = bssid
        self.essid = essid
        self.on_progress = on_progress
        self.on_cracked = on_cracked

        self.progress = AircrackProgress(bssid=bssid, ssid=essid)
        self._process: Optional[StreamingProcess] = None

    @staticmethod
    def is_available() -> bool:
        return command_exists(AircrackRunner.BINARY)

    def build_command(self) -> list[str]:
        args = [self.BINARY, "-w", str(self.wordlist)]
        if self.bssid:
            args.extend(["-b", self.bssid])
        if self.essid:
            args.extend(["-e", self.essid])
        args.extend(["-l", str(self.cap_file.with_suffix(".key"))])
        args.append(str(self.cap_file))
        return args

    async def start(self) -> AircrackProgress:
        args = self.build_command()
        logger.info(f"بدء aircrack-ng: {' '.join(args)}")

        self._process = StreamingProcess(
            args,
            on_stdout=self._handle_line,
            on_stderr=self._handle_line,
            on_exit=self._handle_exit,
        )
        await self._process.start()
        return self.progress

    async def stop(self):
        if self._process and self._process.running:
            await self._process.stop()

    def _handle_line(self, line: str):
        if not line:
            return
        self.progress.raw_line = line

        # BSSID/ESSID
        m = re.search(r"\s+(\d+)\s+([0-9A-F:]{17})\s+(.+?)\s+(\S+)", line)
        if m:
            self.progress.bssid = m.group(2)
            self.progress.ssid = m.group(3).strip()

        # "KEY FOUND! [ password ]"
        m = re.search(r"KEY FOUND!\s*\[\s*(.+?)\s*\]", line)
        if m:
            self.progress.password = m.group(1)
            self.progress.status = "cracked"
            if self.on_cracked:
                try:
                    self.on_cracked(self.progress.password)
                except Exception:
                    pass

        # "1234 keys tested (12.34 k/s)"
        m = re.search(r"(\d+)\s+keys tested\s+\(([\d.]+)\s*k/s\)", line)
        if m:
            self.progress.keys_tested = int(m.group(1))
            self.progress.keys_per_second = int(float(m.group(2)) * 1000)

        # "0.45% WPA (1 handshake)"
        m = re.search(r"([\d.]+)%\s+WPA", line)
        if m:
            self.progress.progress_percent = float(m.group(1))

        if self.on_progress:
            try:
                self.on_progress(self.progress)
            except Exception:
                pass

    def _handle_exit(self, rc: int):
        if not self.progress.password:
            self.progress.status = "exhausted"
            logger.info("انتهى aircrack-ng بدون كسر")


async def crack_with_aircrack(
    cap_file: Path,
    wordlist: Path,
    bssid: Optional[str] = None,
) -> AircrackProgress:
    runner = AircrackRunner(cap_file, wordlist, bssid)
    return await runner.start()
