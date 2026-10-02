import argparse
import glob
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

DQ_SUITES = ["source", "staging", "warehouse"]


# parses CLI arguments for the test run
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all tests in order")
    parser.add_argument(
        "--skip",
        default="",
        help="Comma separated stages to skip from unit, smoke, dq",
    )
    return parser.parse_args()


# runs one pytest suite and returns its pass state
def run_pytest(suite: str) -> dict:
    started = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", f"tests/{suite}", "-q"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    passed = proc.returncode == 0
    logger.info("pytest %s %s", suite, "PASS" if passed else "FAIL")
    if not passed:
        logger.error("%s", proc.stdout[-2000:])
    return {
        "name": f"pytest {suite}",
        "status": "SUCCESS" if passed else "FAILED",
        "seconds": round(time.time() - started, 1),
        "detail": "",
    }


# runs one SQL loop file and returns its pass state
def run_sql_file(path: str) -> dict:
    import psycopg

    started = time.time()
    result = {
        "name": Path(path).as_posix(),
        "status": "SUCCESS",
        "seconds": 0.0,
        "detail": "",
    }
    conn = psycopg.connect(
        host="localhost",
        port="5432",
        dbname="datawarehouse",
        user="postgres",
        password="admin",
        autocommit=True,
    )
    try:
        with open(path, encoding="utf-8") as handle:
            conn.execute(handle.read())
    except Exception as exc:  # noqa: BLE001
        result["status"] = "FAILED"
        result["detail"] = str(exc).strip().splitlines()[0][:200]
        logger.error("sql failed name=%s error=%s", path, result["detail"])
    finally:
        conn.close()
        result["seconds"] = round(time.time() - started, 1)
    return result


# checks postgres reachability once before the DQ stage
def pg_reachable() -> bool:
    import psycopg

    try:
        conn = psycopg.connect(
            host="localhost",
            port="5432",
            dbname="datawarehouse",
            user="postgres",
            password="admin",
            connect_timeout=5,
            autocommit=True,
        )
        conn.close()
        return True
    except Exception:  # noqa: BLE001
        return False


# runs every DQ loop suite in layer order
def run_dq() -> list[dict]:
    results: list[dict] = []
    for suite in DQ_SUITES:
        for path in sorted(
            glob.glob(f"tests/data_quality/{suite}/*.sql", root_dir=PROJECT_ROOT)
        ):
            full = str(PROJECT_ROOT / path)
            logger.info("running %s", path)
            outcome = run_sql_file(full)
            outcome["name"] = path
            results.append(outcome)
    return results


# renders the end-of-run summary table
def print_summary(results: list[dict], elapsed: float) -> None:
    table = Table(title="Test run summary")
    table.add_column("Suite", style="cyan")
    table.add_column("Time (s)", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Detail", overflow="fold", max_width=60)
    for result in results:
        status = result["status"]
        table.add_row(
            result["name"],
            str(result["seconds"]),
            f"[green]{status}[/green]"
            if status in ("SUCCESS", "PASS")
            else f"[red]{status}[/red]",
            result["detail"],
        )
    console.print(table)
    console.print(f"elapsed={elapsed:.1f}s suites={len(results)}")


# runs unit, smoke and DQ suites in order
def main() -> int:
    started = datetime.now(UTC)
    args = parse_args()
    skipped = {name.strip() for name in args.skip.split(",") if name.strip()}
    results: list[dict] = []
    if "unit" not in skipped:
        results.append(run_pytest("unit"))
    if "smoke" not in skipped and not any(r["status"] == "FAILED" for r in results):
        results.append(run_pytest("smoke"))
    if "dq" not in skipped and not any(r["status"] == "FAILED" for r in results):
        if not pg_reachable():
            logger.error("postgres unreachable, skipping dq loops")
            results.append(
                {
                    "name": "dq loops",
                    "status": "FAILED",
                    "seconds": 0.0,
                    "detail": "postgres unreachable",
                }
            )
        else:
            for outcome in run_dq():
                results.append(
                    {
                        "name": outcome["name"],
                        "status": "SUCCESS"
                        if outcome["status"] == "SUCCESS"
                        else "FAILED",
                        "seconds": outcome["seconds"],
                        "detail": outcome["detail"],
                    }
                )
    elapsed = (datetime.now(UTC) - started).total_seconds()
    print_summary(results, elapsed)
    failed = [r["name"] for r in results if r["status"] not in ("SUCCESS", "PASS")]
    if failed:
        raise SystemExit(f"failed suites: {', '.join(failed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
