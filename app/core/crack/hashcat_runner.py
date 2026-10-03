# ============================================================
# Alfa Commander - Hashcat Runner
# تشغيل hashcat ومراقبة التقدم
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.constants import AttackState
from app.utils.shell import StreamingProcess, run, command_exists
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نماذج
# ------------------------------------------------------------
@dataclass
class HashcatOptions:
    hash_file: Path
    hash_mode: int = 22000
    wordlist: Optional[Path] = None
    rules: Optional[list[str]] = None
    mask: Optional[str] = None              # للهجوم بالقوة الغاشمة
    increment: bool = False
    workload: int = 2                       # 1-4
    optimized: bool = True
    force: bool = False
    potfile: Optional[Path] = None
    session_name: str = "alfa_commander"
    restore: bool = True
    status_interval: int = 5                # ثواني


@dataclass
class HashcatProgress:
    status: str = "running"                 # running / cracked / exhausted / error
    recovered: int = 0
    total: int = 0
    progress_percent: float = 0.0
    speed_hps: int = 0                      # hash/s
    time_started: Optional[datetime] = None
    time_estimated: float = 0.0             # ثواني
    password: Optional[str] = None
    raw_line: str = ""


# ------------------------------------------------------------
# المشغل
# ------------------------------------------------------------
class HashcatRunner:
    """
    يدير تشغيل hashcat مع مراقبة التقدم.
    """

    BINARY = "hashcat"

    def __init__(
        self,
        opts: HashcatOptions,
        on_progress: Optional[Callable[[HashcatProgress], None]] = None,
        on_cracked: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
    ):
        self.opts = opts
        self.on_progress = on_progress
        self.on_cracked = on_cracked
        self.on_exit = on_exit

        self._process: Optional[StreamingProcess] = None
        self.progress = HashcatProgress()

    @staticmethod
    def is_available() -> bool:
        return command_exists(HashcatRunner.BINARY)

    # ---------- بناء الأمر ----------
    def build_command(self) -> list[str]:
        args = [
            self.BINARY,
            "-m", str(self.opts.hash_mode),
            "-a", "0" if self.opts.wordlist else "3",  # 0=wordlist, 3=mask
            "--status",
            "--status-timer", str(self.opts.status_interval),
            "--potfile-path", str(self.opts.potfile or (self.opts.hash_file.parent / "hashcat.potfile")),
            "--session", self.opts.session_name,
        ]

        if self.opts.optimized:
            args.append("-O")
        if self.opts.force:
            args.append("--force")
        if self.opts.increment:
            args.append("--increment")

        args.extend(["-w", str(self.opts.workload)])

        if self.opts.restore:
            args.append("--restore")

        # الملف + القاموس/القناع
        if self.opts.wordlist:
            args.append(str(self.opts.hash_file))
            args.append(str(self.opts.wordlist))
            if self.opts.rules:
                for rule in self.opts.rules:
                    args.extend(["-r", rule])
        elif self.opts.mask:
            args.append(str(self.opts.hash_file))
            args.append(self.opts.mask)
        else:
            raise ValueError("يجب تحديد wordlist أو mask")

        return args

    # ---------- التشغيل ----------
    async def start(self) -> HashcatProgress:
        args = self.build_command()
        logger.info(f"بدء hashcat: {' '.join(args)}")

        self.progress.time_started = datetime.now()
        self.progress.status = "running"

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

        # Status line: "Time.Started.....: Mon Jan 1 12:00:00 2024 (10 secs)"
        # "Recovered........: 0/1 (0.00%) Digests"
        # "Progress.........: 1000/5000 (20.00%)"
        # "Speed.#1.........: 1234 H/s"

        # Recovered
        m = re.search(r"Recovered\.+:\s*(\d+)/(\d+)\s*\(([\d.]+)%\)", line)
        if m:
            self.progress.recovered = int(m.group(1))
            self.progress.total = int(m.group(2))
            self.progress.progress_percent = float(m.group(3))

        # Speed
        m = re.search(r"Speed\.#\d+\.+:\s*(\d+)\s*H/s", line)
        if m:
            self.progress.speed_hps = int(m.group(1))

        # Time estimated
        m = re.search(r"Time\.Estimated\.+:\s*\((\d+)\s*secs?\)", line)
        if m:
            self.progress.time_estimated = float(m.group(1))

        # Cracked password
        if ":" in line and self.opts.hash_mode == 22000:
            # صيغة: hash:password
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[1].strip():
                self.progress.password = parts[1].strip()
                if self.on_cracked:
                    try:
                        self.on_cracked(self.progress.password)
                    except Exception:
                        pass

        # Status
        if "Status" in line:
            m = re.search(r"Status\.+:\s*(\S+)", line)
            if m:
                self.progress.status = m.group(1).lower()

        # إرسال الحدث
        if self.on_progress:
            try:
                self.on_progress(self.progress)
            except Exception:
                pass

    def _handle_exit(self, rc: int):
        if self.progress.password:
            self.progress.status = "cracked"
            logger.info(f"تم كسر الهاش: {self.progress.password}")
        elif rc == 0:
            self.progress.status = "exhausted"
            logger.info("انتهى hashcat بدون كسر")
        else:
            self.progress.status = "error"
            logger.warning(f"hashcat انتهى برمز {rc}")

        if self.on_exit:
            try:
                self.on_exit(rc)
            except Exception:
                pass


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
async def crack_handshake(
    hash_file: Path,
    wordlist: Path,
    hash_mode: int = 22000,
    on_cracked: Optional[Callable[[str], None]] = None,
) -> HashcatProgress:
    """كسر مصافحة/PMKID."""
    opts = HashcatOptions(
        hash_file=hash_file,
        hash_mode=hash_mode,
        wordlist=wordlist,
    )
    runner = HashcatRunner(opts, on_cracked=on_cracked)
    return await runner.start()


async def crack_with_mask(
    hash_file: Path,
    mask: str,
    hash_mode: int = 22000,
) -> HashcatProgress:
    """كسر بقناع (brute force)."""
    opts = HashcatOptions(
        hash_file=hash_file,
        hash_mode=hash_mode,
        mask=mask,
    )
    runner = HashcatRunner(opts)
    return await runner.start()
