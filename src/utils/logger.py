import logging
import os

from dotenv import load_dotenv

load_dotenv()

_configured: set[str] = set()


# returns a configured logger for the given name
def get_logger(name: str) -> logging.Logger:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = logging.getLevelName(level_name)
    resolved = level if isinstance(level, int) else logging.INFO
    logger = logging.getLogger(name)
    logger.setLevel(resolved)
    if name not in _configured:
        handler = logging.StreamHandler()
        handler.setLevel(resolved)
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
        _configured.add(name)
    return logger
