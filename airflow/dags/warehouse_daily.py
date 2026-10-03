"""Daily warehouse pipeline: parallel extracts, sequential loads, GX quality gates.

Chain: preflight >> [extract_mongo, extract_databricks] >> source_tests >>
staging >> staging_tests >> warehouse >> warehouse_tests >> analytics >>
analytics_tests >> master.
"""

import os
from datetime import timedelta

import pendulum
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup

from airflow import DAG

REPO = "/opt/warehouse"
TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "Asia/Kolkata")

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=60),
}


# logs task failure context for external alerting integrations
def log_failure(context: dict) -> None:
    task_id = context["task_instance"].task_id
    print(f"warehouse_daily failed task={task_id} error={context.get('exception')}")


# builds one pipeline stage task backed by main.py
def stage_task(stage: str) -> BashOperator:
    return BashOperator(
        task_id=stage,
        bash_command=f"cd {REPO} && python main.py --only {stage}",
        execution_timeout=timedelta(hours=2),
        on_failure_callback=log_failure,
    )


with DAG(
    dag_id="warehouse_daily",
    description="Extract, load, and validate the data warehouse layers",
    schedule="@daily",
    start_date=pendulum.datetime(2025, 1, 1, tz=TIMEZONE),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["warehouse", "production"],
    doc_md=__doc__,
) as dag:
    preflight = BashOperator(
        task_id="preflight",
        bash_command=f"cd {REPO} && python scripts/check_sources.py",
        execution_timeout=timedelta(minutes=10),
        retries=0,
        on_failure_callback=log_failure,
    )

    with TaskGroup(group_id="extract") as extract:
        extract_mongo = BashOperator(
            task_id="extract_mongo",
            bash_command=f"cd {REPO} && python scripts/run_mongo_job.py",
            execution_timeout=timedelta(hours=3),
            sla=timedelta(hours=2),
            on_failure_callback=log_failure,
        )
        extract_databricks = BashOperator(
            task_id="extract_databricks",
            bash_command=f"cd {REPO} && python scripts/run_databricks_job.py",
            execution_timeout=timedelta(hours=3),
            sla=timedelta(hours=2),
            on_failure_callback=log_failure,
        )

    source_tests = stage_task("source-tests")
    staging = stage_task("staging")
    staging_tests = stage_task("staging-tests")
    warehouse = stage_task("warehouse")
    warehouse_tests = stage_task("warehouse-tests")
    analytics = stage_task("analytics")
    analytics_tests = stage_task("analytics-tests")
    master = stage_task("master")

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
    )
