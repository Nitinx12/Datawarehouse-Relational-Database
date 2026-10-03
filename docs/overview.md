# Warehouse — Current Stage

Last updated: 2026-10-03. End-to-end pipeline is built from extract to
master gate, runnable locally (`main.py`) and on schedule (Airflow DAG
`warehouse_daily`, Mon–Fri 11:00 Asia/Kolkata).

## What exists today

- Full pipeline in `main.py` with 9 stages: `extract`, `source-tests`,
  `staging`, `staging-tests`, `warehouse`, `warehouse-tests`,
  `analytics`, `analytics-tests`, `master`.
- Two Spark extract jobs: MongoDB (`erp_source`) and Databricks
  (`crm_source`) into Postgres schema `source`.
- SQL load procedures: 6 staging, 3 warehouse
  (`dim_customers`, `dim_products`, `fact_sales`), 1 analytics
  (`monthly_kpi_snapshot`).
- Two-level quality gates per layer: SQL DQ checks
  (`tests/data_quality/<layer>/*.sql`) then Great Expectations
  checkpoints, plus a GX master gate.
- Airflow DAG with parallel extracts, per-stage retries (quality-gate
  stages use `retries=0`), failure emails, and an always-run summary
  email with row counts and task breakdown.
- Docker stack: `postgres:17`, `mongo:7`, separate Airflow metadata DB,
  Airflow scheduler + webserver (Airflow 2.10.5, Java 17, Spark 3.5.3,
  `uv`), Streamlit dashboard on Postgres analytics layer.
- Logging: every script logs to console and `logs/warehouse.log`
  (10 MB rotation, 5 backups) via `src/utils/logger.py`; Airflow task
  logs persist in `airflow/logs/`.
- CI: ruff lint/format, SQLFluff, unit tests on push; gitleaks secret
  scan on push/PR.

## Data flow

```
MongoDB (erp_source) ──┐
                       ├─► source ─► staging ─► warehouse ─► analytics
Databricks (crm_source)┘    │           │            │             │
                         DQ+GX       DQ+GX        DQ+GX         DQ+GX
                                                              master gate
```

Schemas in Postgres `datawarehouse` DB: `source`, `staging`,
`warehouse`, `analytics` (created by `sql/00_init_schema.sql`).

## Current gaps / next steps

- Stack is configured and `docker compose config` passes, but no
  containers were running at last check — bring up with
  `docker compose up -d --build` (or `Batchfile infra-up`).
- `.env` holds real secrets and is gitignored; new clones start from
  `.env.example` and must fill in `change_me` values.
- `notebooks/*_eda.ipynb` and `monitor/*.sh` are exploratory/ops
  helpers, not wired into the pipeline.
