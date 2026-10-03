# ============================================================
# Alfa Commander - Shell Utilities
# تشغيل الأوامر بشكل آمن وغير متزامن مع بث المخرجات
# ============================================================

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import signal
import subprocess
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Optional, Sequence

from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# نتيجة تنفيذ أمر
# ------------------------------------------------------------
@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def __str__(self) -> str:
        status = "✓" if self.ok else "✗"
        return f"[{status}] {self.command} (rc={self.returncode}, {self.duration:.2f}s)"


# ------------------------------------------------------------
# أدوات مساعدة عامة
# ------------------------------------------------------------
def command_exists(name: str) -> bool:
    """التحقق من وجود أمر في PATH."""
    return shutil.which(name) is not None


def require_root() -> None:
    """يرفع استثناء إذا لم يكن المستخدم root."""
    if os.geteuid() != 0:
        raise PermissionError("هذا الأمر يتطلب صلاحيات root")


def shell_quote(parts: Sequence[str]) -> str:
    """تحويل قائمة وسائط إلى سطر أمر آمن."""
    return " ".join(shlex.quote(str(p)) for p in parts)


# ------------------------------------------------------------
# تشغيل أمر (متزامن)
# ------------------------------------------------------------
def run(
    cmd: str | Sequence[str],
    timeout: Optional[float] = 30.0,
    check: bool = False,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    input_data: Optional[str] = None,
    capture: bool = True,
) -> CommandResult:
    """
    تشغيل أمر بشكل متزامن.

    Args:
        cmd: سلسلة أو قائمة وسائط
        timeout: المهلة بالثواني (None = لا حد)
        check: رفع استثناء إذا فشل الأمر
        cwd: مجلد العمل
        env: متغيرات بيئة إضافية
        input_data: نص يُمرر إلى stdin
        capture: إذا False، يُترك المخرجات تمر إلى الطرفية
    """
    if isinstance(cmd, str):
        args = shlex.split(cmd)
        cmd_str = cmd
    else:
        args = list(cmd)
        cmd_str = shell_quote(args)

    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    import time
    start = time.monotonic()

    try:
        if capture:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=full_env,
                input=input_data,
            )
            cmd_result = CommandResult(
                command=cmd_str,
                returncode=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                duration=time.monotonic() - start,
            )
        else:
            result = subprocess.run(
                args,
                timeout=timeout,
                cwd=cwd,
                env=full_env,
                input=input_data,
            )
            cmd_result = CommandResult(
                command=cmd_str,
                returncode=result.returncode,
                duration=time.monotonic() - start,
            )
    except subprocess.TimeoutExpired as e:
        logger.warning(f"انتهت مهلة الأمر: {cmd_str}")
        cmd_result = CommandResult(
            command=cmd_str,
            returncode=-1,
            stdout=(e.stdout or b"").decode(errors="ignore") if isinstance(e.stdout, bytes) else (e.stdout or ""),
            stderr=(e.stderr or b"").decode(errors="ignore") if isinstance(e.stderr, bytes) else (e.stderr or ""),
            duration=time.monotonic() - start,
            timed_out=True,
        )
    except FileNotFoundError:
        logger.error(f"الأمر غير موجود: {args[0]}")
        cmd_result = CommandResult(
            command=cmd_str,
            returncode=127,
            stderr=f"Command not found: {args[0]}",
            duration=time.monotonic() - start,
        )
    except Exception as e:
        logger.exception(f"فشل تنفيذ: {cmd_str}")
        cmd_result = CommandResult(
            command=cmd_str,
            returncode=-1,
            stderr=str(e),
            duration=time.monotonic() - start,
        )

    if check and not cmd_result.ok:
        raise RuntimeError(
            f"فشل الأمر: {cmd_str}\n"
            f"returncode={cmd_result.returncode}\n"
            f"stderr={cmd_result.stderr}"
        )

    return cmd_result


# ------------------------------------------------------------
# تشغيل أمر (غير متزامن)
# ------------------------------------------------------------
async def run_async(
    cmd: str | Sequence[str],
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
) -> CommandResult:
    """تشغيل أمر بشكل غير متزامن."""
    if isinstance(cmd, str):
        args = shlex.split(cmd)
        cmd_str = cmd
    else:
        args = list(cmd)
        cmd_str = shell_quote(args)

    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    import time
    start = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=full_env,
        )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return CommandResult(
                command=cmd_str,
                returncode=proc.returncode or 0,
                stdout=stdout_b.decode(errors="ignore"),
                stderr=stderr_b.decode(errors="ignore"),
                duration=time.monotonic() - start,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return CommandResult(
                command=cmd_str,
                returncode=-1,
                duration=time.monotonic() - start,
                timed_out=True,
            )
    except FileNotFoundError:
        return CommandResult(
            command=cmd_str,
            returncode=127,
            stderr=f"Command not found: {args[0]}",
            duration=time.monotonic() - start,
        )


# ------------------------------------------------------------
# عملية طويلة الأمد مع بث المخرجات
# ------------------------------------------------------------
class StreamingProcess:
    """
    يدير عملية طويلة الأمد (airodump-ng، aireplay-ng، إلخ)
    ويوفّر بثاً مباشراً للأسطر.
    """

    def __init__(
        self,
        cmd: str | Sequence[str],
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ):
        if isinstance(cmd, str):
            self.args = shlex.split(cmd)
            self.command_str = cmd
        else:
            self.args = list(cmd)
            self.command_str = shell_quote(self.args)

        self.on_stdout = on_stdout
        self.on_stderr = on_stderr
        self.on_exit = on_exit
        self.cwd = cwd

        self.env = os.environ.copy()
        if env:
            self.env.update(env)

        self.proc: Optional[asyncio.subprocess.Process] = None
        self._running = False
        self._tasks: list[asyncio.Task] = []

    @property
    def running(self) -> bool:
        return self._running

    @property
    def pid(self) -> Optional[int]:
        return self.proc.pid if self.proc else None

    async def start(self):
        if self._running:
            return
        logger.debug(f"تشغيل: {self.command_str}")
        self.proc = await asyncio.create_subprocess_exec(
            *self.args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            env=self.env,
            preexec_fn=os.setsid,  # مجموعة عمليات منفصلة للإيقاف الآمن
        )
        self._running = True
        self._tasks = [
            asyncio.create_task(self._pump(self.proc.stdout, self.on_stdout)),
            asyncio.create_task(self._pump(self.proc.stderr, self.on_stderr)),
            asyncio.create_task(self._wait()),
        ]

    async def _pump(self, stream: Optional[asyncio.StreamReader], callback: Optional[Callable[[str], None]]):
        if stream is None:
            return
        try:
            while True:
                line_b = await stream.readline()
                if not line_b:
                    break
                line = line_b.decode(errors="ignore").rstrip("\n")
                if callback:
                    try:
                        callback(line)
                    except Exception as e:
                        logger.exception(f"خطأ في callback: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"خطأ في بث المخرجات: {e}")

    async def _wait(self):
        if self.proc is None:
            return
        rc = await self.proc.wait()
        self._running = False
        logger.debug(f"انتهت العملية {self.command_str} (rc={rc})")
        if self.on_exit:
            try:
                self.on_exit(rc)
            except Exception:
                logger.exception("خطأ في on_exit")

    async def stop(self, timeout: float = 5.0):
        """إيقاف العملية بأمان (SIGTERM ثم SIGKILL)."""
        if not self.proc or not self._running:
            return
        try:
            pgid = os.getpgid(self.proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:
            self.proc.terminate()

        try:
            await asyncio.wait_for(self.proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"العملية لم تستجب، إرسال SIGKILL: {self.command_str}")
            try:
                pgid = os.getpgid(self.proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                self.proc.kill()

        for t in self._tasks:
            if not t.done():
                t.cancel()
        self._running = False

    async def wait(self) -> int:
        if self.proc is None:
            return -1
        return await self.proc.wait()


# ------------------------------------------------------------
# التحقق من وجود أدوات متعددة دفعة واحدة
# ------------------------------------------------------------
def check_tools(tools: Sequence[str]) -> dict[str, bool]:
    """يرجع dict باسم الأداة وحالتها."""
    return {tool: command_exists(tool) for tool in tools}


def missing_tools(tools: Sequence[str]) -> list[str]:
    return [t for t in tools if not command_exists(t)]


# ------------------------------------------------------------
# تشغيل أمر مع sudo
# ------------------------------------------------------------
def run_sudo(cmd: str | Sequence[str], **kwargs) -> CommandResult:
    """تشغيل أمر عبر sudo (دون إدخال كلمة مرور تفاعلياً)."""
    if isinstance(cmd, str):
        args = ["sudo", "-n"] + shlex.split(cmd)
    else:
        args = ["sudo", "-n"] + list(cmd)
    return run(args, **kwargs)
