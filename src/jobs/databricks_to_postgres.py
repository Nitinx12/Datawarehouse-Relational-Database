import argparse
import math
import os
import sys
import time
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
from databricks.sql.client import Connection as DatabricksConnection
from dotenv import load_dotenv
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BinaryType,
    BooleanType,
    ByteType,
    DataType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    MapType,
    ShortType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.jobs._report import render_report, short_error
from src.jobs.mongo_to_postgres import (
    _int_env,
    count_rows,
    ensure_etl_logs_table,
    ensure_merge_key,
    ensure_target_table,
    get_last_watermark,
    insert_log_start,
    jdbc_url,
    update_log_finish,
    validate_collection,
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
        default="",
        help="Incremental column, empty means auto-detect (updated_at first)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover, count and plan without writing anything",
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
        .config("spark.driver.extraJavaOptions", "-Duser.timezone=UTC")
        .config("spark.executor.extraJavaOptions", "-Duser.timezone=UTC")
    )
    session = builder.getOrCreate()
    session.sparkContext.setLogLevel(os.getenv("SPARK_LOG_LEVEL", "WARN"))
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
    return aware.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f") + "+00:00"


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


# counts every row in a databricks table
def count_table(
    connection: DatabricksConnection, catalog: str, schema: str, table: str
) -> int:
    arrow = fetch_all_arrow(
        connection, f"SELECT COUNT(*) AS n FROM {qualified(catalog, schema, table)}"
    )
    return int(arrow.to_pandas()["n"][0])


# maps an arrow type to a spark type, None when unsupported
def arrow_to_spark_type(t: pa.DataType) -> DataType | None:
    types = pa.types
    if types.is_boolean(t):
        return BooleanType()
    if types.is_int8(t):
        return ByteType()
    if types.is_int16(t) or types.is_uint8(t):
        return ShortType()
    if types.is_int32(t) or types.is_uint16(t):
        return IntegerType()
    if types.is_int64(t) or types.is_uint32(t):
        return LongType()
    if types.is_uint64(t):
        return DecimalType(20, 0)
    if types.is_float16(t) or types.is_float32(t):
        return FloatType()
    if types.is_float64(t):
        return DoubleType()
    if types.is_decimal(t):
        return DecimalType(t.precision, t.scale)
    if types.is_string(t) or types.is_large_string(t) or types.is_null(t):
        return StringType()
    if types.is_binary(t) or types.is_large_binary(t):
        return BinaryType()
    if types.is_date(t):
        return DateType()
    if types.is_timestamp(t):
        return TimestampType()
    if types.is_list(t) or types.is_large_list(t):
        element = arrow_to_spark_type(t.value_type)
        return ArrayType(element) if element is not None else None
    if types.is_map(t):
        key, item = arrow_to_spark_type(t.key_type), arrow_to_spark_type(t.item_type)
        return MapType(key, item) if key is not None and item is not None else None
    if types.is_struct(t):
        fields = []
        for i in range(t.num_fields):
            child = arrow_to_spark_type(t.field(i).type)
            if child is None:
                return None
            fields.append(StructField(t.field(i).name, child, True))
        return StructType(fields)
    return None


# converts one arrow batch into a spark dataframe with an explicit schema
# (pandas inference turns nullable ints into doubles and fails on all-null columns)
def arrow_to_spark(spark: SparkSession, batch: pa.Table) -> DataFrame:
    fields: list[StructField] = []
    columns: list[list] = []
    for index, field in enumerate(batch.schema):
        spark_type = arrow_to_spark_type(field.type)
        column = batch.column(index)
        if spark_type is None:
            column = column.cast(pa.string())
            spark_type = StringType()
        fields.append(StructField(field.name, spark_type, True))
        columns.append(column.to_pylist())
    rows = list(zip(*columns)) if columns else []
    return spark.createDataFrame(rows, StructType(fields))


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
    dry_run: bool,
    run_id: str,
) -> dict:
    started = time.time()
    watermark_to = datetime.now(UTC)
    total = count_table(connection, catalog, schema, table)
    before = count_rows(target_schema, table)
    if watermark_column is None:
        logger.info("no watermark column table=%s using full reload", table)
        mode = "full (no watermark)"
        watermark_from = None
    elif full_load:
        mode = "FULL"
        watermark_from = None
    else:
        watermark_from = get_last_watermark(job_name, table)
        mode = "INCREMENTAL" if watermark_from is not None else "FULL"
    log_id = insert_log_start(
        job_name,
        table,
        target_schema,
        mode,
        watermark_column,
        watermark_from,
        watermark_to,
        run_id,
    )
    result = {
        "name": table,
        "mode": mode,
        "status": "SUCCESS",
        "watermark_column": watermark_column,
        "total": total,
        "extracted": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": total,
        "before": before,
        "after": before,
        "columns": 0,
        "chunks": 0,
        "seconds": 0.0,
        "validation": "N/A",
        "validation_detail": "",
        "error": None,
    }
    try:
        where = (
            f"WHERE {watermark_filter(watermark_column, watermark_from, watermark_to)}"
            if watermark_column
            else ""
        )
        window_total = count_window(
            connection,
            catalog,
            schema,
            table,
            watermark_column,
            watermark_from,
            watermark_to,
        )
        if window_total == 0:
            result["validation"], result["validation_detail"] = validate_collection(
                target_schema, table, before
            )
            if result["validation"] == "PASS":
                result["status"] = "SKIPPED (no new/changed rows)"
                update_log_finish(
                    log_id,
                    "SUCCESS",
                    0,
                    0,
                    0,
                    None,
                    0,
                    0,
                    "PASS",
                    result["validation_detail"],
                )
            else:
                result["status"] = "VALIDATION FAILED"
                result["error"] = result["validation_detail"]
                update_log_finish(
                    log_id,
                    "VALIDATION FAILED",
                    0,
                    0,
                    0,
                    result["validation_detail"],
                    0,
                    0,
                    "FAIL",
                    result["validation_detail"],
                )
            return result
        if dry_run:
            # the window count is the plan; no need to pull every batch
            result["extracted"] = window_total
            result["chunks"] = math.ceil(window_total / batch_size)
            result["columns"] = (
                len(table_columns(connection, catalog, schema, table)) + 1
            )
            result["skipped"] = max(total - window_total, 0)
            result["status"] = "DRY-RUN"
            update_log_finish(log_id, "DRY-RUN", window_total, 0, result["chunks"])
            return result
        default_parallelism = max(1, spark.sparkContext.defaultParallelism)
        jdbc_batchsize = _int_env("JDBC_BATCHSIZE", 10000)
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        url = jdbc_url()
        max_retries = _int_env("ETL_MAX_RETRIES", 3)
        retry_delay = _int_env("ETL_RETRY_DELAY_SECONDS", 10)
        merge_ready: bool | None = None
        cursor = connection.cursor()
        try:
            cursor.arraysize = batch_size
            cursor.execute(f"SELECT * FROM {qualified(catalog, schema, table)} {where}")
            while True:
                batch = cursor.fetchmany_arrow(batch_size)
                if batch.num_rows == 0:
                    break
                attempt = 0
                while True:
                    try:
                        raw = arrow_to_spark(spark, batch)
                        partitions = min(
                            default_parallelism,
                            max(1, math.ceil(batch.num_rows / 5000)),
                        )
                        prepared = normalize_frame(raw, watermark_column).repartition(
                            partitions
                        )
                        if not result["columns"]:
                            result["columns"] = len(prepared.columns)
                        ensure_target_table(target_schema, table, prepared, pk)
                        if merge_ready is None:
                            merge_ready = ensure_merge_key(target_schema, table, pk)
                        inserted, updated = write_chunk_upsert(
                            prepared,
                            target_schema,
                            table,
                            user,
                            password,
                            url,
                            jdbc_batchsize,
                            pk if merge_ready else None,
                        )
                        # counters only move once the chunk fully succeeded (retry-safe)
                        result["extracted"] += batch.num_rows
                        result["chunks"] += 1
                        result["inserted"] += inserted
                        result["updated"] += updated
                        logger.info(
                            "chunk done table=%s chunk=%d rows=%d",
                            table,
                            result["chunks"],
                            inserted + updated,
                        )
                        break
                    except Exception:
                        attempt += 1
                        if attempt > max_retries:
                            raise
                        time.sleep(retry_delay)
        finally:
            cursor.close()
        result["skipped"] = max(total - result["extracted"], 0)
        result["after"] = count_rows(target_schema, table)
        result["validation"], result["validation_detail"] = validate_collection(
            target_schema, table, before + result["inserted"]
        )
        if result["validation"] == "PASS":
            update_log_finish(
                log_id,
                "SUCCESS",
                result["extracted"],
                result["inserted"] + result["updated"],
                result["chunks"],
                None,
                result["inserted"],
                result["updated"],
                "PASS",
                result["validation_detail"],
            )
        else:
            result["status"] = "VALIDATION FAILED"
            result["error"] = result["validation_detail"]
            update_log_finish(
                log_id,
                "VALIDATION FAILED",
                result["extracted"],
                result["inserted"] + result["updated"],
                result["chunks"],
                result["validation_detail"],
                result["inserted"],
                result["updated"],
                "FAIL",
                result["validation_detail"],
            )
        return result
    except Exception as exc:
        result["status"] = "FAILED"
        result["error"] = short_error(exc)
        update_log_finish(
            log_id,
            "FAILED",
            result["extracted"],
            result["inserted"] + result["updated"],
            result["chunks"],
            traceback.format_exc(),
            result["inserted"],
            result["updated"],
            "FAIL",
            result["error"],
        )
        raise
    finally:
        result["seconds"] = time.time() - started


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
        watermark = detect_column(columns, [watermark_arg.strip()])
        if watermark is None:
            raise ValueError(
                f"watermark column {watermark_arg.strip()!r} not in table {table}, "
                f"have {columns}"
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
    started = datetime.now(UTC)
    args = parse_args()
    run_id = f"{datetime.now(UTC):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
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
        results: list[dict] = []
        failed: list[str] = []
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.fields[tbl]}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task(
                    "extract", total=len(tables), tbl="starting..."
                )
                for table in tables:
                    progress.update(task, tbl=table)
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
                            args.dry_run,
                            run_id,
                        )
                        logger.info("table done name=%s result=%s", table, result)
                        results.append(result)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("table failed name=%s error=%s", table, exc)
                        failed.append(table)
                        results.append(
                            {
                                "name": table,
                                "mode": "FAILED",
                                "status": "FAILED",
                                "watermark_column": args.watermark_column or None,
                                "total": 0,
                                "extracted": 0,
                                "inserted": 0,
                                "updated": 0,
                                "skipped": 0,
                                "before": 0,
                                "after": 0,
                                "columns": 0,
                                "chunks": 0,
                                "seconds": 0.0,
                                "validation": "N/A",
                                "validation_detail": "",
                                "error": short_error(exc),
                            }
                        )
                    progress.advance(task)
        finally:
            spark.stop()
        elapsed = (datetime.now(UTC) - started).total_seconds()
        has_issues = render_report(
            "Databricks -> PostgreSQL Extraction Report",
            f"{catalog}.{schema}",
            target_schema,
            run_id,
            args.dry_run,
            results,
            elapsed,
            "Tables",
            args.job_name,
            "Table",
        )
        logger.info("run %s complete issues=%s", run_id, has_issues)
        if failed:
            raise SystemExit(f"failed tables: {', '.join(failed)}")
    finally:
        close_connection(connection)


if __name__ == "__main__":
    main()
