import argparse
import glob
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_all_tests import run_sql_file
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYERS = ["source", "staging", "warehouse", "analytics"]


# parses the layer selection for the dq run
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SQL data-quality checks for one layer"
    )
    parser.add_argument("--layer", required=True, choices=LAYERS)
    return parser.parse_args()


# runs every check file for the layer in filename order
def main() -> int:
    args = parse_args()
    paths = sorted(
        glob.glob(f"tests/data_quality/{args.layer}/*.sql", root_dir=PROJECT_ROOT)
    )
    if not paths:
        logger.error("no check files layer=%s", args.layer)
        return 2
    failed: list[str] = []
    for path in paths:
        outcome = run_sql_file(str(PROJECT_ROOT / path))
        state = "ok" if outcome["status"] == "SUCCESS" else "FAIL"
        logger.info("dq check %s %s (%ss)", path, state, outcome["seconds"])
        if outcome["status"] != "SUCCESS":
            failed.append(path)
    if failed:
        logger.error("dq %s FAILED files=%s", args.layer, ", ".join(failed))
        return 1
    logger.info("dq %s SUCCESS files=%d", args.layer, len(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
