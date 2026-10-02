import argparse
import math
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
from databricks.sql.client import Connection as DatabricksConnection
from dotenv import load_dotenv
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StructType

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.jobs.mongo_to_postgres import (
    _int_env,
    ensure_etl_logs_table,
    ensure_target_table,
    get_last_watermark,
    insert_log_start,
    jdbc_url,
    update_log_finish,
    write_chunk_upsert,
)
from src.utils.connection import close_connection, get_databricks_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)

JOB_NAME = "databricks_to_postgres"
WATERMARK_COLUMN = "updated_at"
WATERMARK_CANDIDATES = [
    WATERMARK_COLUMN,
    "updatedAt",
    "modified_at",
    "last_modified",
    "LastModifiedDate",
    "SystemModstamp",
    "updated_on",
]
PK_CANDIDATES = ["id", "Id", "ID"]


# reads a str env var with a fallback default
def _str_env(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


# parses CLI arguments for the databricks to postgres job
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incremental Databricks to Postgres loader"
    )
    parser.add_argument(
        "--tables",
        default="",
        help="Comma separated Databricks tables, empty means all in schema",
    )
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Ignore watermark and reload everything",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="Rows per chunk, 0 means ETL_BATCH_SIZE env",
    )
    parser.add_argument(
        "--databricks-catalog", default="", help="Override DATABRICKS_CATALOG env"
    )
    parser.add_argument(
        "--databricks-schema",
        default="",
        help="Source schema, defaults to DATABRICKS_SCHEMA env or default",
    )
    parser.add_argument(
        "--target-schema", default="", help="Override POSTGRES_SCHEMA_SOURCE env"
    )
    parser.add_argument(
        "--watermark-column",
        default=WATERMARK_COLUMN,
        help="Incremental column, default updated_at, empty means auto-detect",
    )
    parser.add_argument(
        "--pk-column", default="id", help="Primary key for upsert, default id"
    )
    parser.add_argument(
        "--job-name", default=JOB_NAME, help="Job name recorded in source.etl_logs"
    )
    return parser.parse_args()


# builds a spark session tuned for arrow ingest and parallel jdbc writes
def build_spark(app_name: str) -> SparkSession:
    if SparkSession.getActiveSession() is not None:
        return SparkSession.getActiveSession()  # type: ignore[return-value]
    jar_dir = PROJECT_ROOT / "jars"
    jars = sorted(
        str(p)
        for p in jar_dir.glob("*.jar")
        if "mongo" not in p.name.lower() and "bson" not in p.name.lower()
    )
    builder = SparkSession.builder.appName(app_name)
    master = os.getenv("SPARK_MASTER", "")
    if not master and os.getenv("ENVIRONMENT", "local") == "local":
        master = "local[*]"
    if master:
        builder = builder.master(master)
    if jars:
        builder = builder.config("spark.jars", ",".join(jars))
    builder = (
        builder.config(
            "spark.sql.session.timeZone", os.getenv("BUSINESS_TIMEZONE", "Asia/Kolkata")
        )
        .config(
            "spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTITIONS", "200")
        )
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
    )
    session = builder.getOrCreate()
    session.sparkContext.setLogLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    return session


# renders a fully qualified databricks table name with backticks
def qualified(catalog: str, schema: str, table: str) -> str:
    return f"`{catalog}`.`{schema}`.`{table}`"


# runs a sql statement and returns the full arrow result
def fetch_all_arrow(connection: DatabricksConnection, sql: str) -> pa.Table:
    cursor = connection.cursor()
    try:
        cursor.execute(sql)
        return cursor.fetchall_arrow()
    finally:
        cursor.close()


# lists user tables in a databricks catalog schema
def discover_tables(
    connection: DatabricksConnection, catalog: str, schema: str
) -> list[str]:
    cursor = connection.cursor()
    try:
        cursor.execute(f"SHOW TABLES IN `{catalog}`.`{schema}`")
        rows = cursor.fetchall()
        return [row[1] for row in rows if not str(row[1]).startswith("system")]
    finally:
        cursor.close()


# returns the column names of a databricks table without scanning rows
def table_columns(
    connection: DatabricksConnection, catalog: str, schema: str, table: str
) -> list[str]:
    arrow = fetch_all_arrow(
        connection, f"SELECT * FROM {qualified(catalog, schema, table)} LIMIT 0"
    )
    return [field.name for field in arrow.schema]


# picks the first candidate present in columns, case-insensitive
def detect_column(columns: list[str], candidates: list[str]) -> str | None:
    lowered = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


# formats a datetime literal for databricks sql
def format_ts(value: datetime) -> str:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


# builds the watermark filter fragment for a window
def watermark_filter(
    watermark_column: str, watermark_from: datetime | None, watermark_to: datetime
) -> str:
    upper = f"`{watermark_column}` <= TIMESTAMP '{format_ts(watermark_to)}'"
    if watermark_from is None:
        return upper
    return f"`{watermark_column}` > TIMESTAMP '{format_ts(watermark_from)}' AND {upper}"


# counts rows inside the watermark window
def count_window(
    connection: DatabricksConnection,
    catalog: str,
    schema: str,
    table: str,
    watermark_column: str | None,
    watermark_from: datetime | None,
    watermark_to: datetime,
) -> int:
    where = (
        f"WHERE {watermark_filter(watermark_column, watermark_from, watermark_to)}"
        if watermark_column
        else ""
    )
    arrow = fetch_all_arrow(
        connection,
        f"SELECT COUNT(*) AS n FROM {qualified(catalog, schema, table)} {where}",
    )
    return int(arrow.to_pandas()["n"][0])


# converts one arrow batch into a spark dataframe
def arrow_to_spark(spark: SparkSession, batch: pa.Table) -> DataFrame:
    return spark.createDataFrame(batch.to_pandas())


# flattens complex columns and stamps the load time
def normalize_frame(frame: DataFrame, watermark_column: str | None) -> DataFrame:
    complex_cols = [
        f.name
        for f in frame.schema.fields
        if isinstance(f.dataType, (StructType, ArrayType))
    ]
    for column in complex_cols:
        frame = frame.withColumn(column, F.to_json(F.col(column)))
    if watermark_column and watermark_column in frame.columns:
        frame = frame.withColumn(
            watermark_column, F.col(watermark_column).cast("timestamp")
        )
    return frame.withColumn("_loaded_at", F.current_timestamp())


# runs extract and load for a single databricks table with chunked arrow fetch
def run_table(
    spark: SparkSession,
    connection: DatabricksConnection,
    table: str,
    catalog: str,
    schema: str,
    target_schema: str,
    watermark_column: str | None,
    pk: str | None,
    batch_size: int,
    full_load: bool,
    job_name: str,
) -> dict:
    watermark_to = datetime.now(UTC)
    watermark_from = None if full_load else get_last_watermark(job_name, table)
    mode = "FULL" if full_load or watermark_from is None else "INCREMENTAL"
    log_id = insert_log_start(
        job_name,
        table,
        target_schema,
        mode,
        watermark_column or "-",
        watermark_from,
        watermark_to,
    )
    where = (
        f"WHERE {watermark_filter(watermark_column, watermark_from, watermark_to)}"
        if watermark_column
        else ""
    )
    order = f"ORDER BY `{watermark_column}`, `{pk}`" if watermark_column and pk else ""
    total = count_window(
        connection,
        catalog,
        schema,
        table,
        watermark_column,
        watermark_from,
        watermark_to,
    )
    if total == 0:
        update_log_finish(log_id, "SUCCESS", 0, 0, 0)
        return {"table": table, "extracted": 0, "loaded": 0, "chunks": 0}
    default_parallelism = max(1, spark.sparkContext.defaultParallelism)
    jdbc_batchsize = _int_env("JDBC_BATCHSIZE", 10000)
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    url = jdbc_url()
    max_retries = _int_env("ETL_MAX_RETRIES", 3)
    retry_delay = _int_env("ETL_RETRY_DELAY_SECONDS", 30)
    cursor = connection.cursor()
    cursor.arraysize = batch_size
    total_extracted = 0
    total_loaded = 0
    chunks_done = 0
    table_ready = False
    try:
        cursor.execute(
            f"SELECT * FROM {qualified(catalog, schema, table)} {where} {order}"
        )
        while True:
            batch = cursor.fetchmany_arrow(batch_size)
            if batch.num_rows == 0:
                break
            attempt = 0
            while True:
                try:
                    raw = arrow_to_spark(spark, batch)
                    partitions = min(
                        default_parallelism, max(1, math.ceil(batch.num_rows / 5000))
                    )
                    prepared = normalize_frame(raw, watermark_column).repartition(
                        partitions
                    )
                    ensure_target_table(target_schema, table, prepared, pk)
                    table_ready = True
                    loaded = write_chunk_upsert(
                        prepared,
                        target_schema,
                        table,
                        user,
                        password,
                        url,
                        jdbc_batchsize,
                        pk,
                    )
                    total_extracted += batch.num_rows
                    total_loaded += loaded
                    chunks_done += 1
                    logger.info(
                        "chunk done table=%s chunk=%d rows=%d",
                        table,
                        chunks_done,
                        loaded,
                    )
                    break
                except Exception:
                    attempt += 1
                    if attempt > max_retries:
                        raise
                    time.sleep(retry_delay)
    except Exception as exc:
        update_log_finish(
            log_id, "FAILED", total_extracted, total_loaded, chunks_done, str(exc)
        )
        raise
    finally:
        cursor.close()
    if not table_ready:
        update_log_finish(log_id, "SUCCESS", 0, 0, 0)
        return {"table": table, "extracted": 0, "loaded": 0, "chunks": 0}
    update_log_finish(log_id, "SUCCESS", total_extracted, total_loaded, chunks_done)
    return {
        "table": table,
        "extracted": total_extracted,
        "loaded": total_loaded,
        "chunks": chunks_done,
    }


# resolves watermark and pk columns for a table
def resolve_columns(
    connection: DatabricksConnection,
    catalog: str,
    schema: str,
    table: str,
    watermark_arg: str,
    pk_arg: str,
) -> tuple[str | None, str | None]:
    columns = table_columns(connection, catalog, schema, table)
    if watermark_arg.strip():
        watermark = watermark_arg.strip()
        if watermark not in columns:
            raise ValueError(
                f"watermark column {watermark!r} not in table {table}, have {columns}"
            )
    else:
        watermark = detect_column(columns, WATERMARK_CANDIDATES)
    pk = pk_arg.strip() or None
    if pk and pk not in columns:
        found = detect_column(columns, [pk, *PK_CANDIDATES])
        pk = found
    if pk is None:
        logger.info("no pk found table=%s using append-only mode", table)
    return watermark, pk


# entrypoint wiring spark, watermarks, chunks and audit logs
def main() -> None:
    args = parse_args()
    batch_size = args.batch_size or _int_env("ETL_BATCH_SIZE", 10000)
    catalog = args.databricks_catalog or _str_env("DATABRICKS_CATALOG", "crm_source")
    schema = args.databricks_schema or _str_env("DATABRICKS_SCHEMA", "default")
    target_schema = args.target_schema or os.getenv("POSTGRES_SCHEMA_SOURCE", "source")
    ensure_etl_logs_table()
    connection = get_databricks_connection()
    try:
        if args.tables.strip():
            tables = [t.strip() for t in args.tables.split(",") if t.strip()]
        else:
            tables = discover_tables(connection, catalog, schema)
        if not tables:
            logger.info("no tables to load")
            return
        spark = build_spark(args.job_name)
        failed: list[str] = []
        try:
            for table in tables:
                try:
                    watermark, pk = resolve_columns(
                        connection,
                        catalog,
                        schema,
                        table,
                        args.watermark_column,
                        args.pk_column,
                    )
                    result = run_table(
                        spark,
                        connection,
                        table,
                        catalog,
                        schema,
                        target_schema,
                        watermark,
                        pk,
                        batch_size,
                        args.full_load,
                        args.job_name,
                    )
                    logger.info("table done name=%s result=%s", table, result)
                except Exception as exc:  # noqa: BLE001
                    logger.error("table failed name=%s error=%s", table, exc)
                    failed.append(table)
        finally:
            spark.stop()
        if failed:
            raise SystemExit(f"failed tables: {', '.join(failed)}")
    finally:
        close_connection(connection)


if __name__ == "__main__":
    main()
