#!/usr/bin/env bash
# Audits secret hygiene: env files, tracked secrets, hardcoded credentials.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILURES=0

# records one audit result for the final summary
report() {
    local name="$1" status="$2" detail="${3:-}"
    if [ "$status" = "ok" ]; then
        echo "PASS $name $detail"
    else
        echo "FAIL $name $detail"
        FAILURES=$((FAILURES + 1))
    fi
}

# ensures the real .env file is never tracked by git
check_env_untracked() {
    if git -C "$ROOT" ls-files --error-unmatch .env >/dev/null 2>&1; then
        report ".env untracked" fail ".env is committed"
    else
        report ".env untracked" ok
    fi
}

# ensures no secret file ever entered git history
check_history_clean() {
    local hits
    hits="$(git -C "$ROOT" log --all --oneline -- .env | wc -l)"
    if [ "$hits" -eq 0 ]; then
        report "git history clean" ok "no .env commits"
    else
        report "git history clean" fail "$hits commit(s) touch .env"
    fi
}

# ensures no hardcoded secrets sit in tracked source files
check_no_hardcoded_secrets() {
    local hits
    hits="$(git -C "$ROOT" grep -n -i -E '(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*["'\''][^"'\'']+["'\'']' -- . ':!.env.example' ':!*.md' 2>/dev/null | grep -v -i -E '(example|placeholder|changeme|xxx|test|dummy|password=("|'"'"'))' || true)"
    if [ -z "$hits" ]; then
        report "no hardcoded secrets" ok
    else
        report "no hardcoded secrets" fail "$(echo "$hits" | wc -l) suspect line(s)"
        echo "$hits"
    fi
}

# warns when the configured postgres password is missing or default
check_password_strength() {
    local password="${POSTGRES_PASSWORD:-}"
    if [ -z "$password" ] && [ -f "$ROOT/.env" ]; then
        password="$(grep -E '^POSTGRES_PASSWORD=' "$ROOT/.env" | cut -d= -f2- || true)"
    fi
    if [ -z "$password" ]; then
        report "postgres password set" fail "empty or missing"
    elif [ "$password" = "postgres" ] || [ "$password" = "password" ]; then
        report "postgres password set" fail "default value in use"
    else
        report "postgres password set" ok
    fi
}

check_env_untracked
check_history_clean
check_no_hardcoded_secrets
check_password_strength

if [ "$FAILURES" -gt 0 ]; then
    echo "pipeline_security: $FAILURES failing check(s)"
    exit 1
fi
echo "pipeline_security: all checks passed"
