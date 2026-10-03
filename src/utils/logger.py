import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_configured: set[str] = set()


# log level from environment, INFO when unset or invalid
def _level() -> int:
    level = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO").upper())
    return level if isinstance(level, int) else logging.INFO


# shared formatter for console and file handlers
def _formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# rotating file handler, None when the log dir is not writable
def _file_handler(
    level: int, formatter: logging.Formatter
) -> RotatingFileHandler | None:
    try:
        log_dir = Path(os.getenv("LOG_DIR", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "warehouse.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler
    except OSError:
        return None


# returns a configured logger for the given name
def get_logger(name: str) -> logging.Logger:
    level = _level()
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if name not in _configured:
        formatter = _formatter()
        stream = logging.StreamHandler()
        stream.setLevel(level)
        stream.setFormatter(formatter)
        logger.addHandler(stream)
        file_handler = _file_handler(level, formatter)
        if file_handler is not None:
            logger.addHandler(file_handler)
        logger.propagate = False
        _configured.add(name)
    return logger
