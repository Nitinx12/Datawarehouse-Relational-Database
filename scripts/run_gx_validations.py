# runs GX layer checkpoints plus the master gate over fresh frames
import sys
import time
from pathlib import Path

import great_expectations as gx
import pandas as pd
from great_expectations.data_context import FileDataContext

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


# loads one spec query into a dataframe with the spec column order
def fetch_frame(query: str, columns: list[str]) -> pd.DataFrame:
    from src.utils.engine import read_postgres

    return read_postgres(query)[columns]


# imports table specs without rebuilding the project
def load_specs() -> dict[str, dict]:
    from scripts.setup_gx_project import table_specs

    return table_specs()


# runs one table validation and summarizes its result
def run_validation(validation: object, frame: pd.DataFrame) -> tuple[bool, str]:
    try:
        result = validation.run(batch_parameters={"dataframe": frame})
    except Exception as exc:  # noqa: BLE001
        return False, str(exc).strip().splitlines()[0][:200]
    if bool(result.success):
        return True, ""
    detail = "; ".join(
        run.expectation_config.get("type", "?")
        for run in result.results
        if not run.success
    )[:200]
    return False, detail


# runs every table validation inside one layer checkpoint
def run_layer(context: FileDataContext, layer: str, specs: dict[str, dict]) -> dict:
    started = time.time()
    tables: list[str] = []
    try:
        checkpoint = context.checkpoints.get(f"{layer}_layer")
    except Exception as exc:  # noqa: BLE001
        return {
            "name": f"gx {layer}",
            "layer": layer,
            "success": False,
            "seconds": round(time.time() - started, 1),
            "detail": str(exc).strip().splitlines()[0][:200],
        }
    for validation in checkpoint.validation_definitions:
        asset = validation.name.removesuffix("_validation")
        spec = specs[asset]
        try:
            frame = fetch_frame(spec["query"], spec["columns"])
        except Exception as exc:  # noqa: BLE001
            tables.append(f"{asset}: {str(exc).strip().splitlines()[0][:100]}")
            continue
        success, detail = run_validation(validation, frame)
        if not success:
            tables.append(f"{asset}: {detail}" if detail else asset)
    return {
        "name": f"gx {layer}",
        "layer": layer,
        "success": not tables,
        "seconds": round(time.time() - started, 1),
        "detail": "" if not tables else f"failed tables: {', '.join(tables)}"[:200],
    }


# runs the master checkpoint holding every table validation
def run_master(context: FileDataContext, specs: dict[str, dict]) -> dict:
    started = time.time()
    try:
        checkpoint = context.checkpoints.get("master_layer")
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "gx master",
            "layer": "master",
            "success": False,
            "seconds": round(time.time() - started, 1),
            "detail": str(exc).strip().splitlines()[0][:200],
        }
    tables: list[str] = []
    for validation in checkpoint.validation_definitions:
        asset = validation.name.removesuffix("_validation")
        spec = specs[asset]
        try:
            frame = fetch_frame(spec["query"], spec["columns"])
        except Exception as exc:  # noqa: BLE001
            tables.append(f"{asset}: {str(exc).strip().splitlines()[0][:100]}")
            continue
        success, detail = run_validation(validation, frame)
        if not success:
            tables.append(f"{asset}: {detail}" if detail else asset)
    return {
        "name": "gx master",
        "layer": "master",
        "success": not tables,
        "seconds": round(time.time() - started, 1),
        "detail": "" if not tables else f"failed tables: {', '.join(tables)}"[:200],
    }


# runs every layer checkpoint in pipeline order plus master
def run_all(include_master: bool = True) -> list[dict]:
    from scripts.setup_gx_project import LAYERS

    context = gx.get_context(mode="file", project_root_dir=str(PROJECT_DIR))
    specs = load_specs()
    results = [run_layer(context, layer, specs) for layer in LAYERS]
    if include_master:
        results.append(run_master(context, specs))
    return results


# entry point used by CI and the final pytest gate
def main() -> int:
    results = run_all()
    failed = [item["name"] for item in results if not item["success"]]
    for item in results:
        status = "PASS" if item["success"] else "FAIL"
        print(f"{status} {item['name']} ({item['seconds']}s) {item['detail']}")
    passed = len(results) - len(failed)
    print(f"gx layers: {passed}/{len(results)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
