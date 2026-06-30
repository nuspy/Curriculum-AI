from __future__ import annotations

import sys

from loguru import logger

from ..config.settings import get_settings

_configured = False

_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - {message}"
)


def setup_logging(level: str | None = None):
    """Configura loguru su stderr. Idempotente."""
    global _configured
    lvl = (level or get_settings().log_level).upper()
    logger.remove()
    logger.add(sys.stderr, level=lvl, backtrace=False, diagnose=False, format=_FORMAT)
    _configured = True
    return logger


def get_logger():
    if not _configured:
        setup_logging()
    return logger
