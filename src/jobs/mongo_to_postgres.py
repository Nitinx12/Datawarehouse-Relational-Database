import argparse
import math
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StructType

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.connection import (
    get_mongo_client,
    get_postgres_connection,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

JOB_NAME = "mongo_to_postgres"
WATERMARK_COLUMN = "updatedAt"


# reads an int env var with a fallback default
def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# parses CLI arguments for the mongo to postgres job
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incremental MongoDB to Postgres loader"
    )
    parser.add_argument(
        "--collections",
        default="",
        help="Comma separated Mongo collections, empty means all",
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
    parser.add_argument("--mongo-database", default="", help="Override MONGO_DB env")
    parser.add_argument(
        "--target-schema", default="", help="Override POSTGRES_SCHEMA_SOURCE env"
    )
    parser.add_argument(
        "--watermark-column",
        default=WATERMARK_COLUMN,
        help="Incremental column, default updatedAt",
    )
    parser.add_argument(
        "--job-name", default=JOB_NAME, help="Job name recorded in source.etl_logs"
    )
    return parser.parse_args()


# builds a spark session with local mongo and postgres jars
def build_spark(app_name: str) -> SparkSession:
    if SparkSession.getActiveSession() is not None:
        return SparkSession.getActiveSession()  # type: ignore[return-value]
    jar_dir = PROJECT_ROOT / "jars"
    jars = sorted(
        str(p) for p in jar_dir.glob("*.jar") if "databricks" not in p.name.lower()
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
        .config(
            "spark.mongodb.read.partitioner",
            os.getenv("MONGO_PARTITIONER", "MongoPaginateBySizePartitioner"),
        )
        .config(
            "spark.mongodb.read.partition.sizeInMB",
            os.getenv("MONGO_PARTITION_MB", "64"),
        )
    )
    session = builder.getOrCreate()
    session.sparkContext.setLogLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    return session


# returns the postgres jdbc url from environment
def jdbc_url() -> str:
    return f"jdbc:postgresql://{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', '')}"


# creates source.etl_logs when it does not exist
def ensure_etl_logs_table() -> None:
    ddl_path = PROJECT_ROOT / "sql" / "01_source_etl_logs.sql"
    ddl = ddl_path.read_text(encoding="utf-8") if ddl_path.exists() else ""
    statements = [s for s in ddl.split(";") if s.strip()] if ddl else []
    conn = get_postgres_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            if statements:
                for statement in statements:
                    cur.execute(statement)
            else:
                cur.execute(
                    "CREATE SCHEMA IF NOT EXISTS source; "
                    "CREATE TABLE IF NOT EXISTS source.etl_logs (id BIGSERIAL PRIMARY KEY, "
                    "job_name VARCHAR NOT NULL, collection_name VARCHAR NOT NULL, "
                    "target_schema VARCHAR NOT NULL, target_table VARCHAR NOT NULL, "
                    "mode VARCHAR NOT NULL, watermark_column VARCHAR NOT NULL, "
                    "watermark_from TIMESTAMPTZ, watermark_to TIMESTAMPTZ, "
                    "rows_extracted BIGINT NOT NULL DEFAULT 0, rows_loaded BIGINT NOT NULL DEFAULT 0, "
                    "chunks INTEGER NOT NULL DEFAULT 0, status VARCHAR NOT NULL, "
                    "error_message TEXT, started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
                    "finished_at TIMESTAMPTZ)"
                )
    finally:
        conn.close()


# fetches the last successful watermark for a collection
def get_last_watermark(job_name: str, collection: str) -> datetime | None:
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT watermark_to FROM source.etl_logs "
                "WHERE job_name = %s AND collection_name = %s AND status = 'SUCCESS' "
                "ORDER BY watermark_to DESC LIMIT 1",
                (job_name, collection),
            )
            row = cur.fetchone()
            if row is None or row[0] is None:
                return None
            value: datetime = row[0]
            return value if value.tzinfo else value.replace(tzinfo=UTC)
    finally:
        conn.close()


# inserts a STARTED audit row and returns its id
def insert_log_start(
    job_name: str,
    collection: str,
    target_schema: str,
    mode: str,
    watermark_column: str,
    watermark_from: datetime | None,
    watermark_to: datetime,
) -> int:
    conn = get_postgres_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO source.etl_logs (job_name, collection_name, target_schema, "
                "target_table, mode, watermark_column, watermark_from, watermark_to, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'STARTED') RETURNING id",
                (
                    job_name,
                    collection,
                    target_schema,
                    collection,
                    mode,
                    watermark_column,
                    watermark_from,
                    watermark_to,
                ),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
    finally:
        conn.close()


# marks an audit row as SUCCESS or FAILED with counters
def update_log_finish(
    log_id: int,
    status: str,
    rows_extracted: int,
    rows_loaded: int,
    chunks: int,
    error_message: str | None = None,
) -> None:
    conn = get_postgres_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE source.etl_logs SET status = %s, rows_extracted = %s, "
                "rows_loaded = %s, chunks = %s, error_message = %s, finished_at = NOW() WHERE id = %s",
                (status, rows_extracted, rows_loaded, chunks, error_message, log_id),
            )
    finally:
        conn.close()


# formats a datetime as mongo extended-json $date
def format_mongo_date(value: datetime) -> str:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")


# builds the aggregation pipeline for one watermark chunk
def build_pipeline(
    watermark_column: str, start: datetime | None, end: datetime, first_chunk: bool
) -> str:
    op = "$gt" if first_chunk else "$gte"
    if start is None:
        match = f'{{"{watermark_column}": {{"$lte": {{"$date": "{format_mongo_date(end)}"}}}}}}'
    else:
        match = f'{{"{watermark_column}": {{"{op}": {{"$date": "{format_mongo_date(start)}"}}, "$lte": {{"$date": "{format_mongo_date(end)}"}}}}}}'
    return f'[{{"$match": {match}}}, {{"$sort": {{"{watermark_column}": 1}}}}]'


# splits the watermark window into time-bounded chunks using only boundary keys
def get_chunk_boundaries(
    collection: str,
    watermark_column: str,
    watermark_from: datetime | None,
    watermark_to: datetime,
    batch_size: int,
    database: str | None = None,
) -> list[tuple[datetime | None, datetime]]:
    client = get_mongo_client()
    try:
        db_name = database or os.getenv("MONGO_DB", "erp_source")
        coll = client[db_name][collection]
        base_filter: dict = {}
        if watermark_from is not None:
            base_filter = {
                watermark_column: {"$gt": watermark_from, "$lte": watermark_to}
            }
        else:
            base_filter = {watermark_column: {"$lte": watermark_to}}
        total = coll.count_documents(base_filter)
        if total == 0:
            return []
        n_chunks = max(1, math.ceil(total / batch_size))
        if n_chunks == 1:
            return [(watermark_from, watermark_to)]
        edges: list[datetime] = []
        for i in range(n_chunks):
            docs = (
                coll.find(base_filter, {watermark_column: 1})
                .sort(watermark_column, 1)
                .skip(i * batch_size)
                .limit(1)
            )
            for doc in docs:
                value = doc.get(watermark_column)
                if isinstance(value, datetime):
                    edges.append(value if value.tzinfo else value.replace(tzinfo=UTC))
        if not edges:
            return [(watermark_from, watermark_to)]
        bounds: list[tuple[datetime | None, datetime]] = []
        for i, edge in enumerate(edges):
            start = watermark_from if i == 0 else edge
            end = edges[i + 1] if i + 1 < len(edges) else watermark_to
            bounds.append((start, end))
        return bounds
    finally:
        client.close()


# reads one watermark chunk from mongo through the spark connector
def read_mongo_chunk(
    spark: SparkSession,
    database: str,
    collection: str,
    pipeline: str,
) -> DataFrame:
    mongo_uri = (
        os.getenv("MONGO_URL", "").strip()
        or f"mongodb://{os.getenv('MONGO_HOST', 'localhost')}:{os.getenv('MONGO_PORT', '27017')}"
    )
    return (
        spark.read.format("mongodb")
        .option("spark.mongodb.read.connection.uri", mongo_uri)
        .option("spark.mongodb.read.database", database)
        .option("spark.mongodb.read.collection", collection)
        .option("aggregation.pipeline", pipeline)
        .load()
    )


# flattens mongo types into a postgres-ready frame
def normalize_mongo_frame(frame: DataFrame, watermark_column: str) -> DataFrame:
    if "_id" in frame.columns:
        id_type = frame.schema["_id"].dataType
        if isinstance(id_type, StructType):
            names = [f.name for f in id_type.fields]
            oid_field = (
                "oid" if "oid" in names else ("$oid" if "$oid" in names else names[0])
            )
            frame = frame.withColumn(
                "id", F.col(f"_id.{oid_field}").cast("string")
            ).drop("_id")
        else:
            frame = frame.withColumn("id", F.col("_id").cast("string")).drop("_id")
    complex_cols = [
        f.name
        for f in frame.schema.fields
        if isinstance(f.dataType, (StructType, ArrayType))
    ]
    for column in complex_cols:
        frame = frame.withColumn(column, F.to_json(F.col(column)))
    if watermark_column in frame.columns:
        frame = frame.withColumn(
            watermark_column, F.col(watermark_column).cast("timestamp")
        )
    return frame.withColumn("_loaded_at", F.current_timestamp())


# maps a spark type name to a postgres column type
def spark_type_to_postgres(type_name: str) -> str:
    mapping = {
        "string": "TEXT",
        "integer": "BIGINT",
        "long": "BIGINT",
        "short": "BIGINT",
        "byte": "BIGINT",
        "double": "DOUBLE PRECISION",
        "float": "DOUBLE PRECISION",
        "decimal": "NUMERIC",
        "boolean": "BOOLEAN",
        "timestamp": "TIMESTAMPTZ",
        "date": "DATE",
        "binary": "BYTEA",
    }
    return mapping.get(type_name.lower(), "TEXT")


# creates the target table and evolves it with new columns
def ensure_target_table(
    schema: str, table: str, frame: DataFrame, pk: str | None = "id"
) -> None:
    conn = get_postgres_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            definitions = []
            for field in frame.schema.fields:
                pg_type = spark_type_to_postgres(
                    field.dataType.simpleString().split("<")[0].split("(")[0]
                )
                pk_suffix = " PRIMARY KEY" if field.name == pk else ""
                definitions.append(f'"{field.name}" {pg_type}{pk_suffix}')
            cur.execute(
                f'CREATE TABLE IF NOT EXISTS "{schema}"."{table}" ({", ".join(definitions)})'
            )
            for field in frame.schema.fields:
                if field.name == pk:
                    continue
                pg_type = spark_type_to_postgres(
                    field.dataType.simpleString().split("<")[0].split("(")[0]
                )
                cur.execute(
                    f'ALTER TABLE "{schema}"."{table}" ADD COLUMN IF NOT EXISTS "{field.name}" {pg_type}'
                )
    finally:
        conn.close()


# writes one chunk to postgres with staging upsert on pk
def write_chunk_upsert(
    frame: DataFrame,
    schema: str,
    table: str,
    user: str,
    password: str,
    url: str,
    jdbc_batchsize: int = 5000,
    pk: str | None = "id",
) -> int:
    stage = f"{table}__stg"
    (
        frame.write.format("jdbc")
        .option("url", url)
        .option("dbtable", f"{schema}.{stage}")
        .option("user", user)
        .option("password", password)
        .option("driver", "org.postgresql.Driver")
        .option("batchsize", str(jdbc_batchsize))
        .option("stringtype", "unspecified")
        .mode("overwrite")
        .save()
    )
    conn = get_postgres_connection()
    try:
        conn.autocommit = True
        columns = frame.columns
        names = ", ".join(f'"{c}"' for c in columns)
        updates = (
            ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in columns if c != pk)
            if pk
            else ""
        )
        with conn.cursor() as cur:
            if pk and updates:
                cur.execute(
                    f'INSERT INTO "{schema}"."{table}" ({names}) '
                    f'SELECT {names} FROM "{schema}"."{stage}" '
                    f'ON CONFLICT ("{pk}") DO UPDATE SET {updates}'
                )
            elif pk:
                cur.execute(
                    f'INSERT INTO "{schema}"."{table}" ({names}) '
                    f'SELECT {names} FROM "{schema}"."{stage}" ON CONFLICT DO NOTHING'
                )
            else:
                cur.execute(
                    f'INSERT INTO "{schema}"."{table}" ({names}) '
                    f'SELECT {names} FROM "{schema}"."{stage}"'
                )
            cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{stage}"')
            row = cur.fetchone()
            return int(row[0]) if row else 0
    finally:
        conn.close()


# discovers loadable mongo collections excluding system ones
def discover_collections(database: str) -> list[str]:
    client = get_mongo_client()
    try:
        return [
            c
            for c in client[database].list_collection_names()
            if not c.startswith("system.")
        ]
    finally:
        client.close()


# runs extract and load for a single collection with chunking
def run_collection(
    spark: SparkSession,
    collection: str,
    database: str,
    target_schema: str,
    watermark_column: str,
    batch_size: int,
    full_load: bool,
    job_name: str,
) -> dict:
    watermark_to = datetime.now(UTC)
    watermark_from = None if full_load else get_last_watermark(job_name, collection)
    mode = "FULL" if full_load or watermark_from is None else "INCREMENTAL"
    log_id = insert_log_start(
        job_name,
        collection,
        target_schema,
        mode,
        watermark_column,
        watermark_from,
        watermark_to,
    )
    bounds = get_chunk_boundaries(
        collection, watermark_column, watermark_from, watermark_to, batch_size, database
    )
    if not bounds:
        update_log_finish(log_id, "SUCCESS", 0, 0, 0)
        return {"collection": collection, "extracted": 0, "loaded": 0, "chunks": 0}
    default_parallelism = max(1, spark.sparkContext.defaultParallelism)
    max_retries = _int_env("ETL_MAX_RETRIES", 3)
    retry_delay = _int_env("ETL_RETRY_DELAY_SECONDS", 30)
    jdbc_batchsize = _int_env("JDBC_BATCHSIZE", 5000)
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    url = jdbc_url()
    total_extracted = 0
    total_loaded = 0
    chunks_done = 0
    for index, (start, end) in enumerate(bounds):
        pipeline = build_pipeline(
            watermark_column, start, end, first_chunk=(index == 0)
        )
        attempt = 0
        while True:
            try:
                raw = read_mongo_chunk(spark, database, collection, pipeline)
                partitions = min(
                    default_parallelism, max(1, math.ceil(batch_size / 2000))
                )
                prepared = normalize_mongo_frame(raw, watermark_column).repartition(
                    partitions
                )
                ensure_target_table(target_schema, collection, prepared)
                extracted = prepared.count()
                if extracted == 0:
                    break
                loaded = write_chunk_upsert(
                    prepared,
                    target_schema,
                    collection,
                    user,
                    password,
                    url,
                    jdbc_batchsize,
                )
                total_extracted += extracted
                total_loaded += loaded
                chunks_done += 1
                logger.info(
                    "chunk done collection=%s chunk=%d rows=%d",
                    collection,
                    index,
                    loaded,
                )
                break
            except Exception as exc:
                attempt += 1
                if attempt > max_retries:
                    update_log_finish(
                        log_id,
                        "FAILED",
                        total_extracted,
                        total_loaded,
                        chunks_done,
                        str(exc),
                    )
                    raise
                time.sleep(retry_delay)
    update_log_finish(log_id, "SUCCESS", total_extracted, total_loaded, chunks_done)
    return {
        "collection": collection,
        "extracted": total_extracted,
        "loaded": total_loaded,
        "chunks": chunks_done,
    }


# entrypoint wiring spark, watermarks, chunks and audit logs
def main() -> None:
    args = parse_args()
    batch_size = args.batch_size or _int_env("ETL_BATCH_SIZE", 10000)
    database = args.mongo_database or os.getenv("MONGO_DB", "erp_source")
    target_schema = args.target_schema or os.getenv("POSTGRES_SCHEMA_SOURCE", "source")
    ensure_etl_logs_table()
    if args.collections.strip():
        collections = [c.strip() for c in args.collections.split(",") if c.strip()]
    else:
        collections = discover_collections(database)
    if not collections:
        logger.info("no collections to load")
        return
    spark = build_spark(args.job_name)
    failed: list[str] = []
    try:
        for collection in collections:
            try:
                result = run_collection(
                    spark,
                    collection,
                    database,
                    target_schema,
                    args.watermark_column,
                    batch_size,
                    args.full_load,
                    args.job_name,
                )
                logger.info("collection done name=%s result=%s", collection, result)
            except Exception as exc:  # noqa: BLE001
                logger.error("collection failed name=%s error=%s", collection, exc)
                failed.append(collection)
    finally:
        spark.stop()
    if failed:
        raise SystemExit(f"failed collections: {', '.join(failed)}")


if __name__ == "__main__":
    main()
