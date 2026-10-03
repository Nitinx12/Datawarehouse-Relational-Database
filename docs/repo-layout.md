# Repo Layout

```
datawarehouse/
├── main.py                     pipeline runner: extract → master, --only/--skip
├── airflow/
│   ├── dags/warehouse_daily.py daily DAG (Mon–Fri 11:00 Asia/Kolkata)
│   ├── Dockerfile.airflow      Airflow 2.10.5 + Java 17 + Spark 3.5.3 + uv
│   ├── requirements.txt        container Python deps (+ postgres provider)
│   ├── plugins/                Airflow plugins dir (mounted, empty)
│   └── logs/                   task logs (bind mount target, gitignored)
├── scripts/                    runnable entry points (see operations.md)
│   ├── _submit.py              spark-submit wrapper (Mongo/Databricks jobs)
│   ├── check_sources.py        preflight reachability checks
│   ├── run_mongo_job.py / run_databricks_job.py
│   ├── run_staging_load.py     also provides call_procedure()
│   ├── run_warehouse_load.py
│   ├── run_dq_checks.py / run_all_tests.py
│   └── run_gx_validations.py / setup_gx_project.py
├── src/
│   ├── jobs/
│   │   ├── mongo_to_postgres.py / databricks_to_postgres.py
│   │   ├── _report.py          end-of-run summary (logger-backed)
│   │   └── proc_*.sql          staging + warehouse load procedures
│   └── utils/
│       ├── connection.py       Postgres / Mongo / Databricks connectors
│       ├── engine.py           SQL read helpers
│       ├── session.py          Spark session builder
│       └── logger.py           console + rotating file logging
├── sql/
│   ├── 00_init_schema.sql      schemas (mounted into postgres initdb)
│   ├── 01_source_etl_logs.sql  ETL log tables
│   ├── analytics/              analysis, exploration, materialized_views,
│   │                           reporting_tables, views
│   └── metadata/               database_metadata.sql, sequence.sql
├── tests/
│   ├── unit/                   test_databricks_helpers, test_mongo_helpers,
│   │                           test_report, test_staging_runner, test_submit
│   ├── smoke/test_services.py  service reachability
│   ├── data_quality/           source|staging|warehouse|analytics SQL checks
│   └── gx/                     per-layer + master + pipeline-complete tests
├── gx/                         GX project: checkpoints, expectations,
│                               validation_definitions, great_expectations.yml
├── dashboard/                  Streamlit app (home.py, pages/, lib/),
│                               Dockerfile, requirements.txt
├── docker/
│   └── entrypoint.sh           airflow-init: db migrate + admin user
├── docker-compose.yml          postgres + mongo + airflow + dashboard stack
├── docs/                       this documentation
├── monitor/                    pipeline_health.sh, pipeline_security.sh,
│                               setup_env.sh (ops helpers)
├── notebooks/                  source/staging/warehouse EDA notebooks
├── jars/                       Spark jars: mongo connector 10.5.0, bson,
│                               mongodb drivers, databricks-jdbc, postgresql
├── .env / .env.example         secrets (gitignored) + committed template
├── .github/workflows/          ci.yml (ruff/sqlfluff/pytest), leaks.yml
├── Makefile / Batchfile.bat    Linux / Windows task runners (same targets)
├── pyproject.toml              uv project `lrdb`, py>=3.11, dev group
│                               (pytest, ruff, sqlfluff)
├── uv.lock / .python-version   locked deps, Python 3.11
├── AGENTS.md                   repo conventions (comments, ruff, pyspark,
│                               sqlfluff rules)
└── logs/ / airflow/logs/       runtime logs (created on demand, gitignored)
```

## Conventions (from AGENTS.md)

- One short comment above each function/class/SQL model; no comments
  inside bodies; no long docstrings.
- Python: `ruff` format+lint before commit, type-hint every signature,
  pure DataFrame-in/DataFrame-out transforms, broadcast small joins,
  partitioned Delta writes, never `.collect()` large frames.
- SQL: `::VARCHAR` casts, UPPERCASE keywords, 4-space indent, one
  column per line, explicit joins/aliases, layout per
  `src/jobs/proc_staging_cust_info.sql`.
- Commits follow Conventional Commits (`.commitlintrc.json`).
