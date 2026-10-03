#!/usr/bin/env bash
# One-shot Airflow bootstrap: migrate the metadata DB, ensure the admin user.
set -euo pipefail

airflow db migrate

airflow users create \
    --username "${AIRFLOW_ADMIN_USER:-admin}" \
    --password "${AIRFLOW_ADMIN_PASSWORD:-admin}" \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com || true
