# Changelog

All notable changes to this project use [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
