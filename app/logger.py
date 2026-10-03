# ============================================================
# Alfa Commander - Logger
# نظام تسجيل موحد
# ============================================================

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Callable

from app.constants import LOG_FILE, LogLevel
from app.config import get_config


# ------------------------------------------------------------
# ألوان الطرفية
# ------------------------------------------------------------
class Colors:
    RESET = "\033[0m"
    GRAY = "\033[90m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD_RED = "\033[1;91m"
    CYAN = "\033[96m"


LOG_COLORS = {
    "DEBUG": Colors.GRAY,
    "INFO": Colors.CYAN,
    "WARNING": Colors.YELLOW,
    "ERROR": Colors.RED,
    "CRITICAL": Colors.BOLD_RED,
}


# ------------------------------------------------------------
# مُنسّق الطرفية الملوّن
# ------------------------------------------------------------
class ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = LOG_COLORS.get(record.levelname, Colors.RESET)
        record.levelname_colored = f"{color}{record.levelname:<8}{Colors.RESET}"
        return super().format(record)


# ------------------------------------------------------------
# معالج مخصص لعرض السجلات في الواجهة الرسومية
# ------------------------------------------------------------
class QtSignalHandler(logging.Handler):
    """
    يرسل السجلات إلى callback (يُستخدم من الواجهة الرسومية).
    """

    def __init__(self, callback: Optional[Callable[[str, str], None]] = None):
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord):
        if self.callback is None:
            return
        try:
            msg = self.format(record)
            self.callback(record.levelname, msg)
        except Exception:
            self.handleError(record)


# ------------------------------------------------------------
# المُسجّل الرئيسي
# ------------------------------------------------------------
_logger: Optional[logging.Logger] = None
_qt_handler: Optional[QtSignalHandler] = None


def setup_logger(
    name: str = "alfa",
    gui_callback: Optional[Callable[[str, str], None]] = None,
) -> logging.Logger:
    global _logger, _qt_handler

    if _logger is not None:
        if gui_callback and _qt_handler:
            _qt_handler.callback = gui_callback
        return _logger

    cfg = get_config().config.logging
    level = getattr(logging, cfg.level.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    # إزالة أي معالجات قديمة
    logger.handlers.clear()

    # ------ معالج الملف ------
    if cfg.file_enabled:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=cfg.max_bytes,
            backupCount=cfg.backup_count,
            encoding="utf-8",
        )
        file_fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    # ------ معالج الطرفية ------
    if cfg.console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_fmt = ColoredFormatter(
            fmt="%(asctime)s | %(levelname_colored)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_fmt)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    # ------ معالج الواجهة الرسومية ------
    _qt_handler = QtSignalHandler(gui_callback)
    qt_fmt = logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S")
    _qt_handler.setFormatter(qt_fmt)
    _qt_handler.setLevel(level)
    logger.addHandler(_qt_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    if _logger is None:
        return setup_logger()
    return _logger


def attach_gui_callback(callback: Callable[[str, str], None]):
    """ربط واجهة المستخدم بمُسجّل السجلات."""
    global _qt_handler
    if _qt_handler is None:
        setup_logger(gui_callback=callback)
    else:
        _qt_handler.callback = callback


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
def debug(msg: str, *args, **kwargs):
    get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    get_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    get_logger().critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    get_logger().exception(msg, *args, **kwargs)
