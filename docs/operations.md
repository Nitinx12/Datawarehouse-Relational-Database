# Operations — Scripts, Docker, Airflow, Makefile, CI

## Scripts (`scripts/`)

Entry points used by `main.py`, the DAG, and developers directly.

| Script | Role |
|---|---|
| `check_sources.py` | Preflight: pings Postgres, Mongo, Databricks; exit 2 on failure |
| `run_mongo_job.py` | Submits `src/jobs/mongo_to_postgres.py` via `_submit` with Mongo + Postgres jars |
| `run_databricks_job.py` | Submits `src/jobs/databricks_to_postgres.py` with Postgres jar |
| `_submit.py` | Shared spark-submit wrapper: resolves `jars/`, sets `PYSPARK_PYTHON`, filters Spark stderr noise, logs start/exit code |
| `run_staging_load.py` | Calls `staging.*` procedures in order; exposes `call_procedure()` reused by warehouse loader and `main.py` |
| `run_warehouse_load.py` | Calls `warehouse.*` procedures via the shared `call_procedure()` |
| `run_dq_checks.py` | Runs `tests/data_quality/<layer>/*.sql` for one `--layer` |
| `run_gx_validations.py` | Runs GX layer checkpoints + master gate over fresh frames |
| `run_all_tests.py` | Full suite: pytest unit/smoke, SQL DQ loops, GX layers |
| `setup_gx_project.py` | One-shot rebuild of the GX project (validations, checkpoints) from specs |

`src/jobs/` holds the Spark jobs plus the `proc_*.sql` procedure
definitions they load; `src/utils/` holds `connection.py` (Postgres /
Mongo / Databricks connectors), `engine.py`, `session.py` (Spark
session), `logger.py` (console + rotating file logging).

## Docker (`docker-compose.yml`, `airflow/Dockerfile.airflow`)

Services: `postgres` (16, warehouse DB + init scripts), `mongo` (7),
`airflow-metadata` (separate Postgres for Airflow), `airflow-init`
(one-shot DB migrate + admin user via `docker/entrypoint.sh`),
`airflow-scheduler`, `airflow-webserver` (:8080), `dashboard` (:8501).

- Airflow image: `apache/airflow:2.10.5-python3.11` + OpenJDK 17,
  Spark 3.5.3, `uv`, `airflow/requirements.txt`.
- Containers talk over service names (`postgres`, `mongo`,
  `airflow-metadata`); compose overrides `POSTGRES_HOST`, `MONGO_HOST`,
  `MONGO_URL` accordingly. Local runs use `localhost` from `.env`.
- Code is bind-mounted (`./:/opt/warehouse`,
  `./airflow/dags:/opt/airflow/dags`), so DAG edits need no rebuild;
  dependency changes do.
- Key env: `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` (metadata DB),
  `AIRFLOW_CONN_WAREHOUSE_POSTGRES` (auto-creates the
  `warehouse_postgres` connection for summary emails), `ALERT_EMAILS`,
  `LOG_DIR=logs`, SMTP settings for alerts.

## Airflow (`airflow/dags/warehouse_daily.py`)

- Schedule `0 11 * * 1-5`, `max_active_runs=1`, 6h `dagrun_timeout`.
- Chain: `preflight` → `extract` group (`extract_mongo`,
  `extract_databricks` in parallel) → `source-tests` → `staging` →
  … → `master` → `summary_email` (trigger rule `ALL_DONE`, wired to
  every upstream stage so it reports even on failure).
- Every task runs `uv run` from `/opt/warehouse`; retries 2 with
  exponential backoff, except DQ/master gates (`retries=0` — a failed
  check won't self-heal).
- `notify_failure` emails on task failure; `send_summary` emails the
  run report with warehouse row counts, then raises to keep failed
  runs red.

## Makefile / Batchfile.bat

Same targets on Linux (`make <t>`) and Windows (`Batchfile <t>`):
per-stage runs (`extract`, `staging`, `warehouse`, … map to
`main.py --only`), `pipeline`, `no-extract`, `test`, `gx`, `gx-build`,
`lint`/`format` (ruff), `dashboard`/`dashboard-install`,
`infra-up`/`infra-down`/`infra-logs`, `airflow-trigger`.

## GitHub Actions (`.github/workflows/`)

- `ci.yml` (on push): `uv sync`, ruff check + format check on
  `src/ scripts/ tests/`, SQLFluff lint on `sql/ src/jobs/ tests/`,
  `pytest tests/unit`.
- `leaks.yml` (push/PR/manual): gitleaks secret scan over full
  history. `.env` is gitignored; only `.env.example` is committed.

## Logging

- App code: `get_logger(__name__)` → console + `logs/warehouse.log`
  (rotating, 10 MB × 5). Falls back to console if the log dir is not
  writable. Level via `LOG_LEVEL`, dir via `LOG_DIR`.
- Airflow task logs: `/opt/airflow/logs` in containers, bound to
  `airflow/logs/` on the host; base folder pinned via
  `AIRFLOW__LOGGING__BASE_LOG_FOLDER`.
- Follow live stack output with `docker compose logs -f`
  (`Batchfile infra-logs`).
