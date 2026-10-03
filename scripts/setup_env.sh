#!/usr/bin/env bash
# Validates the monitoring environment: interpreter, venv, env file, database.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/Scripts/python.exe}"
FAILURES=0

# records one setup check for the final summary
report() {
    local name="$1" status="$2" detail="${3:-}"
    if [ "$status" = "ok" ]; then
        echo "PASS $name $detail"
    else
        echo "FAIL $name $detail"
        FAILURES=$((FAILURES + 1))
    fi
}

# ensures a usable python interpreter exists
check_python() {
    local version
    if command -v "$PYTHON" >/dev/null 2>&1; then
        version="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        report "python available" ok "$version"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON="python3"
        report "python available" ok "system python3 (venv missing)"
    else
        report "python available" fail "no interpreter found"
    fi
}

# ensures project dependencies are installed
check_dependencies() {
    if "$PYTHON" -c "import psycopg, pandas, great_expectations" >/dev/null 2>&1; then
        report "dependencies installed" ok "psycopg pandas gx"
    else
        report "dependencies installed" fail "run: uv sync"
    fi
}

# ensures an .env file exists without overwriting a real one
check_env_file() {
    if [ -f "$ROOT/.env" ]; then
        report ".env present" ok
    elif [ -f "$ROOT/.env.example" ]; then
        cp "$ROOT/.env.example" "$ROOT/.env"
        report ".env present" ok "created from .env.example (edit secrets)"
    else
        report ".env present" fail "no .env or .env.example"
    fi
}

# ensures required postgres settings are defined
check_env_vars() {
    local missing=""
    local var
    for var in POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
        if [ -z "${!var:-}" ]; then
            if [ -f "$ROOT/.env" ] && grep -qE "^${var}=.+" "$ROOT/.env"; then
                continue
            fi
            missing="$missing $var"
        fi
    done
    if [ -z "$missing" ]; then
        report "env vars set" ok "POSTGRES_*"
    else
        report "env vars set" fail "missing:$missing"
    fi
}

# ensures the database answers before monitors run
check_database() {
    if "$PYTHON" -c "
import sys
sys.path.insert(0, '$ROOT')
from src.utils.connection import get_postgres_connection, close_connection
close_connection(get_postgres_connection())
" >/dev/null 2>&1; then
        report "database reachable" ok
    else
        report "database reachable" fail "check POSTGRES_* and server"
    fi
}

check_python
check_dependencies
check_env_file
check_env_vars
check_database

if [ "$FAILURES" -gt 0 ]; then
    echo "setup_env: $FAILURES failing check(s)"
    exit 1
fi
echo "setup_env: environment ready"
