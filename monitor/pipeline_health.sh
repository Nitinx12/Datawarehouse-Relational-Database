#!/usr/bin/env bash
# Monitors pipeline health: reachability, rowcounts, freshness, ETL log failures.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/Scripts/python.exe}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-48}"
RUN_GX=0
FAILURES=0

# prints usage for the health monitor
usage() {
    echo "Usage: pipeline_health.sh [--gx] [--max-age-hours N] [--python PATH]"
    echo "  --gx               also run the GX layer and master gates"
    echo "  --max-age-hours N  freshness SLA in hours (default 48)"
}

# parses CLI flags for the health monitor
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --gx) RUN_GX=1; shift ;;
            --max-age-hours) MAX_AGE_HOURS="$2"; shift 2 ;;
            --python) PYTHON="$2"; shift 2 ;;
            -h|--help) usage; exit 0 ;;
            *) echo "unknown flag: $1"; usage; exit 2 ;;
        esac
    done
}

# records one check result for the final summary
report() {
    local name="$1" status="$2" detail="${3:-}"
    if [ "$status" = "ok" ]; then
        echo "PASS $name $detail"
    else
        echo "FAIL $name $detail"
        FAILURES=$((FAILURES + 1))
    fi
}

# checks postgres accepts connections
check_postgres() {
    if "$PYTHON" -c "
import os, sys
sys.path.insert(0, '$ROOT')
from src.utils.connection import get_postgres_connection, close_connection
conn = get_postgres_connection()
close_connection(conn)
" >/dev/null 2>&1; then
        report "postgres reachable" ok
    else
        report "postgres reachable" fail "connection refused"
    fi
}

# runs one SQL query and prints the first value
query_one() {
    "$PYTHON" -c "
import sys
sys.path.insert(0, '$ROOT')
from src.utils.engine import read_postgres
print(read_postgres('''$1''').iloc[0, 0])
" 2>/dev/null
}

# fails when any pipeline table is empty
check_rowcounts() {
    local tables=(
        'source."CUST_AZ12"' 'source."LOC_A101"' 'source."PX_CAT_G1V2"'
        "source.cust_info" "source.prd_info" "source.sales_details"
        "staging.cust_az12" "staging.cust_info" "staging.loc_a101"
        "staging.prd_info" "staging.px_cat_g1v2" "staging.sales_details"
        "warehouse.dim_customers" "warehouse.dim_products" "warehouse.fact_sales"
    )
    local empty=""
    local count
    for table in "${tables[@]}"; do
        count="$(query_one "SELECT COUNT(*) FROM $table" || echo ERROR)"
        if [ "$count" = "0" ] || [ "$count" = "ERROR" ]; then
            empty="$empty $table($count)"
        fi
    done
    if [ -z "$empty" ]; then
        report "rowcounts non-empty" ok "${#tables[@]} tables"
    else
        report "rowcounts non-empty" fail "empty:$empty"
    fi
}

# fails when any layer watermark is older than the SLA
check_freshness() {
    local watermarks=(
        "source.cust_info|_loaded_at"
        "staging.sales_details|loaded_at"
        "warehouse.dim_customers|updated_at"
        "analytics.monthly_kpi_snapshot|loaded_at"
    )
    local stale=""
    local entry table column age
    for entry in "${watermarks[@]}"; do
        table="${entry%%|*}"
        column="${entry##*|}"
        age="$(query_one "SELECT EXTRACT(EPOCH FROM (NOW() - MAX($column))) / 3600 FROM $table" || echo ERROR)"
        if [ "$age" = "ERROR" ] || [ "${age%%.*}" -ge "$MAX_AGE_HOURS" ] 2>/dev/null; then
            stale="$stale $table(${age}h)"
        fi
    done
    if [ -z "$stale" ]; then
        report "freshness within ${MAX_AGE_HOURS}h" ok
    else
        report "freshness within ${MAX_AGE_HOURS}h" fail "stale:$stale"
    fi
}

# fails when recent ETL runs did not succeed
check_etl_logs() {
    local failed
    failed="$(query_one "SELECT COUNT(*) FROM source.etl_logs WHERE started_at > NOW() - INTERVAL '7 days' AND status NOT IN ('SUCCESS', 'COMPLETED', 'SKIPPED')" || echo ERROR)"
    if [ "$failed" = "0" ]; then
        report "etl_logs clean (7d)" ok
    else
        report "etl_logs clean (7d)" fail "failures=$failed"
    fi
}

# runs the GX layer and master gates
check_gx() {
    if [ "$RUN_GX" = "1" ]; then
        if "$PYTHON" "$ROOT/scripts/run_gx_validations.py" >/dev/null 2>&1; then
            report "gx gates" ok "all layers + master"
        else
            report "gx gates" fail "see scripts/run_gx_validations.py output"
        fi
    fi
}

parse_args "$@"
check_postgres
check_rowcounts
check_freshness
check_etl_logs
check_gx

if [ "$FAILURES" -gt 0 ]; then
    echo "pipeline_health: $FAILURES failing check(s)"
    exit 1
fi
echo "pipeline_health: all checks passed"
