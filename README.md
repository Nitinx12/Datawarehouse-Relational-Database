# Datawarehouse

Retail data warehouse ETL: lands MongoDB + Databricks sources in Postgres,
cleanses through staging, models warehouse dims/fact, and serves analytics
marts to a Streamlit dashboard. One pipeline, one scheduler, four data layers.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the system map and
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) to deploy the full stack.

## Quickstart

```powershell
uv sync --group dev --frozen
Copy-Item .env.example .env   # then fill in secrets
docker compose up -d --build
python main.py                # full extract-to-master run
```

Helpers: `Batchfile.bat help` on Windows, `make help` with make installed.

## Pipeline stages

| Stage | What runs |
| ----- | --------- |
| `extract` | Spark jobs (`mongo_to_postgres`, `databricks_to_postgres`) into `source` |
| `source-tests` | DQ SQL checks, then GX gate |
| `staging` | `staging.*` stored procedures |
| `staging-tests` | DQ SQL checks, then GX gate |
| `warehouse` | `warehouse.*` stored procedures (2 dims + 1 fact) |
| `warehouse-tests` | DQ SQL checks, then GX gate |
| `analytics` | Monthly KPI snapshot procedure |
| `analytics-tests` | DQ SQL checks, then GX gate |
| `master` | GX master gate over every table |

Run one stage: `python main.py --only staging`. Skip stages: `python main.py --skip extract`.

## Quality gates

Every layer runs SQL checks first, then Great Expectations; DQ failure skips GX
for that layer. Details in [docs/TESTING.md](docs/TESTING.md).

## Observability

- `python scripts/run_all_tests.py` — unit + smoke + DQ + GX suites
- `bash scripts/pipeline_health.sh` — reachability, rowcounts, freshness, ETL logs
- `bash scripts/airflow_report.sh` — Airflow services, DAG runs, task states
- `bash scripts/docker_report.sh` — container states, resources, errors, disk
- Grafana (`:3000`) over Prometheus (`:9090`) plus Postgres-backed alerts

## Docs

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — environment setup and stack deployment
- [docs/AIRFLOW.md](docs/AIRFLOW.md) — DAG, schedule, and alerting
- [docs/RUNBOOK.md](docs/RUNBOOK.md) — recovery and on-call steps
- [docs/monitoring.md](docs/monitoring.md) — metrics, dashboards, and alerts
- [docs/TESTING.md](docs/TESTING.md) — test tiers and quality gates
- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, checks, and commit conventions
- [dashboard/README.md](dashboard/README.md) — dashboard pages and local run
