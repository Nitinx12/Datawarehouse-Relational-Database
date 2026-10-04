# Changelog

All notable changes to this project use [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- WP1 traceability: one `run_id` per DAG run via `WAREHOUSE_RUN_ID` env set
  from Airflow `{{ run_id }}` with fallback to `AIRFLOW_CTX_DAG_RUN_ID`.
- WP1 row counts: `run_load` now propagates staged/inserted/updated/skipped
  and `parse_notice` covers warehouse combined/reloaded and analytics
  upsert notices, so `rows_in`/`rows_out` are real.
- Verified 2026-10-04 against Docker Postgres (`wp1_docker_verify`):
  one `run_id` across 8 stages, staging 37/37, warehouse 79279/60398,
  analytics 38/38, before/after totals identical (18484/397/60398/38).

### Added

- CI pipeline (ruff, SQLFluff, unit tests, compose validation).
- CD pipeline publishing airflow and dashboard images to GHCR.
- Docker build validation, CodeQL, commitlint, and labeler workflows.

## [0.1.0] - 2026-10-04

### Added

- End-to-end warehouse pipeline: MongoDB + Databricks extracts, staging,
  warehouse, and analytics layers orchestrated by Airflow (`warehouse_daily`).
- Postgres stored procedures with DQ SQL checks and Great Expectations gates.
- Streamlit dashboard over `analytics.report_*` marts.
- Prometheus + Grafana observability stack.
