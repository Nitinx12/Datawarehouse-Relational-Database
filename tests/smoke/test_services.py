import pytest

psycopg = pytest.importorskip("psycopg")


def pg_dsn():
    import os

    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "dbname": os.getenv("POSTGRES_DB", "datawarehouse"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "connect_timeout": 5,
        "autocommit": True,
    }


def pg_available():
    try:
        conn = psycopg.connect(**pg_dsn())
        conn.close()
        return True
    except Exception:  # noqa: BLE001
        return False


def mongo_available():
    try:
        from pymongo import MongoClient

        client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:  # noqa: BLE001
        return False


needs_pg = pytest.mark.skipif(not pg_available(), reason="postgres unreachable")
needs_mongo = pytest.mark.skipif(not mongo_available(), reason="mongodb unreachable")


@needs_pg
def test_schemas_exist():
    conn = psycopg.connect(**pg_dsn())
    try:
        rows = conn.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name IN ('source','staging','warehouse')"
        ).fetchall()
        assert {r[0] for r in rows} == {"source", "staging", "warehouse"}
    finally:
        conn.close()


@needs_pg
def test_etl_logs_table_exists():
    conn = psycopg.connect(**pg_dsn())
    try:
        row = conn.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'source' AND table_name = 'etl_logs'"
        ).fetchone()
        assert row is not None
    finally:
        conn.close()


@needs_pg
def test_staging_procedures_exist():
    conn = psycopg.connect(**pg_dsn())
    try:
        rows = conn.execute(
            "SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'staging' AND proname LIKE 'load_%'"
        ).fetchall()
        assert len(rows) >= 6
    finally:
        conn.close()


@needs_pg
def test_warehouse_procedures_exist():
    conn = psycopg.connect(**pg_dsn())
    try:
        rows = conn.execute(
            "SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'warehouse' AND proname LIKE 'load_%'"
        ).fetchall()
        assert {r[0] for r in rows} >= {
            "load_dim_customers",
            "load_dim_products",
            "load_fact_sales",
        }
    finally:
        conn.close()


@needs_mongo
def test_mongo_collections_exist():
    from pymongo import MongoClient

    client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=3000)
    try:
        names = client["erp_source"].list_collection_names()
        assert {"PX_CAT_G1V2", "CUST_AZ12", "LOC_A101"} <= set(names)
    finally:
        client.close()
