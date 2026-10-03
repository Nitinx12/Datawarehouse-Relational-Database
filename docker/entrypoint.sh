#!/usr/bin/env bash
# One-shot Airflow bootstrap: migrate the metadata DB, ensure the admin user.
set -euo pipefail

airflow db migrate

if [ "${_AIRFLOW_WWW_USER_CREATE:-true}" = "true" ]; then
    airflow users create \
        --username "${_AIRFLOW_WWW_USER_USERNAME:-admin}" \
        --password "${_AIRFLOW_WWW_USER_PASSWORD:?set _AIRFLOW_WWW_USER_PASSWORD in .env}" \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com || true
fi
