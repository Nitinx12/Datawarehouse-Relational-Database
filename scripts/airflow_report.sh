#!/usr/bin/env bash
# Prints a master report of the Airflow pipeline: services, latest DAG runs, task states, DB stage summary.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/Scripts/python.exe}"
DAG="${DAG:-warehouse_daily}"
LIMIT="${LIMIT:-5}"

# prints usage for the airflow report
usage() {
    echo "Usage: airflow_report.sh [--dag ID] [--limit N] [--python PATH]"
    echo "  --dag ID    DAG to inspect (default warehouse_daily)"
    echo "  --limit N   latest runs to show (default 5)"
    echo "  --python P  venv python for DB queries"
}

# parses CLI flags for the airflow report
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --dag) DAG="$2"; shift 2 ;;
            --limit) LIMIT="$2"; shift 2 ;;
            --python) PYTHON="$2"; shift 2 ;;
            -h|--help) usage; exit 0 ;;
            *) echo "unknown flag: $1"; usage; exit 2 ;;
        esac
    done
}

# runs an airflow CLI command inside the scheduler container
airflow_cli() {
    docker compose exec -T airflow-scheduler airflow "$@"
}

# reports whether the scheduler container is running
scheduler_running() {
    local cid
    cid="$(docker compose ps -q airflow-scheduler 2>/dev/null || true)"
    [ -n "$cid" ] && [ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null || echo false)" = "true" ]
}

# prints scheduler and webserver container state
section_services() {
    echo "=== services ==="
    if ! docker compose ps airflow-scheduler airflow-webserver 2>/dev/null; then
        echo "compose stack unreachable (docker down or wrong directory)"
        return 1
    fi
}

# prints the latest DAG runs as a compact table
section_dag_runs() {
    echo "=== latest $LIMIT runs of $DAG ==="
    local raw
    raw="$(airflow_cli dags list-runs -d "$DAG" --limit "$LIMIT" -o json 2>/dev/null || true)"
    if [ -z "$raw" ] || ! PYTHON_JSON="$raw" "$PYTHON" -c "import json,os; json.loads(os.environ['PYTHON_JSON'])" 2>/dev/null; then
        airflow_cli dags list-runs -d "$DAG" --limit "$LIMIT" 2>/dev/null || echo "could not list runs (scheduler warming up or DAG paused)"
        return 0
    fi
    PYTHON_JSON="$raw" "$PYTHON" -c "
import json, os
for row in json.loads(os.environ['PYTHON_JSON']):
    rid = row.get('run_id') or row.get('dag_run_id') or row.get('execution_date')
    print(f\"{rid}  state={row.get('state')}  start={row.get('start_date')}  end={row.get('end_date')}\")
"
}

# extracts the latest run id from list-runs json
latest_run_id() {
    local raw="$1"
    PYTHON_JSON="$raw" "$PYTHON" -c "
import json, os
rows = json.loads(os.environ['PYTHON_JSON'])
row = rows[0] if rows else {}
print(row.get('run_id') or row.get('dag_run_id') or '')
"
}

# prints per-task states for one dag run
section_task_states() {
    local run_id="$1"
    echo "=== task states for $run_id ==="
    local raw
    raw="$(airflow_cli tasks states-for-dag-run "$DAG" --run-id "$run_id" -o json 2>/dev/null || true)"
    if [ -z "$raw" ]; then
        echo "could not fetch task states"
        return 0
    fi
    PYTHON_JSON="$raw" "$PYTHON" -c "
import json, os
data = json.loads(os.environ['PYTHON_JSON'])
pairs = data.items() if isinstance(data, dict) else ((r.get('task_id'), r.get('state')) for r in data)
for task, state in pairs:
    print(f'{task}: {state}')
"
}

# prints the latest pipeline run per stage from postgres
section_db_summary() {
    echo "=== pipeline stages in postgres (ops.pipeline_run_log) ==="
    if ! "$PYTHON" -c "
import sys
sys.path.insert(0, '$ROOT')
from src.utils.connection import get_postgres_connection, close_connection
close_connection(get_postgres_connection())
" >/dev/null 2>&1; then
        echo "postgres unreachable, skipping DB summary"
        return 0
    fi
    "$PYTHON" -c "
import sys
sys.path.insert(0, '$ROOT')
from src.utils.engine import read_postgres
latest = read_postgres('SELECT run_id FROM ops.pipeline_run_log ORDER BY started_at DESC LIMIT 1')
if latest.empty:
    print('no pipeline runs logged yet')
    sys.exit()
run_id = latest.iloc[0, 0]
print(f'run_id={run_id}')
rows = read_postgres(
    f\"SELECT stage, status, duration_s, rows_in, rows_out, rows_rejected \"  # noqa: S608
    f\"FROM ops.pipeline_run_log WHERE run_id = '{run_id}' ORDER BY started_at\"
)
print(rows.to_string(index=False))
" 2>/dev/null
}

parse_args "$@"
cd "$ROOT" || exit 1

section_services || echo "services: stack not running"
echo ""
if scheduler_running; then
    section_dag_runs
    echo ""
    raw_runs="$(airflow_cli dags list-runs -d "$DAG" --limit 1 -o json 2>/dev/null || true)"
    latest="$(latest_run_id "$raw_runs")"
    if [ -n "$latest" ]; then
        section_task_states "$latest"
    else
        echo "no DAG runs found yet"
    fi
else
    echo "scheduler not running, skipping DAG run detail (start with: docker compose up -d)"
fi
echo ""
section_db_summary
