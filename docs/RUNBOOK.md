# Datawarehouse Runbook

**Environment:** Windows 11 + Docker Desktop, PowerShell, repo at `C:\Git-Repo\datawarehouse`
**Last updated:** 2026-10-04 (after the 2026-10-03 debug session)
**Next scheduled run:** Monday 2026-10-05 11:00 IST (DAG `warehouse_daily`, Mon-Fri)

> Never put real passwords, tokens or app passwords in this file, in chat, or in screenshots. Secrets live only in `.env`.

---

## 1. Status at a glance

| Area | State |
|---|---|
| Full DAG run | **Green.** Two consecutive successes: `manual__2026-10-03T17:39:57+00:00` (~2 min) and `manual__2026-10-03T18:07:24+00:00` (~4 min, sequential extracts, all services running) |
| Memory (3.5 GiB Docker limit) | Fixed in code: extracts run one after the other, Spark `driver_memory=1g`. No need to stop Grafana/webserver/dashboard any more |
| Airflow metrics in Prometheus | **Working** (StatsD port fixed). Heartbeat confirmed rising |
| Grafana dashboards | Working. Two panels still need the logging fix (section 6) |
| Grafana alert rules | Parse/provisioning bug fixed (all 11 loaded). End-to-end email test (Step 4) **not yet confirmed** |
| Contact point `Email` | Delivery attempt logged with no error. Confirm the test email actually reached the inbox |
| Credential rotation | **Not done. Required before Monday** (see section 6, item 1) |
| DAG `warehouse_daily` | **Unpaused** (it will run on schedule) |

---

## 2. How the system works

- One DAG, `warehouse_daily`. Airflow is only the scheduler; each task calls `main.py --only <stage>` or a script.
- Task order: `preflight` -> `extract_mongo` -> `extract_databricks` -> `source-tests` -> `staging` -> `staging-tests` -> `warehouse` -> `warehouse-tests` -> `analytics` -> `analytics-tests` -> `master` -> `summary_email`.
- `summary_email` always runs and **deliberately fails the DAG run** if any earlier task failed. That is by design, not an SMTP fault.
- Commands inside the container run as `cd /opt/warehouse && UV_PROJECT_ENVIRONMENT=/tmp/warehouse-venv uv run --project /opt/warehouse <command>`. The `/tmp` venv avoids the Windows `.venv` in the repo mount.
- `max_active_runs=1`: a second run waits in `queued` while one is `running`.
- Monitoring chain: Airflow -> StatsD (UDP 9125) -> `statsd-exporter` -> Prometheus -> Grafana; Postgres/Mongo exporters -> Prometheus; pipeline history in `ops.pipeline_run_log` and `ops.table_snapshot` -> Grafana (Postgres datasource `warehouse`); alerts -> Grafana contact point `Email`.

---

## 3. Daily operations

**Rule 1: never rebuild, recreate or restart containers while a run is active.** It kills running tasks with SIGTERM.

| Task | Command |
|---|---|
| List runs | `docker compose exec airflow-scheduler airflow dags list-runs -d warehouse_daily` |
| Trigger a run | `docker compose exec airflow-scheduler airflow dags trigger warehouse_daily` (note the `logical_date` it prints) |
| Task states of a run | `docker compose exec airflow-scheduler airflow tasks states-for-dag-run warehouse_daily "2026-10-03T18:07:24+00:00"` (use the real logical date, not a placeholder and not the run_id) |
| Read a failed task log | `docker compose exec airflow-scheduler bash -c 'grep -n -i -E "ERROR\|Exception\|does not exist\|Cannot allocate" "/opt/airflow/logs/dag_id=warehouse_daily/run_id=<run_id>/task_id=<task>/attempt=1.log" \| head -30'` (extract tasks live under `task_id=extract.extract_mongo` / `extract.extract_databricks`) |
| Run one stage by hand | `docker compose exec airflow-scheduler bash -c "cd /opt/warehouse && UV_PROJECT_ENVIRONMENT=/tmp/warehouse-venv uv run --project /opt/warehouse main.py --only <stage>"` |
| Run SQL from PowerShell | `@'` ...sql... `'@ \| docker compose exec -T postgres psql -U postgres -d datawarehouse` (stdin avoids quote mangling) |
| Apply a SQL file | `Get-Content .\path\file.sql -Raw \| docker compose exec -T postgres psql -U postgres -d datawarehouse -v ON_ERROR_STOP=1` |
| Check memory | `docker stats --no-stream` |
| Pause / unpause DAG | `docker compose exec airflow-scheduler airflow dags pause\|unpause warehouse_daily` |
| Pipeline history | `SELECT stage, status, rows_out FROM ops.pipeline_run_log ORDER BY started_at DESC LIMIT 15;` |
| Prometheus targets | `(Invoke-RestMethod "http://localhost:9090/api/v1/targets").data.activeTargets \| Select-Object @{n='job';e={$_.labels.job}}, health, lastError` |

Search tip: PowerShell `Select-String` has no `-Recurse`. Use `Get-ChildItem -Recurse -File ... | Select-String ...` and exclude `.venv`, `.git`, `logs`.

---

## 4. Errors we faced and how they were fixed

Legend: **FIXED** = fixed and verified, **FIXED (verify)** = fix applied, outcome not yet confirmed, **OPEN** = still to do.

### 4.1 Airflow and pipeline

| # | Error / symptom | Cause | Fix | Status |
|---|---|---|---|---|
| 1 | `500 Internal Server Error` on Docker `_ping` during `docker compose up` | Transient Docker Desktop engine hiccup | Retry; `docker compose ps` worked straight after | FIXED |
| 2 | Triggered run stuck in `queued` | An older run was still `running`; `max_active_runs=1` | Check `list-runs`, mark the stale run failed, then trigger | FIXED |
| 3 | Extract logs: `Task received SIGTERM signal` | `docker compose up --build` recreated the scheduler mid-run | Rule 1 above. Never recreate containers during a run | FIXED (process rule) |
| 4 | `OSError: Exec format error: '/opt/warehouse/.venv/Scripts/spark-submit.cmd'` | Container tried to use the Windows `.venv` from the repo mount | Always run with `UV_PROJECT_ENVIRONMENT=/tmp/warehouse-venv` (the DAG already does) | FIXED |
| 5 | `source-tests` failed in GX on `source_loc_a101` / `source_cust_az12` | `source.LOC_A101` missing: Mongo was empty when the extract ran | Re-ran `run_mongo_job.py` once data was loaded (LOC_A101: 18,484 rows) | FIXED |
| 6 | Mongo extract logged `no collections to load` but reported `success` | `discover_collections()` lists non-`system.` collections; none existed | Data loaded. **Guard still missing** (section 6) | OPEN (hardening) |
| 7 | `staging` failed: `procedure staging.load_px_cat_g1v2() does not exist` | Docker Postgres had schemas but none of the load procedures | Applied the six `proc_staging_*.sql`, three `proc_warehouse_*.sql` and `monthly_kpi_snapshot.sql` (11 routines verified) | FIXED |
| 8 | `analytics` failed: `relation "analytics.report_sales_monthly" does not exist` | Views never created in Docker Postgres | Applied `report_sales_monthly`, `report_customers`, `report_products`, `report_category_sales` | FIXED |
| 9 | `analytics-tests` failed: `missing materialized view mv_report_customers` | Materialized view never created | Applied `sql/analytics/materialized_views/mv_report_customers.sql` | FIXED |
| 10 | `mv_report_customers` created with **0 rows** (while `report_customers` had 18,482) | View was created while the old failed run's retry was truncating/reloading tables, so it snapshotted an empty source | `REFRESH MATERIALIZED VIEW analytics.mv_report_customers;` -> 18,482 rows | FIXED |
| 11 | Materialized view goes stale after every load | Nothing refreshes it; the test only checks existence | Add `REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_report_customers;` to the end of the `analytics` stage | OPEN |
| 12 | `summary_email` failed and looked like an SMTP problem | It fails on purpose when any earlier task failed | None needed (by design) | FIXED (understanding) |
| 13 | `preflight` took ~106 s instead of ~15 s | Recreating the scheduler wipes `/tmp/warehouse-venv`; the first task rebuilds it | Expected after a scheduler recreate. Normal speed afterwards | FIXED (expected) |

### 4.2 Memory (Docker limit 3.5 GiB, PC has 8 GB)

| # | Error / symptom | Cause | Fix | Status |
|---|---|---|---|---|
| 14 | `OSError: Cannot allocate memory: '/opt/warehouse/jars'`, `Error initializing SparkContext`, `java.io.IOException: Cannot allocate memory` | Two parallel Spark JVMs at `driver_memory=2g` plus webserver (1 GiB), Grafana, scheduler exceeded 3.5 GiB | (a) `docker-compose.yml` line 17: `SPARK_DRIVER_MEMORY: 1g`. (b) `scripts/_submit.py` line 97: fallback `"4g"` -> `"1g"`. (c) `warehouse_daily.py`: added `extract_mongo >> extract_databricks` so extracts run sequentially. Verified with all services running (run 18:07:24 green) | FIXED |

If a Spark task later fails with a Java heap `OutOfMemoryError` (not `Cannot allocate memory`), raise `SPARK_DRIVER_MEMORY` to `1500m`.

### 4.3 Monitoring: Prometheus, StatsD, Grafana

| # | Error / symptom | Cause | Fix | Status |
|---|---|---|---|---|
| 15 | `airflow_scheduler_heartbeat` empty although the `airflow` target was `up` | Airflow sent StatsD to port **8125**, `statsd-exporter` listens on **9125**. UDP drops silently | `docker-compose.yml` line 25: `AIRFLOW__METRICS__STATSD_PORT: "9125"`, then recreated scheduler + webserver. Heartbeat now rises (11 -> 23 in a minute) | FIXED |
| 16 | `statsd-exporter` crash-loop: `invalid match: airflow.operator_failures_*` | Bad glob in `monitoring/statsd/mapping.yml` | Mapping now uses `match_type: regex` for operator metrics; exporter starts cleanly | FIXED |
| 17 | All 11 Grafana alert rules showed `[sse.missingDependentNode] ... could not find dependent node [$B]` | In provisioned rules, `reduce` and `threshold` nodes need the bare refId (`B`), not `$B`. Only `math` nodes use `$A - $B2` | Rewrote `expression: $A` -> `A`, `$B` -> `B`, `$C` -> `C` on reduce/threshold nodes in `rules.yaml`; restarted Grafana. Errors gone from the rules list | FIXED (verify Health = OK in UI) |
| 18 | `Target down` would never fire | `up == 0` keeps the sample value 0, threshold is `> 0`, so 0 > 0 is false | `expr: up == bool 0` (1 when down, 0 when up) | FIXED (verify with Step 4) |
| 19 | `Staging zero-delta streak` would fire immediately | Every staging run logs `rows_out = 0` | Rule paused with `isPaused: true` until `rows_out` is really written. Remove that line afterwards | FIXED (paused) |
| 20 | Dashboard panel "Last run status" shows **No data** | `status` is text; a stat panel only shows numeric fields by default | Patched `pipeline-overview.json` panel 1 (text field, value mappings, orange for unknown values). File delivered with this runbook, not yet loaded into Grafana | OPEN (apply file) |
| 21 | "Warehouse DB size" panel red | No thresholds, Grafana default red-at-80 applied to a byte count | Neutral threshold added in patched `infrastructure.json` | OPEN (apply file) |
| 22 | Backup file `rules.yaml.bak` next to live rules | Left by the edit | Grafana ignores it (log: `invalid suffix ... skipping`); moved to the user profile folder | FIXED |

Harmless Grafana log noise to ignore: `plugins.dedupe ... duplicate` warnings, `skipped registering status sub-resource ... dual writing`, `Failed to read plugin provisioning files ... provisioning/plugins` (that folder does not exist, which is fine), and `RemovedInAirflow3Warning` about the StatsD validator.

### 4.4 Tooling and process mistakes (so we do not repeat them)

| Mistake | Correct approach |
|---|---|
| Pasted `<logical_date>` literally into `states-for-dag-run` | Use the real logical date printed by `dags trigger` |
| `airflow dags state` assumed to take a run_id | It needs the logical date |
| Typed YAML lines (`AIRFLOW__METRICS__STATSD_PORT: 9125`) or Python lines into PowerShell | Those are file contents, not commands. Edit the file, or use the .NET replace snippet below |
| `Select-String -Recurse` | Not a parameter. Pipe from `Get-ChildItem -Recurse` |
| `psql -c "..."` with embedded double quotes | Pipe SQL through stdin with a here-string |
| `uv run` without `UV_PROJECT_ENVIRONMENT` inside the container | Always set it to `/tmp/warehouse-venv` |
| Relying on the truncated `main.py` failure summary | Grep the raw task log |
| Pasting `.env` contents into chat | Redact values. Anything pasted is compromised and must be rotated |

Safe file edit from PowerShell (no BOM, keeps content intact):

```powershell
$p = Join-Path (Get-Location) "docker-compose.yml"
$t = [System.IO.File]::ReadAllText($p)
$t = $t.Replace('old text', 'new text')
[System.IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($false)))
```

### 4.5 Security

| Issue | Action |
|---|---|
| Real SMTP app password, Grafana admin password and two DB role passwords were pasted into a chat | Treat all four as compromised. Rotate (section 5) |
| Postgres (5432), Mongo (27017), Airflow webserver (8080) and dashboard (8501) are bound to `0.0.0.0` | Change to `127.0.0.1:<port>:<port>` in `docker-compose.yml` unless LAN access is needed |
| Databricks token was listed for rotation in the original runbook | Rotate in the same pass |

---

## 5. Credential rotation procedure

Do this when **no DAG run is active** and before Monday 11:00 IST.

1. **Gmail app password:** Google Account -> Security -> App passwords. Revoke the old one, create a new one.
2. **Databricks token:** create a new token in the workspace, revoke the old one.
3. **Postgres role passwords:** list roles with `\du`, then:
   ```powershell
   @'
   ALTER ROLE <exporter_role> PASSWORD '<new_password>';
   ALTER ROLE <grafana_role> PASSWORD '<new_password>';
   '@ | docker compose exec -T postgres psql -U postgres -d datawarehouse -v ON_ERROR_STOP=1
   ```
4. Update `.env` with every new value. Confirm `.env` is in `.gitignore` and was never committed.
5. Recreate the affected services:
   ```powershell
   docker compose up -d --force-recreate postgres-exporter grafana airflow-scheduler
   ```
6. Grafana only reads the admin password on first start, so reset it explicitly:
   ```powershell
   docker compose exec grafana grafana cli admin reset-admin-password '<new_password>'
   ```
7. Verify: Prometheus targets all `up`; Grafana Postgres datasource passes Save & test; contact point **Test** email arrives; trigger one DAG run and confirm it is green (this proves the new SMTP and Databricks credentials).

Expect one slow `preflight` (~2 min) after recreating the scheduler.

---

## 6. Open items (do in this order)

| Priority | Item | How |
|---|---|---|
| 1 | **Rotate credentials** (before Monday) | Section 5 |
| 2 | **Confirm email path** | Grafana -> Alerting -> Contact points -> **Test** on `Email`; check inbox and spam |
| 3 | **Verify alert Health** | Alerting -> Alert rules -> Health filter: **Error** and **No data** must be empty, nothing Firing. If `Warehouse reconciliation mismatch` errors, change `$A - $B2` to `$$A - $$B2` in `rules.yaml` (Grafana expands `$` in provisioning files), then `docker compose restart grafana` |
| 4 | **Step 4: end-to-end alert test** | `docker compose stop mongodb-exporter`; expect "Target down" email in ~7-10 min (5 min evaluation + 2 min pending + ~30 s grouping); then `docker compose start mongodb-exporter` and expect a "Resolved" email |
| 5 | **Refresh the materialized view in the pipeline** | Add `REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_report_customers;` at the end of the `analytics` stage (unique index on `customer_sk` already exists) |
| 6 | **Fix `rows_out` / `rows_in` logging** | All staging/warehouse/analytics rows log `rows_out = 0`, extract/master are NULL. Find the writer: `Get-ChildItem -Recurse -File -Include *.py \| Where-Object { $_.FullName -notmatch '\\(\.venv\|\.git\|logs)\\' } \| Select-String "pipeline_run_log\|rows_out\|rows_in\|rows_rejected"`. Then remove `isPaused: true` from `wh-zero-delta` |
| 7 | **One `run_id` per DAG run** | Today each `main.py --only <stage>` call generates its own `run_id` (`local_...`, `__airflow_temporary_run_...`), so "Total run duration" and "Staging vs fact reconciliation" are per task, not per run. Pass Airflow's run id into `main.py` (for example via an env var set in the DAG) |
| 8 | **Load the patched dashboards** | Find where Grafana reads them: `Select-String -Path .\monitoring\grafana\provisioning\dashboards\dashboards.yml -Pattern path`. Copy `pipeline-overview.json` and `infrastructure.json` over the existing files, then `docker compose restart grafana`. Add a mapping for any other `status` value: `SELECT DISTINCT status FROM ops.pipeline_run_log;` |
| 9 | **Watch Monday's scheduled run** | It is the first scheduled run since the fixes. Check `airflow_dagrun_schedule_delay` appears (only scheduled runs emit it) and the "Airflow DAG duration" panel updates |
| 10 | **Empty-source guard** | Make `extract_mongo` fail when no collections are found instead of logging `no collections to load` and succeeding |
| 11 | **SQL bootstrap script** | Create `scripts/apply_sql.ps1` that applies, in order: staging procs, warehouse procs, analytics tables, views, then the materialized view. Prevents errors 7-9 on a rebuilt Postgres volume |
| 12 | **Pick one Postgres** | Docker Postgres is the real one (option A). Stop the Windows PG17 service so nothing points at it by accident |
| 13 | **Confirm KPI month column** | `SELECT column_name FROM information_schema.columns WHERE table_schema='analytics' AND table_name='monthly_kpi_snapshot' ORDER BY ordinal_position;` (likely `order_month`) |
| 14 | **Data quirk** | `source."CUST_AZ12"."GEN"` contains the text `{"$numberDouble": "NaN"}` for some rows. Map it to NULL in `src/jobs/mongo_to_postgres.py` |
| 15 | **Reconciliation rule scope** | `wh-reconcile` compares `MAX(row_count)` over all snapshots, not the latest run. Restrict it to the latest `run_id` once item 7 is done |
| 16 | **Minor** | Two-row gap between `dim_customers` (18,484) and `report_customers` (18,482): confirm it is intentional. "Mongo connections" shows 0: check `mongodb_ss_connections` labels. Optional: healthchecks.io key, decision on committing `airflow/plugins/.gitkeep` |

---

## 7. Monitoring reference

### Prometheus targets (`monitoring/prometheus.yml`, scrape every 30 s)

`prometheus` (localhost:9090), `postgres` (postgres-exporter:9187), `mongodb` (mongodb-exporter:9216), `airflow` (statsd-exporter:9102). Prometheus has **no** rule files; all alerting lives in Grafana.

### Airflow metrics (from `monitoring/statsd/mapping.yml`)

| Metric | Appears when |
|---|---|
| `airflow_scheduler_heartbeat`, `airflow_dag_processing_*`, `airflow_executor_*`, `airflow_pool_*` | Continuously |
| `airflow_dagrun_duration{status,dag_id}` (`_sum`, `_count`) | After a DAG run finishes. Mean is across all runs since the exporter last restarted |
| `airflow_operator_successes{operator}` | After a task succeeds |
| `airflow_operator_failures{operator}` | Only after the first task failure |
| `airflow_dagrun_schedule_delay{dag_id}` | Only for scheduled runs, not manual triggers |

### Grafana alert rules (`monitoring/grafana/provisioning/alerting/rules.yaml`)

| Rule | Group (interval) | Fires when | Severity |
|---|---|---|---|
| Pipeline overdue | warehouse-data (15m) | Hours since last `master` SUCCESS exceeds 25 h (Tue-Fri) or 73 h (Sat-Mon). No data = Alerting | critical |
| Source shrink | warehouse-data | A source table dropped more than 20% vs previous snapshot | critical |
| Staging reject ratio high | warehouse-data | Latest staging reject ratio above 1% | warning |
| Staging zero-delta streak | warehouse-data | Last 3 staging runs all moved 0 rows. **Paused** until `rows_out` is fixed | warning |
| Warehouse orphans | warehouse-data | Orphan product/customer keys above 0 | critical |
| Warehouse reconciliation mismatch | warehouse-data | Staging `sales_details` rows differ from `fact_sales` | critical |
| Warehouse shrink | warehouse-data | Any dim/fact table lost rows | critical |
| Target down | warehouse-infra (5m) | `up == bool 0` for 2 min | critical |
| Scheduler heartbeat stalled | warehouse-infra | `increase(airflow_scheduler_heartbeat[5m]) < 1` for 5 min | critical |
| DAG import errors | warehouse-infra | `airflow_dag_processing_import_errors > 0` for 5 min | critical |
| Postgres connections high | warehouse-infra | Connection usage above 80% for 5 min | warning |

Contact point `Email` (`contact-points.yaml`) sends to `$SMTP_USER`; `policies.yaml` routes every alert to it. Required Grafana environment: `SMTP_USER`, `GF_SMTP_ENABLED=true`, `GF_SMTP_HOST=smtp.gmail.com:587`, `GF_SMTP_USER`, `GF_SMTP_PASSWORD`, `GF_SMTP_FROM_ADDRESS` (all confirmed set).

### Dashboards (`monitoring/grafana/provisioning/dashboards`)

Infrastructure (Prometheus), Layer Health and Pipeline Overview (Postgres datasource `warehouse`, tables `ops.pipeline_run_log` and `ops.table_snapshot`).

---

## 8. Troubleshooting playbook

| Symptom | Check | Likely fix |
|---|---|---|
| Run stuck in `queued` | `list-runs`: is another run `running`? | Wait or mark the stale run failed |
| Task failed | Grep the raw task log (section 3) | Match the message to section 4 |
| `does not exist` for a procedure, view or table | `\df staging.*`, `\dv analytics.*`, `\dt source.*` | Apply the missing SQL file; long-term, build the bootstrap script |
| `Cannot allocate memory` | `docker stats --no-stream` | Confirm `SPARK_DRIVER_MEMORY=1g` and extracts are sequential |
| Task killed with SIGTERM | Did a container get recreated mid-run? | Rule 1 |
| `analytics-tests` fails on the materialized view | `SELECT count(*) FROM analytics.mv_report_customers;` | `REFRESH MATERIALIZED VIEW analytics.mv_report_customers;` |
| Airflow panels empty | `Where-Object { $_ -like "*airflow*" }` over metric names in Prometheus | Check `STATSD_PORT=9125`; task metrics only exist after a run |
| Grafana rule shows Error | Open the rule, read the message | `$` in expressions, datasource uid, or SQL error |
| Alert rule Normal while the target is down | Query `up` in Prometheus | Rule or query bug |
| Rule Firing but no email | Alerting -> Contact points -> last delivery; Notification policies | SMTP credentials, `SMTP_USER` empty inside the container |
| Heartbeat not rising | Run `increase` twice, 60 s apart | Scheduler down or StatsD port wrong |

---

## 9. Rules to live by

1. No container rebuild, recreate or restart while a DAG run is active.
2. Always use `UV_PROJECT_ENVIRONMENT=/tmp/warehouse-venv` inside the container.
3. Read the raw task log, not the truncated summary.
4. Pipe SQL through stdin; edit files with the .NET replace snippet, not by typing file contents into the shell.
5. Redact secrets before pasting anywhere; rotate anything that leaked.
6. After any change to `docker-compose.yml`, recreate only the affected services, and only between runs.
7. A "success" with zero rows is not success: check row counts, not just status.
