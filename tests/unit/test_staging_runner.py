import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from run_staging_load import PROCEDURES, parse_notice


def test_parse_notice_full_merge_counts():
    result = parse_notice(
        "staging.cust_info: staged=10 inserted=7 updated=3 null-key skipped=0"
    )
    assert result == {"staged": 10, "inserted": 7, "updated": 3, "skipped": 0}


def test_parse_notice_full_refresh_counts():
    result = parse_notice("staging.px_cat_g1v2: reloaded=37 rows")
    assert result == {"staged": 37, "inserted": 37, "updated": 0, "skipped": 0}


def test_parse_notice_garbage_counts_zero():
    assert parse_notice("something unexpected") == {
        "staged": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
    }


# parses warehouse dimension combined counts
def test_parse_notice_warehouse_combined():
    result = parse_notice("warehouse.dim_customers: combined=100 inserted=10 updated=5")
    assert result == {"staged": 100, "inserted": 10, "updated": 5, "skipped": 0}


# parses warehouse fact reload with orphan suffix
def test_parse_notice_warehouse_reloaded():
    result = parse_notice(
        "warehouse.fact_sales: reloaded=500 rows orphan_products=1 orphan_customers=2"
    )
    assert result == {"staged": 500, "inserted": 500, "updated": 0, "skipped": 0}


# parses analytics snapshot upsert counts
def test_parse_notice_analytics_upserted():
    result = parse_notice("analytics.monthly_kpi_snapshot: upserted=12 months")
    assert result == {"staged": 12, "inserted": 12, "updated": 0, "skipped": 0}


def test_procedures_follow_dependency_order():
    assert PROCEDURES.index("staging.load_px_cat_g1v2") < PROCEDURES.index(
        "staging.load_sales_details"
    )
    assert set(PROCEDURES) == {
        "staging.load_px_cat_g1v2",
        "staging.load_cust_info",
        "staging.load_prd_info",
        "staging.load_cust_az12",
        "staging.load_loc_a101",
        "staging.load_sales_details",
    }
