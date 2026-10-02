import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_staging_load import call_procedure, print_summary

from src.utils.logger import get_logger

logger = get_logger(__name__)

PROCEDURES = [
    "warehouse.load_dim_customers",
    "warehouse.load_dim_products",
    "warehouse.load_fact_sales",
]


# parses CLI arguments for the warehouse run
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run warehouse load procedures in order"
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma separated procedure short names to run, empty means all in order",
    )
    return parser.parse_args()


# runs every warehouse procedure in dependency order
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
    results = [
        call_procedure(procedure, "run_warehouse_load") for procedure in procedures
    ]
    elapsed = (datetime.now(UTC) - started).total_seconds()
    print_summary(results, elapsed, "Warehouse load summary")
    failed = [r["name"] for r in results if r["status"] != "SUCCESS"]
    if failed:
        raise SystemExit(f"failed procedures: {', '.join(failed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
