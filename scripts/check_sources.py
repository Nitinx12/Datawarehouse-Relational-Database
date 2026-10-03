import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.connection import (
    close_connection,
    get_databricks_connection,
    get_mongo_client,
    get_postgres_connection,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


# checks postgres reachability with a trivial query
def check_postgres() -> None:
    connection = get_postgres_connection()
    try:
        connection.execute("SELECT 1")
    finally:
        close_connection(connection)


# checks mongo reachability with a ping command
def check_mongo() -> None:
    client = get_mongo_client()
    try:
        client.admin.command("ping")
    finally:
        client.close()


# checks databricks when configured, warns and skips otherwise
def check_databricks() -> None:
    if not os.getenv("DATABRICKS_HOST", "").strip():
        logger.warning("databricks not configured, skipping databricks check")
        return
    connection = get_databricks_connection()
    try:
        connection.cursor().execute("SELECT 1")
    finally:
        close_connection(connection)


# fails fast when any required source is unreachable
def main() -> int:
    checks = [
        ("postgres", check_postgres),
        ("mongo", check_mongo),
        ("databricks", check_databricks),
    ]
    failed: list[str] = []
    for name, check in checks:
        try:
            check()
            logger.info("source reachable name=%s", name)
        except Exception as exc:  # noqa: BLE001
            logger.error("source unreachable name=%s error=%s", name, exc)
            failed.append(name)
    if failed:
        logger.error("preflight FAILED sources=%s", ",".join(failed))
        return 2
    logger.info("preflight SUCCESS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
