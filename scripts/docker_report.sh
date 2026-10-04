#!/usr/bin/env bash
# Prints a master report of the compose stack: service states, resources, recent errors, disk usage.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAIL="${TAIL:-200}"
ERRORS="${ERRORS:-30}"

# prints usage for the docker report
usage() {
    echo "Usage: docker_report.sh [--tail N] [--errors N]"
    echo "  --tail N    log lines scanned per stack (default 200)"
    echo "  --errors N  error lines shown (default 30)"
}

# parses CLI flags for the docker report
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --tail) TAIL="$2"; shift 2 ;;
            --errors) ERRORS="$2"; shift 2 ;;
            -h|--help) usage; exit 0 ;;
            *) echo "unknown flag: $1"; usage; exit 2 ;;
        esac
    done
}

# prints one line per stack container with state and health
section_services() {
    echo "=== services ==="
    docker compose ps --format "table {{.Service}}\t{{.State}}\t{{.Health}}" 2>/dev/null || echo "compose stack unreachable (docker down or wrong directory)"
}

# highlights containers that are down, unhealthy, or restarting often
section_problems() {
    echo "=== problems (down / unhealthy / restarts) ==="
    local ids
    ids="$(docker compose ps -q 2>/dev/null || true)"
    if [ -z "$ids" ]; then
        echo "stack is down (start with: docker compose up -d --build)"
        return 0
    fi
    # shellcheck disable=SC2086
    docker inspect -f '{{.Name}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}} restarts={{.RestartCount}}' $ids
}

# prints CPU, memory, and network usage per stack container
section_resources() {
    echo "=== resources ==="
    local ids
    ids="$(docker compose ps -q 2>/dev/null || true)"
    if [ -z "$ids" ]; then
        echo "stack is down, nothing to measure"
        return 0
    fi
    # shellcheck disable=SC2086
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $ids 2>/dev/null || echo "stats unavailable"
}

# prints recent error lines from the whole stack
section_errors() {
    echo "=== recent errors (last $TAIL log lines) ==="
    docker compose logs --no-color --tail="$TAIL" 2>/dev/null | grep -aiE 'error|exception|traceback|failed|fatal|killed' | tail -"$ERRORS" || true
}

# prints docker disk usage
section_disk() {
    echo "=== disk ==="
    docker system df 2>/dev/null || echo "docker unreachable"
}

parse_args "$@"
cd "$ROOT" || exit 1

section_services
echo ""
section_problems
echo ""
section_resources
echo ""
section_errors
echo ""
section_disk
