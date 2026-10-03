# Pipeline Monitoring Guide

Per-layer monitoring plus Prometheus + Grafana for the `datawarehouse` repo.
Put this file at `docs/monitoring.md`.

---

## 1. Design decisions

The pipeline is a **batch job** (Mon-Fri 11:00 IST), not a long-running service. That shapes the stack:

| Question | Where the answer lives | Tool |
|---|---|---|
| Did the run happen, how long did each stage take, did it fail? | `ops.pipeline_run_log` (Postgres) | Grafana -> Postgres |
| Is each layer's data healthy (counts, rejects, orphans, freshness)? | `ops.table_snapshot` + layer tables | Grafana -> Postgres |
| Are Postgres, Mongo and the Airflow scheduler healthy? | Exporters | Prometheus |
| Who gets told when something is wrong? | One path for everything | Grafana alerting -> email |

Choices made on purpose:
- **No Pushgateway.** Batch state already lives in Postgres, so Grafana reads it directly. One less moving part.
- **No Alertmanager.** Grafana evaluates alerts on both Prometheus and Postgres data and sends the email. One notification path.
- **No cAdvisor / node_exporter.** They are unreliable on Docker Desktop for Windows. Use Postgres/Mongo exporters and Airflow StatsD instead.
- **Keep an external dead man's switch** (healthchecks.io) in addition. If your host or Docker is down, Prometheus and Grafana are down with it, and silence looks like success.

```
main.py / Airflow ──writes──► ops.pipeline_run_log, ops.table_snapshot ──┐
                                                                          ├──► Grafana ──► email
Postgres ─► postgres-exporter ┐                                           │   (dashboards
Mongo ────► mongodb-exporter  ├──► Prometheus ───────────────────────────┘    + alerts)
Airflow ──StatsD──► statsd-exporter ┘
```

---

## 2. Phase 1: record data about every run (do this first)

Dashboards need data. Nothing below works until these tables are filled.

### 2.1 Tables

Follow the repo SQL conventions (UPPERCASE keywords, 4-space indent, one column per line). Save as `sql/02_ops_monitoring.sql` and mount it into postgres initdb, or run it once manually.

```sql
CREATE SCHEMA IF NOT EXISTS ops;

-- one row per stage per run; retries overwrite the same row
CREATE TABLE IF NOT EXISTS ops.pipeline_run_log (
    run_id          VARCHAR NOT NULL,
    stage           VARCHAR NOT NULL,
    status          VARCHAR NOT NULL,
    attempt         INT,
    started_at      TIMESTAMPTZ NOT NULL,
    duration_s      NUMERIC(10, 1),
    rows_in         BIGINT,
    rows_out        BIGINT,
    rows_rejected   BIGINT,
    detail          JSONB,
    PRIMARY KEY (run_id, stage)
);

-- row count of every base table per layer per run
CREATE TABLE IF NOT EXISTS ops.table_snapshot (
    run_id          VARCHAR NOT NULL,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    layer           VARCHAR NOT NULL,
    table_name      VARCHAR NOT NULL,
    row_count       BIGINT NOT NULL,
    PRIMARY KEY (run_id, layer, table_name)
);

-- records row counts for every base table in the four data layers
CREATE OR REPLACE PROCEDURE ops.record_layer_snapshot(p_run_id VARCHAR)
LANGUAGE plpgsql
AS $$
DECLARE
    v_rec RECORD;
    v_count BIGINT;
BEGIN
    FOR v_rec IN
        SELECT
            table_schema,
            table_name
        FROM information_schema.tables
        WHERE table_schema IN ('source', 'staging', 'warehouse', 'analytics')
            AND table_type = 'BASE TABLE'
    LOOP
        EXECUTE FORMAT('SELECT COUNT(*) FROM %I.%I', v_rec.table_schema, v_rec.table_name)
        INTO v_count;

        INSERT INTO ops.table_snapshot (run_id, layer, table_name, row_count)
        VALUES (p_run_id, v_rec.table_schema, v_rec.table_name, v_count)
        ON CONFLICT (run_id, layer, table_name)
        DO UPDATE SET
            row_count = EXCLUDED.row_count,
            captured_at = NOW();
    END LOOP;
END;
$$;
```

`record_layer_snapshot` discovers tables automatically, so new tables are monitored with no list to maintain.

### 2.2 Writing the rows (implemented in `src/utils/tracking.py`)

`src/utils/tracking.py` is the real implementation: `RUN_ID` (from
`AIRFLOW_CTX_DAG_RUN_ID`, timestamp fallback locally), `ATTEMPT` (from
`AIRFLOW_CTX_TRY_NUMBER`), the `track_stage()` context manager
(upserts one row per stage per run, retries overwrite), `stage_metrics()`
(aggregates stage result rows into `rows_in`/`rows_out`/`rows_rejected`
plus `dq_failed`/`gx_failed` in `detail`), and `record_snapshot()`
(calls `ops.record_layer_snapshot`).

Key points:
- Every stage of one DAG run shares one `run_id` via the Airflow
  context vars. Locally, `run_id` falls back to a timestamp.
- `main.py` wraps each stage in `track_stage()` and calls
  `record_snapshot()` after the `extract`, `staging`, `warehouse` and
  `analytics` stages.
- `scripts/run_mongo_job.py` and `scripts/run_databricks_job.py` wrap
  their `submit()` calls in `track_stage("extract_mongo")` /
  `track_stage("extract_databricks")`, so the DAG's direct extract
  tasks are visible in `ops.pipeline_run_log`.
- Run-log and snapshot writes log loudly but never break the pipeline:
  if the `ops` tables are missing, stages still run and the failure is
  in `logs/warehouse.log`.

```python
with track_stage("staging") as m:
    stage_rows = run_stage("staging")
    m.update(stage_metrics("staging", stage_rows))
record_snapshot()
```

---

## 3. Monitoring each layer

Your current baseline from the 2026-10-03 run, useful for sanity-checking thresholds: `dim_customers` 18,484, `dim_products` 397, `fact_sales` 60,398, `staging.cust_info` null-key skipped 4, `monthly_kpi_snapshot` 38 months, every staging load at 0 inserted/updated.

Placeholders like `<date_col>` are column names I cannot see. Fill them in.

### 3.1 Source (`source` schema: Mongo + Databricks extracts)

| Watch | Why | How |
|---|---|---|
| Extract duration per job | A slow extract is the first sign of a source problem | `ops.pipeline_run_log`, stages `extract_mongo`, `extract_databricks` |
| Rows landed per source table | A sudden drop means a broken or partial extract | `ops.table_snapshot`, `layer = 'source'` |
| Source freshness | Extract can succeed on stale data | `SELECT MAX(<updated_col>) FROM source.<table>` |
| Schema drift | Upstream renamed or dropped a column | Compare `information_schema.columns` with the last run |
| Connectivity | Preflight already covers it | `check_sources.py` exit code |

Alert query, source shrink greater than 20% versus the previous run (reuse for any layer by changing `layer`):

```sql
WITH ranked AS (
    SELECT
        table_name,
        row_count,
        LAG(row_count) OVER (PARTITION BY table_name ORDER BY captured_at) AS prev_count,
        ROW_NUMBER() OVER (PARTITION BY table_name ORDER BY captured_at DESC) AS rn
    FROM ops.table_snapshot
    WHERE layer = 'source'
)
SELECT
    COALESCE(MAX((prev_count - row_count)::NUMERIC / NULLIF(prev_count, 0)), 0) AS max_drop_ratio
FROM ranked
WHERE rn = 1;
```

Alert when `max_drop_ratio > 0.2`.

### 3.2 Staging (`staging` schema)

| Watch | Why | How |
|---|---|---|
| staged / inserted / updated per table | Shows whether data is actually moving | `rows_out` on stage `staging` |
| Reject ratio (null-key skipped) | A rising ratio means a bad source or a changed key | `rows_rejected / rows_in` |
| Zero-delta streak | One zero is normal on a quiet day. Three in a row is suspicious | last 3 runs of stage `staging` |
| DQ + GX failures | Gate results over time | `detail->>'dq_failed'`, `detail->>'gx_failed'` |

```sql
-- reject ratio of the latest staging run, alert when > 0.01
SELECT
    rows_rejected::NUMERIC / NULLIF(rows_in, 0) AS reject_ratio
FROM ops.pipeline_run_log
WHERE stage = 'staging'
ORDER BY started_at DESC
LIMIT 1;
```

```sql
-- alert when zero_runs = 3
SELECT
    COUNT(*) AS zero_runs
FROM (
    SELECT rows_out
    FROM ops.pipeline_run_log
    WHERE stage = 'staging'
        AND status = 'SUCCESS'
    ORDER BY started_at DESC
    LIMIT 3
) AS last_three
WHERE rows_out = 0;
```

### 3.3 Warehouse (`warehouse` schema: dims + fact)

| Watch | Why | How |
|---|---|---|
| Dims and fact never shrink | Shrinking means data loss | shrink query from 3.1 with `layer = 'warehouse'`, threshold `> 0` |
| Orphans in `fact_sales` | Broken dimension keys | `detail->>'orphan_products'`, `detail->>'orphan_customers'` must be 0 |
| Reconciliation | Staging sales should equal fact rows (60,398 = 60,398 today) | query below |
| Dim change volume | Sudden mass updates mean a key or SCD problem | `rows_out` for `warehouse` |

```sql
-- alert when staging_rows <> fact_rows (adjust if business rules filter rows)
SELECT
    MAX(row_count) FILTER (WHERE layer = 'staging' AND table_name = 'sales_details') AS staging_rows,
    MAX(row_count) FILTER (WHERE layer = 'warehouse' AND table_name = 'fact_sales') AS fact_rows
FROM ops.table_snapshot
WHERE run_id = (
    SELECT run_id
    FROM ops.pipeline_run_log
    ORDER BY started_at DESC
    LIMIT 1
);
```

```sql
-- alert when orphans > 0
SELECT
    COALESCE((detail ->> 'orphan_products')::INT, 0)
    + COALESCE((detail ->> 'orphan_customers')::INT, 0) AS orphans
FROM ops.pipeline_run_log
WHERE stage = 'warehouse'
ORDER BY started_at DESC
LIMIT 1;
```

### 3.4 Analytics (`monthly_kpi_snapshot`)

| Watch | Why | How |
|---|---|---|
| Latest month present | Stale KPI is the most visible failure to users | `SELECT MAX(<month_col>) FROM analytics.monthly_kpi_snapshot` should be current or previous month |
| Month count never drops | 38 today | shrink query with `layer = 'analytics'` |
| KPI swing | Revenue moving more than X% week over week usually means a data problem | compare latest vs previous value of `<revenue_col>` |
| Null KPIs | Join or calculation broke | `COUNT(*) FILTER (WHERE <kpi_col> IS NULL)` |

### 3.5 Master gate and whole pipeline

| Watch | How |
|---|---|
| Run completed | `ops.pipeline_run_log` stage `master`, status `SUCCESS` |
| Total run duration | sum of stage durations per `run_id` |
| Pipeline overdue (the one alert that catches "it never ran") | query below |

```sql
-- alert when hours_overdue > 0
-- Tue-Fri: run expected within 25h. Weekend/Mon: Friday's run may be 73h old.
SELECT
    EXTRACT(EPOCH FROM (NOW() - MAX(started_at))) / 3600
    - CASE
        WHEN EXTRACT(ISODOW FROM NOW() AT TIME ZONE 'Asia/Kolkata') IN (2, 3, 4, 5) THEN 25
        ELSE 73
    END AS hours_overdue
FROM ops.pipeline_run_log
WHERE stage = 'master'
    AND status = 'SUCCESS';
```

Known limit: public holidays on a weekday will fire this once. Mute it that day.

---

## 4. Phase 2: Prometheus + Grafana stack

### 4.1 Folder layout

```
monitoring/
├── prometheus/prometheus.yml
├── statsd/mapping.yml
└── grafana/
    ├── provisioning/
    │   ├── datasources/datasources.yml
    │   └── dashboards/dashboards.yml
    └── dashboards/            (exported dashboard JSON goes here)
```

### 4.2 Database roles (least privilege)

Two separate roles. Neither should be the warehouse owner.

```sql
-- exporter: metrics only
CREATE ROLE exporter LOGIN PASSWORD 'change_me';
GRANT pg_monitor TO exporter;

-- grafana: read-only on pipeline data
CREATE ROLE grafana_ro LOGIN PASSWORD 'change_me';
GRANT USAGE ON SCHEMA ops, source, staging, warehouse, analytics TO grafana_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA ops, source, staging, warehouse, analytics TO grafana_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA ops, source, staging, warehouse, analytics
    GRANT SELECT ON TABLES TO grafana_ro;
```

Add to `.env.example` (placeholders only, real values in the gitignored `.env`):

```dotenv
EXPORTER_DB_PASSWORD=change_me
GRAFANA_DB_PASSWORD=change_me
GRAFANA_ADMIN_PASSWORD=change_me
```

### 4.3 `docker-compose.yml` additions

Pin versions to the current stable release when you add them. Tags below
verified October 2026 (Prometheus 3.15.0, Grafana 13.2.1,
statsd-exporter 0.31.0, postgres-exporter 0.20.1, mongodb_exporter 0.53.0).

```yaml
  prometheus:
    image: prom/prometheus:v3.15.0
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.retention.time=30d
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "127.0.0.1:9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:13.2.1
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
      GRAFANA_DB_PASSWORD: ${GRAFANA_DB_PASSWORD}
      SMTP_USER: ${SMTP_USER}
      GF_SMTP_ENABLED: "true"
      GF_SMTP_HOST: smtp.gmail.com:587
      GF_SMTP_USER: ${SMTP_USER}
      GF_SMTP_PASSWORD: ${SMTP_PASSWORD}
      GF_SMTP_FROM_ADDRESS: ${SMTP_USER}
      GF_SMTP_STARTTLS_POLICY: MandatoryStartTLS
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      - prometheus
      - postgres
    restart: unless-stopped

  statsd-exporter:
    image: prom/statsd-exporter:v0.31.0
    command: ["--statsd.mapping-config=/etc/statsd/mapping.yml"]
    volumes:
      - ./monitoring/statsd/mapping.yml:/etc/statsd/mapping.yml:ro
    restart: unless-stopped

  postgres-exporter:
    image: quay.io/prometheuscommunity/postgres-exporter:v0.20.1
    environment:
      DATA_SOURCE_NAME: postgresql://exporter:${EXPORTER_DB_PASSWORD}@postgres:5432/datawarehouse?sslmode=disable
    depends_on:
      - postgres
    restart: unless-stopped

  mongodb-exporter:
    image: percona/mongodb_exporter:0.53.0
    command:
      - --mongodb.uri=mongodb://mongo:27017
      - --collect-all
    depends_on:
      - mongo
    restart: unless-stopped
```

At the bottom of the file, add the volumes:

```yaml
volumes:
  prometheus-data:
  grafana-data:
```

If Mongo has auth enabled, put credentials in the URI (from `.env`, not hardcoded).

Point Airflow's StatsD at the exporter by adding to the `airflow-scheduler` service environment:

```yaml
      AIRFLOW__METRICS__STATSD_ON: "True"
      AIRFLOW__METRICS__STATSD_HOST: statsd-exporter
      AIRFLOW__METRICS__STATSD_PORT: "8125"
      AIRFLOW__METRICS__STATSD_PREFIX: airflow
```

Do not bind any of these ports to `0.0.0.0`. Keep `127.0.0.1` unless you put a reverse proxy with auth in front.

### 4.4 `monitoring/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 30s

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]

  - job_name: mongodb
    static_configs:
      - targets: ["mongodb-exporter:9216"]

  - job_name: airflow
    static_configs:
      - targets: ["statsd-exporter:9102"]
```

### 4.5 `monitoring/statsd/mapping.yml`

Keep this minimal. Task-level metrics are deliberately NOT mapped: your task IDs inside TaskGroups contain a dot (`extract.extract_mongo`), which breaks StatsD wildcard matching. Task-level detail comes from `ops.pipeline_run_log` instead.

Operator success/failure counters must use `match_type: regex`: current statsd-exporter versions reject a partial-component glob like `airflow.operator_failures_*` (`invalid match`) and crash-loop.

```yaml
mappings:
  - match: "airflow.dagrun.duration.*.*"
    name: "airflow_dagrun_duration"
    labels:
      status: "$1"
      dag_id: "$2"

  - match: "airflow.dagrun.schedule_delay.*"
    name: "airflow_dagrun_schedule_delay"
    labels:
      dag_id: "$1"

  - match_type: regex
    match: "^airflow\\.operator_failures_(.+)$"
    name: "airflow_operator_failures"
    labels:
      operator: "$1"

  - match_type: regex
    match: "^airflow\\.operator_successes_(.+)$"
    name: "airflow_operator_successes"
    labels:
      operator: "$1"
```

Unmapped metrics such as `airflow_scheduler_heartbeat` and `airflow_dag_processing_import_errors` are still exported with dots turned into underscores.

### 4.6 Grafana provisioning

`monitoring/grafana/provisioning/datasources/datasources.yml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Warehouse
    uid: warehouse
    type: postgres
    access: proxy
    url: postgres:5432
    user: grafana_ro
    secureJsonData:
      password: ${GRAFANA_DB_PASSWORD}
    jsonData:
      database: datawarehouse
      sslmode: disable
      postgresVersion: 1700
```

`monitoring/grafana/provisioning/dashboards/dashboards.yml`:

```yaml
apiVersion: 1
providers:
  - name: warehouse
    folder: Warehouse
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

### 4.7 Start it

```powershell
docker compose up -d prometheus grafana statsd-exporter postgres-exporter mongodb-exporter
docker compose up -d --force-recreate airflow-scheduler
```

Check:
1. `http://localhost:9090/targets`: all four targets show **UP**.
2. `http://localhost:3000` (login `admin` / your `GRAFANA_ADMIN_PASSWORD`): Connections -> Data sources -> both show "Data source is working" when you press Test.
3. Trigger one DAG run. In Prometheus, query `airflow_scheduler_heartbeat` and `pg_up`. Both should return data.

---

## 5. Dashboards

Build these in the Grafana UI, then export each as JSON (Share -> Export) into `monitoring/grafana/dashboards/` and commit. Provisioning then rebuilds them on any machine.

The three dashboards below already exist as committed JSON in `monitoring/grafana/dashboards/` (`pipeline-overview.json`, `layer-health.json`, `infrastructure.json`) and are imported live. Edit panels in the UI and re-export to keep the files in sync.

All Postgres time series panels use this shape (Format: Time series):

```sql
SELECT
    started_at AS time,
    stage AS metric,
    duration_s AS value
FROM ops.pipeline_run_log
WHERE $__timeFilter(started_at)
ORDER BY 1;
```

### 5.1 Pipeline Overview

| Panel | Type | Query source |
|---|---|---|
| Last run status | Stat | latest `master` row, `status` |
| Hours since last success | Stat | the overdue query (3.5), without the CASE |
| Stage duration over time | Time series | query above |
| Total run duration | Time series | `SUM(duration_s)` grouped by `run_id` |
| Retries per run | Bar chart | `attempt` where `attempt > 1` |
| Airflow DAG duration | Time series | Prometheus: `airflow_dagrun_duration_sum / airflow_dagrun_duration_count` |

### 5.2 Layer Health (one row per layer)

| Layer | Panels |
|---|---|
| Source | rows per source table over time, extract duration per job, freshness |
| Staging | inserted/updated per run, reject ratio, zero-delta streak |
| Warehouse | `dim_customers` / `dim_products` / `fact_sales` counts, orphans, staging-vs-fact reconciliation |
| Analytics | months in `monthly_kpi_snapshot`, latest month, KPI week-over-week change |
| Master | DQ failures and GX failures per layer over time |

Row counts over time:

```sql
SELECT
    captured_at AS time,
    layer || '.' || table_name AS metric,
    row_count AS value
FROM ops.table_snapshot
WHERE $__timeFilter(captured_at)
    AND layer = 'warehouse'
ORDER BY 1;
```

### 5.3 Infrastructure (Prometheus)

| Panel | PromQL |
|---|---|
| Postgres up | `pg_up` |
| Postgres connections used | `sum(pg_stat_activity_count) / max(pg_settings_max_connections)` |
| Warehouse DB size | `pg_database_size_bytes{datname="datawarehouse"}` |
| Deadlocks | `increase(pg_stat_database_deadlocks[1h])` |
| Mongo up | `mongodb_up` |
| Mongo connections | `mongodb_ss_connections{conn_type="current"}` |
| Scheduler heartbeat | `increase(airflow_scheduler_heartbeat[5m])` |
| DAG import errors | `airflow_dag_processing_import_errors` |

Metric names can differ slightly between exporter versions. If a panel is empty, open `http://localhost:9090` and use the metric browser to find the exact name.

---

## 6. Alerts (Grafana-managed)

Create under Alerting -> Alert rules. Set the evaluation interval to 5m for infra and 15m for pipeline-data rules. Each rule: query -> Reduce (Last) -> Threshold.

Contact point: Alerting -> Contact points -> add an **Email** point with your address. Put it in the default notification policy so every rule uses it.

Provisioned as code: all rules below except #8 already live in `monitoring/grafana/provisioning/alerting/rules.yaml` (groups `warehouse-data` at 15m, `warehouse-infra` at 5m), the Email contact point in `contact-points.yaml`, and the default policy in `policies.yaml`. Rule #8 is pending: the month column of `monthly_kpi_snapshot` is still a placeholder.

| # | Alert | Datasource | Condition | For | Severity |
|---|---|---|---|---|---|
| 1 | Pipeline overdue | Warehouse | `hours_overdue > 0` | 0m | critical |
| 2 | Source shrink | Warehouse | `max_drop_ratio > 0.2` | 0m | critical |
| 3 | Staging reject ratio high | Warehouse | `reject_ratio > 0.01` | 0m | warning |
| 4 | Staging zero-delta streak | Warehouse | `zero_runs = 3` | 0m | warning |
| 5 | Warehouse orphans | Warehouse | `orphans > 0` | 0m | critical |
| 6 | Warehouse reconciliation mismatch | Warehouse | `staging_rows <> fact_rows` | 0m | critical |
| 7 | Warehouse shrink | Warehouse | shrink query, `> 0` | 0m | critical |
| 8 | Analytics stale month | Warehouse | latest month older than previous month | 0m | warning |
| 9 | Target down | Prometheus | `up == 0` | 2m | critical |
| 10 | Scheduler heartbeat stalled | Prometheus | `increase(airflow_scheduler_heartbeat[5m]) < 1` | 5m | critical |
| 11 | DAG import errors | Prometheus | `airflow_dag_processing_import_errors > 0` | 5m | critical |
| 12 | Postgres connections high | Prometheus | connections used `> 0.8` | 5m | warning |

Settings that avoid noisy or silent alerts:
- Set **No data** state to `Alerting` for rule 1 (a missing row is exactly what you want to hear about) and `OK` for the rest.
- Do not alert on every Airflow retry. Your Airflow failure email and the summary email already cover task-level failure. These Grafana alerts catch what Airflow cannot see.
- Add a one-line runbook to each rule's **Summary** annotation, for example: "Staging reject ratio high: check `source.cust_info` for null keys, then the extract that fed it."

---

## 7. Hardening

- Prometheus, Grafana and exporters bound to `127.0.0.1` only (done above).
- Change the Grafana admin password through `.env`. Never keep the default.
- `grafana_ro` is read-only. `exporter` has `pg_monitor` only. Neither can write.
- `.env` stays gitignored. `leaks.yml` (gitleaks) already scans history, so a leaked password will be caught.
- Add `healthcheck` blocks and `restart: unless-stopped` to `postgres`, `mongo` and `airflow-scheduler`.
- Keep **healthchecks.io** as the external dead man's switch: ping at the end of a successful `summary_email`, alert if no ping by 12:30 IST on weekdays.

---

## 8. Build order and done-checklist

1. Phase 1: tables and `track_stage` in `main.py` and both extract scripts. Verify rows appear in `ops.pipeline_run_log` after `python main.py`.
2. Prove the pipeline in Airflow (containers up, one green run, one deliberately failed gate).
3. Add the DB roles and the monitoring stack (section 4). All four Prometheus targets are UP.
4. Build the three dashboards, export JSON, commit.
5. Create alerts 1, 9 and 10 first (overdue, target down, scheduler stalled). Add the rest layer by layer.
6. Test every alert once by forcing the condition (for example insert a fake low row count in a test run, stop `mongodb-exporter`).
7. Add the external dead man's switch.

Done when:
- [ ] A failed stage shows red in Grafana and an email arrives.
- [ ] Stopping the scheduler container produces an email within about 10 minutes.
- [ ] Skipping a weekday run produces the overdue email.
- [ ] Every layer has at least one alert with a tested trigger.
- [ ] Dashboards load from provisioned JSON on a fresh `docker compose up`.

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Prometheus target DOWN | Wrong service name or container not on the same compose network. Check `docker compose ps` |
| `pg_*` metrics empty | `exporter` role missing `pg_monitor`, or wrong password in `DATA_SOURCE_NAME` |
| No Airflow metrics | Scheduler not recreated after adding the `STATSD` env vars |
| Grafana Postgres test fails | `grafana_ro` has no `USAGE` on a schema, or password mismatch |
| Panels show "No data" | `$__timeFilter` range does not cover any run, or `ops.*` tables are still empty |
| Overdue alert fires on a weekend | `ISODOW` timezone mismatch: confirm the `AT TIME ZONE 'Asia/Kolkata'` part |
| Extract stages missing from run log | The extract scripts must wrap `submit()` in `track_stage` (see section 2.2) |
