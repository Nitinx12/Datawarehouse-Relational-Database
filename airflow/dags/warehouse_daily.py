"""
Airflow DAG for the daily warehouse pipeline. This is the main entrypoint for the warehouse ETL, and is scheduled to run Mon-Fri at 11:00 local time.
The DAG runs the following stages in order:
1. preflight: check that source systems are reachable and healthy
2. extract: pull data from source systems (MongoDB, Databricks)
3. source-tests: run quality checks on the extracted data
4. staging: load data into the staging layer of the warehouse
5. staging-tests: run quality checks on the staging layer
6. warehouse: load data into the warehouse layer
7. warehouse-tests: run quality checks on the warehouse layer
8. analytics: load data into the analytics layer
9. analytics-tests: run quality checks on the analytics layer
10. master: update the master table with the latest data
11. summary_email: send a summary email with the results of the run, including any failures
The DAG is configured with retries and exponential backoff for robustness, and sends email alerts on failures
"""

import logging
import os
from datetime import timedelta
from html import escape

import pendulum
from airflow.exceptions import AirflowFailException
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.email import send_email
from airflow.utils.state import TaskInstanceState
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule

from airflow import DAG

log = logging.getLogger(__name__)

REPO = "/opt/warehouse"
TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "Asia/Kolkata")
ALERT_EMAILS = [e.strip() for e in os.getenv("ALERT_EMAILS", "").split(",") if e.strip()]
WAREHOUSE_CONN_ID = os.getenv("WAREHOUSE_CONN_ID", "warehouse_postgres")

# uv resolves the project's locked environment, same as running locally
UV_RUN = f"cd {REPO} && uv run --project {REPO}"

# tables shown in the summary email (schema.table)
SUMMARY_TABLES = [
    "warehouse.dim_customers",
    "warehouse.dim_products",
    "warehouse.fact_sales",
    "analytics.monthly_kpi_snapshot",
]

STATE_COLORS = {
    "success": "#1a7f37",
    "failed": "#cf222e",
    "upstream_failed": "#bc4c00",
    "skipped": "#6e7781",
    "running": "#0969da",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _send(subject: str, html: str) -> None:
    if not ALERT_EMAILS:
        log.warning("ALERT_EMAILS not set, skipping email: %s", subject)
        return
    send_email(to=ALERT_EMAILS, subject=subject, html_content=html)


def notify_failure(context: dict) -> None:
    """Immediate alert when a task fails after all retries."""
    ti = context["task_instance"]
    run_date = context["logical_date"].in_timezone(TIMEZONE).format("YYYY-MM-DD HH:mm")
    exception = escape(str(context.get("exception")))
    log.error("warehouse_daily failed task=%s error=%s", ti.task_id, exception)
    html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px">
      <h2 style="color:{STATE_COLORS['failed']};margin-bottom:4px">Task failed: {escape(ti.task_id)}</h2>
      <table cellpadding="4">
        <tr><td><b>DAG</b></td><td>{escape(ti.dag_id)}</td></tr>
        <tr><td><b>Run</b></td><td>{escape(context['run_id'])} ({run_date} {TIMEZONE})</td></tr>
        <tr><td><b>Attempts</b></td><td>{ti.try_number} of {ti.max_tries + 1}</td></tr>
        <tr><td><b>Duration</b></td><td>{_fmt_duration(ti.duration)}</td></tr>
        <tr><td><b>Error</b></td><td><code>{exception}</code></td></tr>
      </table>
      <p><a href="{ti.log_url}">Open task log</a></p>
    </div>
    """
    try:
        _send(f"[FAILED] warehouse_daily - {ti.task_id}", html)
    except Exception:  # alerting must never mask the real failure
        log.exception("failed to send failure email")


def _fetch_row_counts() -> list[tuple[str, int | None]]:
    """Row counts per summary table; degrades gracefully if the connection is missing."""
    try:
        from airflow.providers.postgres.hooks.postgres import PostgresHook

        hook = PostgresHook(postgres_conn_id=WAREHOUSE_CONN_ID)
        return [(t, hook.get_first(f"SELECT count(*) FROM {t}")[0]) for t in SUMMARY_TABLES]
    except Exception:
        log.exception("row count lookup failed, continuing without it")
        return []


def send_summary(**context) -> None:
    """Final report. Always runs, then fails the run if anything upstream failed."""
    dag_run = context["dag_run"]
    this_task = context["task_instance"].task_id
    tis = [ti for ti in dag_run.get_task_instances() if ti.task_id != this_task]
    tis.sort(key=lambda t: (t.start_date is None, t.start_date))

    failed = [t for t in tis if t.state == TaskInstanceState.FAILED]
    blocked = [t for t in tis if t.state == TaskInstanceState.UPSTREAM_FAILED]
    retried = [t for t in tis if t.try_number > 1 and t.state == TaskInstanceState.SUCCESS]
    ok = not failed and not blocked

    start = dag_run.start_date or pendulum.now("UTC")
    wall = (pendulum.now("UTC") - start).total_seconds()
    run_date = context["logical_date"].in_timezone(TIMEZONE).format("ddd, DD MMM YYYY HH:mm")
    status = "SUCCESS" if ok else "FAILED"
    color = STATE_COLORS["success" if ok else "failed"]

    rows = ""
    for t in tis:
        state = str(t.state or "none")
        badge = STATE_COLORS.get(state, "#6e7781")
        log_cell = f'<a href="{t.log_url}">log</a>' if t.state == TaskInstanceState.FAILED else ""
        rows += (
            "<tr>"
            f"<td>{escape(t.task_id)}</td>"
            f'<td style="color:{badge};font-weight:600">{state.upper()}</td>'
            f"<td align='right'>{_fmt_duration(t.duration)}</td>"
            f"<td align='center'>{t.try_number}</td>"
            f"<td>{log_cell}</td>"
            "</tr>"
        )

    counts = _fetch_row_counts()
    counts_html = ""
    if counts:
        body = "".join(
            f"<tr><td>{escape(name)}</td><td align='right'>{'n/a' if n is None else f'{n:,}'}</td></tr>"
            for name, n in counts
        )
        counts_html = (
            "<h3>Warehouse snapshot</h3>"
            '<table cellpadding="6" cellspacing="0" style="border-collapse:collapse;min-width:360px">'
            '<tr style="background:#f6f8fa"><th align="left">Table</th><th align="right">Rows</th></tr>'
            f"{body}</table>"
        )

    notes = []
    if failed:
        notes.append("Failed: " + ", ".join(escape(t.task_id) for t in failed))
    if blocked:
        notes.append("Not run (upstream failed): " + ", ".join(escape(t.task_id) for t in blocked))
    if retried:
        notes.append("Recovered after retry: " + ", ".join(escape(t.task_id) for t in retried))
    notes_html = "".join(f"<li>{n}</li>" for n in notes) or "<li>No issues. All steps passed on first attempt.</li>"

    html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1f2328">
      <h2 style="margin-bottom:2px">warehouse_daily <span style="color:{color}">{status}</span></h2>
      <div style="color:#57606a">{run_date} {TIMEZONE} &middot; run <code>{escape(dag_run.run_id)}</code></div>
      <p>
        <b>{len(tis) - len(failed) - len(blocked)}</b> of <b>{len(tis)}</b> tasks passed
        &middot; total time <b>{_fmt_duration(wall)}</b>
      </p>
      <ul>{notes_html}</ul>
      {counts_html}
      <h3>Task breakdown</h3>
      <table cellpadding="6" cellspacing="0" style="border-collapse:collapse;min-width:520px">
        <tr style="background:#f6f8fa">
          <th align="left">Task</th><th align="left">State</th>
          <th align="right">Duration</th><th>Attempts</th><th></th>
        </tr>
        {rows}
      </table>
    </div>
    """
    _send(f"[{status}] warehouse_daily - {run_date}", html)

    if not ok:
        # keep the DAG run red; AirflowFailException skips retries
        raise AirflowFailException("pipeline had failed tasks, see summary email")


# --------------------------------------------------------------------------- #
# DAG
# --------------------------------------------------------------------------- #
DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=60),
    "on_failure_callback": notify_failure,
}


def stage_task(stage: str, retries: int | None = None) -> BashOperator:
    """One main.py stage. Quality-gate stages pass retries=0: a failed check won't fix itself."""
    extra = {} if retries is None else {"retries": retries}
    return BashOperator(
        task_id=stage,
        bash_command=f"{UV_RUN} main.py --only {stage}",
        execution_timeout=timedelta(hours=1),
        **extra,
    )


with DAG(
    dag_id="warehouse_daily",
    description="Extract, load and validate the data warehouse layers (Mon-Fri 11:00)",
    schedule="0 11 * * 1-5",
    start_date=pendulum.datetime(2025, 1, 1, tz=TIMEZONE),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=6),
    default_args=DEFAULT_ARGS,
    tags=["warehouse", "production"],
    doc_md=__doc__,
) as dag:
    preflight = BashOperator(
        task_id="preflight",
        bash_command=f"{UV_RUN} scripts/check_sources.py",
        execution_timeout=timedelta(minutes=10),
        retries=1,
        retry_delay=timedelta(minutes=2),
    )

    with TaskGroup(group_id="extract") as extract:
        extract_mongo = BashOperator(
            task_id="extract_mongo",
            bash_command=f"{UV_RUN} scripts/run_mongo_job.py",
            execution_timeout=timedelta(hours=2),
        )
        extract_databricks = BashOperator(
            task_id="extract_databricks",
            bash_command=f"{UV_RUN} scripts/run_databricks_job.py",
            execution_timeout=timedelta(hours=2),
        )

    source_tests = stage_task("source-tests", retries=0)
    staging = stage_task("staging")
    staging_tests = stage_task("staging-tests", retries=0)
    warehouse = stage_task("warehouse")
    warehouse_tests = stage_task("warehouse-tests", retries=0)
    analytics = stage_task("analytics")
    analytics_tests = stage_task("analytics-tests", retries=0)
    master = stage_task("master", retries=0)

    summary_email = PythonOperator(
        task_id="summary_email",
        python_callable=send_summary,
        trigger_rule=TriggerRule.ALL_DONE,  # run on success AND failure
        on_failure_callback=None,  # its own failure is the "pipeline failed" signal
        retries=1,
        retry_delay=timedelta(minutes=2),
        execution_timeout=timedelta(minutes=10),
    )

    (
        preflight
        >> extract
        >> source_tests
        >> staging
        >> staging_tests
        >> warehouse
        >> warehouse_tests
        >> analytics
        >> analytics_tests
        >> master
        >> summary_email
    )

    # summary must run even when a middle task dies and everything downstream is upstream_failed
    [preflight, extract, source_tests, staging, staging_tests, warehouse,
     warehouse_tests, analytics, analytics_tests] >> summary_email
