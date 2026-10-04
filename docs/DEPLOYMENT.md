# Deployment

Deploys the full stack: Postgres, MongoDB, Airflow, Streamlit dashboard,
Prometheus, and Grafana via `docker-compose.yml`.

## Prerequisites

- Docker Engine 24+ with Compose v2.
- 8 GB RAM free (two Spark JVMs run sequentially to fit Docker memory).
- A copy of `.env` with real secrets (never commit it).

## 1. Configure environment

```powershell
Copy-Item .env.example .env
```

Set at minimum: `POSTGRES_PASSWORD`, `AIRFLOW_DB_PASSWORD`,
`AIRFLOW__CORE__FERNET_KEY`, `AIRFLOW__WEBSERVER__SECRET_KEY`,
`_AIRFLOW_WWW_USER_PASSWORD`, `ALERT_EMAILS`, `DATABRICKS_HOST`,
`DATABRICKS_TOKEN`, and the Grafana/SMTP passwords.
Generate the Fernet key with:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 2. Start the stack

```powershell
docker compose up -d --build
docker compose logs -f
```

Services: Airflow webserver on `:8080`, dashboard on `:8501`,
Prometheus on `127.0.0.1:9090`, Grafana on `127.0.0.1:3000`.
Schema seed files in `sql/` run automatically on first Postgres start.

## 3. Run the pipeline

Airflow DAG `warehouse_daily` runs weekdays at 11:00 Asia/Kolkata.
To trigger once manually:

```powershell
docker compose exec airflow-scheduler airflow dags trigger warehouse_daily
```

Or run stages locally without containers:

```powershell
uv sync --group dev --frozen
python main.py
python main.py --only staging
python scripts/run_all_tests.py
```

## 4. Verify

- `docker compose ps` shows all services healthy.
- `python scripts/check_sources.py` passes preflight.
- Grafana `pipeline-overview` dashboard shows fresh `ops.pipeline_run_log` rows.
- `python scripts/pipeline_health.sh` reports no failed stages.

## 5. Stop

```powershell
docker compose down      # keeps volumes
docker compose down -v   # also drops Postgres/Mongo data
```
