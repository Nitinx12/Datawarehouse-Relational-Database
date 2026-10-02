import argparse
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.connection import get_postgres_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

PROCEDURES = [
    "staging.load_px_cat_g1v2",
    "staging.load_cust_info",
    "staging.load_prd_info",
    "staging.load_cust_az12",
    "staging.load_loc_a101",
    "staging.load_sales_details",
]

NOTICE_PATTERN = re.compile(
    r"staging\.[\w]+: staged=(\d+) inserted=(\d+) updated=(\d+) null-key skipped=(\d+)"
    r"|staging\.[\w]+: reloaded=(\d+) rows"
)


# parses CLI arguments for the staging run
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run staging load procedures in order")
    parser.add_argument(
        "--only",
        default="",
        help="Comma separated procedure short names to run, empty means all in order",
    )
    return parser.parse_args()


# extracts staged/inserted/updated counts from a procedure notice
def parse_notice(notice: str) -> dict:
    match = NOTICE_PATTERN.search(notice)
    if not match:
        return {"staged": 0, "inserted": 0, "updated": 0, "skipped": 0}
    if match.group(5) is not None:
        reloaded = int(match.group(5))
        return {"staged": reloaded, "inserted": reloaded, "updated": 0, "skipped": 0}
    return {
        "staged": int(match.group(1)),
        "inserted": int(match.group(2)),
        "updated": int(match.group(3)),
        "skipped": int(match.group(4)),
    }


# calls one procedure and returns its result row
def call_procedure(procedure: str) -> dict:
    started = time.time()
    result = {"name": procedure, "status": "SUCCESS", "error": None}
    result.update({"staged": 0, "inserted": 0, "updated": 0, "skipped": 0})
    conn = get_postgres_connection()
    try:
        conn.autocommit = True
        notices: list[str] = []
        conn.add_notice_handler(lambda diag: notices.append(diag.message_primary))
        conn.execute(f"CALL {procedure}()")
        for notice in notices:
            logger.info("%s", notice)
        if notices:
            result.update(parse_notice(notices[-1]))
    except Exception as exc:  # noqa: BLE001
        result["status"] = "FAILED"
        result["error"] = str(exc).strip().splitlines()[0][:200]
        logger.error("procedure failed name=%s error=%s", procedure, result["error"])
    finally:
        conn.close()
        result["seconds"] = round(time.time() - started, 1)
    return result


# renders the end-of-run summary table
def print_summary(results: list[dict], elapsed: float) -> None:
    table = Table(title="Staging load summary")
    table.add_column("Procedure", style="cyan")
    table.add_column("Staged", justify="right")
    table.add_column("Inserted", justify="right", style="green")
    table.add_column("Updated", justify="right")
    table.add_column("Skipped", justify="right", style="yellow")
    table.add_column("Time (s)", justify="right")
    table.add_column("Status", justify="center")
    for result in results:
        status = result["status"]
        table.add_row(
            result["name"],
            str(result["staged"]),
            str(result["inserted"]),
            str(result["updated"]),
            str(result["skipped"]),
            str(result["seconds"]),
            f"[green]{status}[/green]"
            if status == "SUCCESS"
            else f"[red]{status}[/red]",
        )
    table.add_row(
        "TOTAL",
        str(sum(r["staged"] for r in results)),
        str(sum(r["inserted"] for r in results)),
        str(sum(r["updated"] for r in results)),
        str(sum(r["skipped"] for r in results)),
        f"{elapsed:.1f}",
        "",
    )
    console.print(table)


# runs every staging procedure in dependency order
def main() -> int:
    started = datetime.now(UTC)
    args = parse_args()
    if args.only.strip():
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        procedures = [p for p in PROCEDURES if p.split(".")[1] in wanted or p in wanted]
    else:
        procedures = PROCEDURES
    if not procedures:
        logger.info("no procedures selected")
        return 0
    results = [call_procedure(procedure) for procedure in procedures]
    elapsed = (datetime.now(UTC) - started).total_seconds()
    print_summary(results, elapsed)
    failed = [r["name"] for r in results if r["status"] != "SUCCESS"]
    if failed:
        raise SystemExit(f"failed procedures: {', '.join(failed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
