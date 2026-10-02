from datetime import UTC, datetime

from src.jobs.mongo_to_postgres import (
    build_pipeline,
    detect_incremental_column,
    format_mongo_bound,
    format_mongo_date,
    format_pymongo_bound,
    mongo_read_uri,
    spark_type_to_postgres,
    to_utc,
    watermark_range_filter,
)

A = datetime(2026, 8, 1, tzinfo=UTC)
B = datetime(2026, 9, 1, tzinfo=UTC)


def test_format_mongo_date_utc_zulu():
    assert format_mongo_date(A) == "2026-08-01T00:00:00.000Z"


def test_to_utc_parses_known_string_format():
    assert to_utc("2026-08-22 11:42:50") == datetime(
        2026, 8, 22, 11, 42, 50, tzinfo=UTC
    )


def test_to_utc_keeps_naive_as_utc():
    assert to_utc(datetime(2026, 1, 1)) == datetime(2026, 1, 1, tzinfo=UTC)  # noqa: DTZ001


def test_format_mongo_bound_date_uses_extended_json():
    assert format_mongo_bound(A, "date") == '{"$date": "2026-08-01T00:00:00.000Z"}'


def test_format_mongo_bound_string_uses_plain_string():
    assert format_mongo_bound(A, "string") == '"2026-08-01 00:00:00"'


def test_format_pymongo_bound_date_passthrough():
    assert format_pymongo_bound(A, "date") == A


def test_format_pymongo_bound_string_formats():
    assert format_pymongo_bound(A, "string") == "2026-08-01 00:00:00"


def test_watermark_range_filter_full_window_string_kind():
    assert watermark_range_filter("updated_at", None, B, "string") == {
        "updated_at": {"$lte": "2026-09-01 00:00:00"}
    }


def test_watermark_range_filter_incremental_date_kind():
    assert watermark_range_filter("updated_at", A, B, "date") == {
        "updated_at": {"$gt": A, "$lte": B}
    }


def test_watermark_range_filter_no_column_matches_all():
    assert watermark_range_filter(None, A, B, "date") == {}


def test_build_pipeline_none_column_matches_all():
    assert build_pipeline(None, None, B, True) == "[]"


def test_build_pipeline_first_chunk_exclusive():
    pipeline = build_pipeline("updated_at", A, B, True, kind="string")
    assert '"$gt": "2026-08-01 00:00:00"' in pipeline
    assert '"$lte": "2026-09-01 00:00:00"' in pipeline


def test_build_pipeline_later_chunk_inclusive():
    pipeline = build_pipeline("updated_at", A, B, False, kind="string")
    assert '"$gte": "2026-08-01 00:00:00"' in pipeline


def test_detect_incremental_column_prefers_updated():
    fields = ["_id", "created_at", "updated_at"]
    assert detect_incremental_column(fields, None) == "updated_at"


def test_detect_incremental_column_falls_back_to_created():
    assert detect_incremental_column(["_id", "created_at"], None) == "created_at"


def test_detect_incremental_column_none_when_absent():
    assert detect_incremental_column(["_id"], None) is None


def test_detect_incremental_column_override_validated():
    assert detect_incremental_column(["a", "b"], "b") == "b"
    assert detect_incremental_column(["a", "b"], "zzz") is None


def test_spark_type_to_postgres_mapping():
    assert spark_type_to_postgres("string") == "TEXT"
    assert spark_type_to_postgres("timestamp") == "TIMESTAMPTZ"
    assert spark_type_to_postgres("long") == "BIGINT"
    assert spark_type_to_postgres("whatever") == "TEXT"


def test_mongo_read_uri_adds_slash_before_options(monkeypatch):
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    assert mongo_read_uri() == (
        "mongodb://localhost:27017/?serverSelectionTimeoutMS=5000&connectTimeoutMS=10000"
    )


def test_mongo_read_uri_keeps_database_path(monkeypatch):
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017/mydb")
    assert mongo_read_uri() == (
        "mongodb://localhost:27017/mydb?serverSelectionTimeoutMS=5000&connectTimeoutMS=10000"
    )


def test_mongo_read_uri_keeps_existing_options(monkeypatch):
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017/?retryWrites=true")
    assert mongo_read_uri() == (
        "mongodb://localhost:27017/?retryWrites=true&serverSelectionTimeoutMS=5000&connectTimeoutMS=10000"
    )
