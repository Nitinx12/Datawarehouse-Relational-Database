import os

from delta import configure_spark_with_delta_pip
from dotenv import load_dotenv
from pyspark.sql import SparkSession

from .logger import get_logger

load_dotenv()

logger = get_logger(__name__)


# returns a configured spark session, reusing the active one when present
def get_spark_session(app_name: str = "lrdb", with_delta: bool = True) -> SparkSession:
    active = SparkSession.getActiveSession()
    if active is not None:
        return active
    builder = SparkSession.builder.appName(app_name)
    master = os.getenv("SPARK_MASTER", "")
    if not master and os.getenv("ENVIRONMENT", "local") == "local":
        master = "local[*]"
    if master:
        builder = builder.master(master)
    builder = builder.config(
        "spark.sql.session.timeZone", os.getenv("BUSINESS_TIMEZONE", "Asia/Kolkata")
    ).config(
        "spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTITIONS", "200")
    )
    if with_delta:
        builder = builder.config(
            "spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension"
        ).config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        builder = configure_spark_with_delta_pip(builder)
    session = builder.getOrCreate()
    session.sparkContext.setLogLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.info("spark connected app=%s master=%s", app_name, master or "existing")
    return session


# stops the given session, or the active one when omitted
def stop_spark_session(session: SparkSession | None = None) -> None:
    target = session if session is not None else SparkSession.getActiveSession()
    if target is not None:
        target.stop()
