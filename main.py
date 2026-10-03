# runs the full warehouse pipeline from extract to master gate
import argparse
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from run_staging_load import call_procedure

console = Console()

STAGES = [
    "extract",
    "source-tests",
    "staging",
    "staging-tests",
    "warehouse",
    "warehouse-tests",
    "analytics",
    "analytics-tests",
    "master",
]

EXTRACT_JOBS = ["run_mongo_job.py", "run_databricks_job.py"]

STAGING_PROCEDURES = [
    "staging.load_px_cat_g1v2",
    "staging.load_cust_info",
    "staging.load_prd_info",
    "staging.load_cust_az12",
    "staging.load_loc_a101",
    "staging.load_sales_details",
]

WAREHOUSE_PROCEDURES = [
    "warehouse.load_dim_customers",
    "warehouse.load_dim_products",
    "warehouse.load_fact_sales",
]

ANALYTICS_PROCEDURES = ["analytics.load_monthly_kpi_snapshot"]


# parses stage selection for the pipeline run
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the warehouse pipeline end to end"
    )
    parser.add_argument(
        "--skip",
        default="",
        help="Comma separated stages to skip, e.g. --skip extract,master",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma separated stages to run, empty means every stage in order",
    )
    return parser.parse_args()


# resolves the ordered stage list from skip/only filters
def select_stages(skip: str, only: str) -> list[str]:
    if only.strip():
        wanted = {name.strip() for name in only.split(",") if name.strip()}
        unknown = wanted - set(STAGES)
        if unknown:
            raise SystemExit(f"unknown stages: {', '.join(sorted(unknown))}")
        return [stage for stage in STAGES if stage in wanted]
    skipped = {name.strip() for name in skip.split(",") if name.strip()}
    return [stage for stage in STAGES if stage not in skipped]


# extracts the last stderr line for a failed extract job
def extract_error(proc: subprocess.CompletedProcess[str]) -> str:
    lines = proc.stderr.strip().splitlines()
    if lines:
        return lines[-1][:200]
    return f"exit={proc.returncode}"


# runs one spark extract job file and returns its result row
def run_extract_job(job_file: str) -> dict:
    started = time.time()
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / job_file)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    passed = proc.returncode == 0
    return {
        "name": f"extract {Path(job_file).stem}",
        "status": "SUCCESS" if passed else "FAILED",
        "seconds": round(time.time() - started, 1),
        "detail": "" if passed else extract_error(proc),
    }


# runs the mongo and databricks extracts into source
def run_extract() -> list[dict]:
    return [run_extract_job(job) for job in EXTRACT_JOBS]


# runs the layer SQL data-quality checks and returns its result row
def run_dq_checks(layer: str) -> dict:
    started = time.time()
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_dq_checks.py"), "--layer", layer],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    passed = proc.returncode == 0
    return {
        "name": f"dq {layer}",
        "status": "SUCCESS" if passed else "FAILED",
        "seconds": round(time.time() - started, 1),
        "detail": "" if passed else extract_error(proc),
    }


# runs one GX layer gate and returns its result row
def run_gx_gate(layer: str) -> dict:
    import great_expectations as gx

    from scripts.run_gx_validations import run_layer
    from scripts.setup_gx_project import LAYERS, table_specs

    assert layer in LAYERS, layer
    context = gx.get_context(mode="file", project_root_dir=str(ROOT))
    outcome = run_layer(context, layer, table_specs())
    return {
        "name": f"gx {layer}",
        "status": "SUCCESS" if outcome["success"] else "FAILED",
        "seconds": outcome["seconds"],
        "detail": outcome["detail"],
    }


# runs load procedures in order and returns one row per procedure
def run_load(procedures: list[str], source: str) -> list[dict]:
    rows: list[dict] = []
    for procedure in procedures:
        outcome = call_procedure(procedure, source)
        rows.append(
            {
                "name": procedure,
                "status": outcome["status"],
                "seconds": outcome["seconds"],
                "detail": outcome["error"] or "",
            }
        )
        if outcome["status"] != "SUCCESS":
            break
    return rows


# refreshes analytics marts and the monthly snapshot
def run_analytics() -> list[dict]:
    return run_load(ANALYTICS_PROCEDURES, "main")


# runs the master gate over every table validation
def run_master_gate() -> list[dict]:
    import great_expectations as gx

    from scripts.run_gx_validations import run_master
    from scripts.setup_gx_project import table_specs

    context = gx.get_context(mode="file", project_root_dir=str(ROOT))
    outcome = run_master(context, table_specs())
    return [
        {
            "name": "gx master",
            "status": "SUCCESS" if outcome["success"] else "FAILED",
            "seconds": outcome["seconds"],
            "detail": outcome["detail"],
        }
    ]


# dispatches one pipeline stage to its runner
def run_stage(stage: str) -> list[dict]:
    if stage == "extract":
        return run_extract()
    if stage in ("staging", "warehouse"):
        procedures = STAGING_PROCEDURES if stage == "staging" else WAREHOUSE_PROCEDURES
        return run_load(procedures, "main")
    if stage == "analytics":
        return run_analytics()
    if stage == "master":
        return run_master_gate()
    layer = stage.removesuffix("-tests")
    dq_row = run_dq_checks(layer)
    if dq_row["status"] != "SUCCESS":
        return [dq_row]
    return [dq_row, run_gx_gate(layer)]


# renders the end-of-run summary table
def print_summary(results: list[dict], elapsed: float) -> None:
    table = Table(title="Pipeline run summary")
    table.add_column("Step", style="cyan")
    table.add_column("Time (s)", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Detail", overflow="fold", max_width=60)
    for result in results:
        status = result["status"]
        table.add_row(
            result["name"],
            str(result["seconds"]),
            f"[green]{status}[/green]"
            if status == "SUCCESS"
            else f"[red]{status}[/red]",
            result["detail"],
        )
    console.print(table)
    console.print(f"elapsed={elapsed:.1f}s steps={len(results)}")


# runs every pipeline stage in dependency order with fail-fast
def main() -> int:
    started = datetime.now(UTC)
    args = parse_args()
    stages = select_stages(args.skip, args.only)
    if not stages:
        console.print("no stages selected")
        return 0
    results: list[dict] = []
    for stage in stages:
        console.print(f"[bold]stage: {stage}[/bold]")
        for row in run_stage(stage):
            results.append(row)
            state = (
                "[green]ok[/green]" if row["status"] == "SUCCESS" else "[red]FAIL[/red]"
            )
            console.print(
                f"  {row['name']} {state} ({row['seconds']}s) {row['detail']}"
            )
        if any(row["status"] != "SUCCESS" for row in results):
            break
    elapsed = (datetime.now(UTC) - started).total_seconds()
    print_summary(results, elapsed)
    failed = [row["name"] for row in results if row["status"] != "SUCCESS"]
    if failed:
        raise SystemExit(f"pipeline FAILED at: {', '.join(failed)}")
    console.print("[green]pipeline SUCCESS[/green]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
