# rebuilds the GX file project with per-layer gates plus a master gate
import shutil
from pathlib import Path

import great_expectations as gx
from great_expectations.expectations import (
    ExpectColumnValuesToBeBetween,
    ExpectColumnValuesToBeInSet,
    ExpectColumnValuesToBeUnique,
    ExpectColumnValuesToNotBeNull,
    ExpectTableColumnsToMatchOrderedList,
    ExpectTableRowCountToBeBetween,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
GX_DIR = PROJECT_DIR / "gx"
DATASOURCE_NAME = "warehouse_frames"
LAYERS = ["source", "staging", "warehouse", "analytics"]
MASTER_CHECKPOINT = "master_layer"
GENERATED_OBJECT_DIRECTORIES = (
    "checkpoints",
    "expectations",
    "validation_definitions",
)


# structural gate shared by every table
def shaped(columns: list[str]) -> list:
    return [
        ExpectTableRowCountToBeBetween(min_value=1),
        ExpectTableColumnsToMatchOrderedList(column_list=columns),
    ]


# not-null gate for one merge or business key
def not_null(column: str) -> ExpectColumnValuesToNotBeNull:
    return ExpectColumnValuesToNotBeNull(column=column)


# uniqueness gate for one merge or business key
def unique(column: str) -> ExpectColumnValuesToBeUnique:
    return ExpectColumnValuesToBeUnique(column=column)


# non-negative measure gate shared by money and quantity columns
def non_negative(column: str) -> ExpectColumnValuesToBeBetween:
    return ExpectColumnValuesToBeBetween(column=column, min_value=0)


# source tables with key presence and raw range guards
def source_specs() -> dict[str, dict]:
    return {
        "source_cust_az12": {
            "layer": "source",
            "query": 'SELECT "BDATE" AS bdate, "CID" AS cid, "GEN" AS gen, updated_at, id, _loaded_at FROM source."CUST_AZ12"',
            "columns": ["bdate", "cid", "gen", "updated_at", "id", "_loaded_at"],
            "expectations": shaped(
                ["bdate", "cid", "gen", "updated_at", "id", "_loaded_at"]
            )
            + [
                not_null("cid"),
                not_null("id"),
                not_null("_loaded_at"),
            ],
        },
        "source_loc_a101": {
            "layer": "source",
            "query": 'SELECT "CID" AS cid, "CNTRY" AS cntry, updated_at, id, _loaded_at FROM source."LOC_A101"',
            "columns": ["cid", "cntry", "updated_at", "id", "_loaded_at"],
            "expectations": shaped(["cid", "cntry", "updated_at", "id", "_loaded_at"])
            + [
                not_null("cid"),
                not_null("id"),
                not_null("_loaded_at"),
            ],
        },
        "source_px_cat_g1v2": {
            "layer": "source",
            "query": 'SELECT "CAT" AS cat, id, "MAINTENANCE" AS maintenance, "SUBCAT" AS subcat, updated_at, _loaded_at FROM source."PX_CAT_G1V2"',
            "columns": [
                "cat",
                "id",
                "maintenance",
                "subcat",
                "updated_at",
                "_loaded_at",
            ],
            "expectations": shaped(
                ["cat", "id", "maintenance", "subcat", "updated_at", "_loaded_at"]
            )
            + [
                not_null("id"),
                not_null("cat"),
                not_null("subcat"),
                not_null("_loaded_at"),
            ],
        },
        "source_cust_info": {
            "layer": "source",
            "query": "SELECT cst_id, cst_key, cst_firstname, cst_lastname, cst_marital_status, cst_gndr, cst_create_date, updated_at, _loaded_at FROM source.cust_info",
            "columns": [
                "cst_id",
                "cst_key",
                "cst_firstname",
                "cst_lastname",
                "cst_marital_status",
                "cst_gndr",
                "cst_create_date",
                "updated_at",
                "_loaded_at",
            ],
            "expectations": shaped(
                [
                    "cst_id",
                    "cst_key",
                    "cst_firstname",
                    "cst_lastname",
                    "cst_marital_status",
                    "cst_gndr",
                    "cst_create_date",
                    "updated_at",
                    "_loaded_at",
                ]
            )
            + [
                ExpectColumnValuesToNotBeNull(column="cst_id", mostly=0.999),
                not_null("cst_key"),
                not_null("_loaded_at"),
            ],
        },
        "source_etl_logs": {
            "layer": "source",
            "query": "SELECT id, job_name, collection_name, target_schema, target_table, mode, watermark_column, watermark_from, watermark_to, rows_extracted, rows_loaded, chunks, status, error_message, started_at, finished_at, duration_seconds, run_id, rows_inserted, rows_updated, validation_status, validation_detail FROM source.etl_logs",
            "columns": [
                "id",
                "job_name",
                "collection_name",
                "target_schema",
                "target_table",
                "mode",
                "watermark_column",
                "watermark_from",
                "watermark_to",
                "rows_extracted",
                "rows_loaded",
                "chunks",
                "status",
                "error_message",
                "started_at",
                "finished_at",
                "duration_seconds",
                "run_id",
                "rows_inserted",
                "rows_updated",
                "validation_status",
                "validation_detail",
            ],
            "expectations": shaped(
                [
                    "id",
                    "job_name",
                    "collection_name",
                    "target_schema",
                    "target_table",
                    "mode",
                    "watermark_column",
                    "watermark_from",
                    "watermark_to",
                    "rows_extracted",
                    "rows_loaded",
                    "chunks",
                    "status",
                    "error_message",
                    "started_at",
                    "finished_at",
                    "duration_seconds",
                    "run_id",
                    "rows_inserted",
                    "rows_updated",
                    "validation_status",
                    "validation_detail",
                ]
            )
            + [
                not_null("job_name"),
                not_null("status"),
                not_null("started_at"),
                non_negative("rows_extracted"),
                non_negative("rows_loaded"),
                non_negative("duration_seconds"),
            ],
        },
        "source_prd_info": {
            "layer": "source",
            "query": "SELECT prd_id, prd_key, prd_nm, prd_cost, prd_line, prd_start_dt, prd_end_dt, updated_at, _loaded_at FROM source.prd_info",
            "columns": [
                "prd_id",
                "prd_key",
                "prd_nm",
                "prd_cost",
                "prd_line",
                "prd_start_dt",
                "prd_end_dt",
                "updated_at",
                "_loaded_at",
            ],
            "expectations": shaped(
                [
                    "prd_id",
                    "prd_key",
                    "prd_nm",
                    "prd_cost",
                    "prd_line",
                    "prd_start_dt",
                    "prd_end_dt",
                    "updated_at",
                    "_loaded_at",
                ]
            )
            + [
                not_null("prd_id"),
                not_null("prd_key"),
                not_null("_loaded_at"),
            ],
        },
        "source_sales_details": {
            "layer": "source",
            "query": "SELECT sls_ord_num, sls_prd_key, sls_cust_id, sls_order_dt, sls_ship_dt, sls_due_dt, sls_sales, sls_quantity, sls_price, updated_at, _loaded_at FROM source.sales_details",
            "columns": [
                "sls_ord_num",
                "sls_prd_key",
                "sls_cust_id",
                "sls_order_dt",
                "sls_ship_dt",
                "sls_due_dt",
                "sls_sales",
                "sls_quantity",
                "sls_price",
                "updated_at",
                "_loaded_at",
            ],
            "expectations": shaped(
                [
                    "sls_ord_num",
                    "sls_prd_key",
                    "sls_cust_id",
                    "sls_order_dt",
                    "sls_ship_dt",
                    "sls_due_dt",
                    "sls_sales",
                    "sls_quantity",
                    "sls_price",
                    "updated_at",
                    "_loaded_at",
                ]
            )
            + [
                not_null("sls_ord_num"),
                not_null("sls_prd_key"),
                not_null("sls_cust_id"),
                not_null("_loaded_at"),
            ],
        },
    }


# staging tables with key, domain, measure, and timestamp guards
def staging_specs() -> dict[str, dict]:
    return {
        "staging_cust_az12": {
            "layer": "staging",
            "query": "SELECT cid, birthdate, gender, updated_at, loaded_at FROM staging.cust_az12",
            "columns": ["cid", "birthdate", "gender", "updated_at", "loaded_at"],
            "expectations": shaped(
                ["cid", "birthdate", "gender", "updated_at", "loaded_at"]
            )
            + [
                not_null("cid"),
                unique("cid"),
                not_null("loaded_at"),
                ExpectColumnValuesToBeInSet(
                    column="gender", value_set=["Male", "Female", "n/a"]
                ),
            ],
        },
        "staging_cust_info": {
            "layer": "staging",
            "query": "SELECT cst_id, cst_key, cst_first_name, cst_last_name, cst_marital_status, cst_gndr, create_date, updated_at, loaded_at FROM staging.cust_info",
            "columns": [
                "cst_id",
                "cst_key",
                "cst_first_name",
                "cst_last_name",
                "cst_marital_status",
                "cst_gndr",
                "create_date",
                "updated_at",
                "loaded_at",
            ],
            "expectations": shaped(
                [
                    "cst_id",
                    "cst_key",
                    "cst_first_name",
                    "cst_last_name",
                    "cst_marital_status",
                    "cst_gndr",
                    "create_date",
                    "updated_at",
                    "loaded_at",
                ]
            )
            + [
                not_null("cst_id"),
                unique("cst_id"),
                not_null("cst_key"),
                not_null("loaded_at"),
                ExpectColumnValuesToBeInSet(
                    column="cst_marital_status",
                    value_set=["Single", "Married", "n/a"],
                ),
                ExpectColumnValuesToBeInSet(
                    column="cst_gndr", value_set=["Female", "Male", "n/a"]
                ),
            ],
        },
        "staging_loc_a101": {
            "layer": "staging",
            "query": "SELECT cid, cntry, updated_at, loaded_at FROM staging.loc_a101",
            "columns": ["cid", "cntry", "updated_at", "loaded_at"],
            "expectations": shaped(["cid", "cntry", "updated_at", "loaded_at"])
            + [
                not_null("cid"),
                unique("cid"),
                not_null("cntry"),
                not_null("loaded_at"),
                ExpectColumnValuesToBeInSet(
                    column="cntry",
                    value_set=[
                        "United States",
                        "United Kingdom",
                        "Germany",
                        "France",
                        "Canada",
                        "Australia",
                        '{"$numberDouble": "NaN"}',
                        "n/a",
                    ],
                ),
            ],
        },
        "staging_prd_info": {
            "layer": "staging",
            "query": "SELECT prd_id, prd_key, prd_nm, prd_cost, prd_line, start_date, end_date, updated_at, loaded_at, cat_id FROM staging.prd_info",
            "columns": [
                "prd_id",
                "prd_key",
                "prd_nm",
                "prd_cost",
                "prd_line",
                "start_date",
                "end_date",
                "updated_at",
                "loaded_at",
                "cat_id",
            ],
            "expectations": shaped(
                [
                    "prd_id",
                    "prd_key",
                    "prd_nm",
                    "prd_cost",
                    "prd_line",
                    "start_date",
                    "end_date",
                    "updated_at",
                    "loaded_at",
                    "cat_id",
                ]
            )
            + [
                not_null("prd_id"),
                unique("prd_id"),
                not_null("prd_key"),
                not_null("loaded_at"),
                non_negative("prd_cost"),
                ExpectColumnValuesToBeInSet(
                    column="prd_line",
                    value_set=["Mountain", "Road", "Other Sales", "Touring", "n/a"],
                ),
            ],
        },
        "staging_px_cat_g1v2": {
            "layer": "staging",
            "query": "SELECT id, cat, subcat, maintenance, updated_at, loaded_at FROM staging.px_cat_g1v2",
            "columns": [
                "id",
                "cat",
                "subcat",
                "maintenance",
                "updated_at",
                "loaded_at",
            ],
            "expectations": shaped(
                ["id", "cat", "subcat", "maintenance", "updated_at", "loaded_at"]
            )
            + [
                not_null("id"),
                unique("id"),
                not_null("cat"),
                not_null("subcat"),
                not_null("loaded_at"),
            ],
        },
        "staging_sales_details": {
            "layer": "staging",
            "query": "SELECT sls_ord_num, sls_prd_key, sls_cust_id, sls_order_dt, sls_ship_dt, sls_due_dt, sls_sales, sls_quantity, sls_price, updated_at, loaded_at FROM staging.sales_details",
            "columns": [
                "sls_ord_num",
                "sls_prd_key",
                "sls_cust_id",
                "sls_order_dt",
                "sls_ship_dt",
                "sls_due_dt",
                "sls_sales",
                "sls_quantity",
                "sls_price",
                "updated_at",
                "loaded_at",
            ],
            "expectations": shaped(
                [
                    "sls_ord_num",
                    "sls_prd_key",
                    "sls_cust_id",
                    "sls_order_dt",
                    "sls_ship_dt",
                    "sls_due_dt",
                    "sls_sales",
                    "sls_quantity",
                    "sls_price",
                    "updated_at",
                    "loaded_at",
                ]
            )
            + [
                not_null("sls_ord_num"),
                not_null("sls_prd_key"),
                not_null("sls_cust_id"),
                not_null("loaded_at"),
                non_negative("sls_sales"),
                ExpectColumnValuesToBeBetween(column="sls_quantity", min_value=1),
                non_negative("sls_price"),
            ],
        },
    }


# warehouse dimensions and fact with key, domain, and measure checks
def warehouse_specs() -> dict[str, dict]:
    return {
        "warehouse_dim_customers": {
            "layer": "warehouse",
            "query": "SELECT customer_sk, customer_key, cst_id, first_name, last_name, marital_status, gender, birthdate, country, create_date, updated_at FROM warehouse.dim_customers",
            "columns": [
                "customer_sk",
                "customer_key",
                "cst_id",
                "first_name",
                "last_name",
                "marital_status",
                "gender",
                "birthdate",
                "country",
                "create_date",
                "updated_at",
            ],
            "expectations": shaped(
                [
                    "customer_sk",
                    "customer_key",
                    "cst_id",
                    "first_name",
                    "last_name",
                    "marital_status",
                    "gender",
                    "birthdate",
                    "country",
                    "create_date",
                    "updated_at",
                ]
            )
            + [
                not_null("customer_sk"),
                unique("customer_sk"),
                not_null("customer_key"),
                unique("customer_key"),
                not_null("updated_at"),
                ExpectColumnValuesToBeInSet(
                    column="gender", value_set=["Female", "Male", "n/a"]
                ),
                ExpectColumnValuesToBeInSet(
                    column="marital_status",
                    value_set=["Single", "Married", "n/a"],
                ),
            ],
        },
        "warehouse_dim_products": {
            "layer": "warehouse",
            "query": "SELECT product_sk, product_id, product_number, product_name, category_id, category, subcategory, maintenance, cost, product_line, start_date, end_date, updated_at FROM warehouse.dim_products",
            "columns": [
                "product_sk",
                "product_id",
                "product_number",
                "product_name",
                "category_id",
                "category",
                "subcategory",
                "maintenance",
                "cost",
                "product_line",
                "start_date",
                "end_date",
                "updated_at",
            ],
            "expectations": shaped(
                [
                    "product_sk",
                    "product_id",
                    "product_number",
                    "product_name",
                    "category_id",
                    "category",
                    "subcategory",
                    "maintenance",
                    "cost",
                    "product_line",
                    "start_date",
                    "end_date",
                    "updated_at",
                ]
            )
            + [
                not_null("product_sk"),
                unique("product_sk"),
                not_null("product_id"),
                unique("product_id"),
                not_null("product_number"),
                not_null("updated_at"),
                non_negative("cost"),
                ExpectColumnValuesToBeInSet(
                    column="product_line",
                    value_set=["Mountain", "Road", "Other Sales", "Touring", "n/a"],
                ),
            ],
        },
        "warehouse_fact_sales": {
            "layer": "warehouse",
            "query": "SELECT order_number, product_key, customer_key, order_date, shipping_date, due_date, sales_amount, quantity, price FROM warehouse.fact_sales",
            "columns": [
                "order_number",
                "product_key",
                "customer_key",
                "order_date",
                "shipping_date",
                "due_date",
                "sales_amount",
                "quantity",
                "price",
            ],
            "expectations": shaped(
                [
                    "order_number",
                    "product_key",
                    "customer_key",
                    "order_date",
                    "shipping_date",
                    "due_date",
                    "sales_amount",
                    "quantity",
                    "price",
                ]
            )
            + [
                not_null("order_number"),
                not_null("product_key"),
                not_null("customer_key"),
                non_negative("sales_amount"),
                ExpectColumnValuesToBeBetween(column="quantity", min_value=1),
                non_negative("price"),
            ],
        },
    }


# analytics marts with segment, KPI, and share checks
def analytics_specs() -> dict[str, dict]:
    return {
        "analytics_report_customers": {
            "layer": "analytics",
            "query": "SELECT customer_sk, customer_key, cst_id, customer_name, birthdate, age, last_order_date, total_orders, total_sales, total_quantity, total_products, lifespan_months, age_group, customer_segment, recency_months, avg_order_value, avg_monthly_spend FROM analytics.report_customers",
            "columns": [
                "customer_sk",
                "customer_key",
                "cst_id",
                "customer_name",
                "birthdate",
                "age",
                "last_order_date",
                "total_orders",
                "total_sales",
                "total_quantity",
                "total_products",
                "lifespan_months",
                "age_group",
                "customer_segment",
                "recency_months",
                "avg_order_value",
                "avg_monthly_spend",
            ],
            "expectations": shaped(
                [
                    "customer_sk",
                    "customer_key",
                    "cst_id",
                    "customer_name",
                    "birthdate",
                    "age",
                    "last_order_date",
                    "total_orders",
                    "total_sales",
                    "total_quantity",
                    "total_products",
                    "lifespan_months",
                    "age_group",
                    "customer_segment",
                    "recency_months",
                    "avg_order_value",
                    "avg_monthly_spend",
                ]
            )
            + [
                not_null("customer_sk"),
                unique("customer_sk"),
                not_null("customer_key"),
                ExpectColumnValuesToBeInSet(
                    column="customer_segment", value_set=["VIP", "Regular", "New"]
                ),
                ExpectColumnValuesToBeInSet(
                    column="age_group",
                    value_set=["Under 20", "20-29", "30-39", "40-49", "50 and above"],
                ),
                ExpectColumnValuesToBeBetween(column="total_orders", min_value=1),
                non_negative("total_sales"),
                non_negative("lifespan_months"),
                non_negative("recency_months"),
                non_negative("avg_order_value"),
                non_negative("avg_monthly_spend"),
            ],
        },
        "analytics_report_products": {
            "layer": "analytics",
            "query": "SELECT product_sk, product_number, product_name, category, subcategory, cost, last_sale_date, lifespan_months, total_orders, total_sales, total_quantity, total_customers, avg_selling_price, product_segment, recency_months, avg_order_revenue, avg_monthly_revenue FROM analytics.report_products",
            "columns": [
                "product_sk",
                "product_number",
                "product_name",
                "category",
                "subcategory",
                "cost",
                "last_sale_date",
                "lifespan_months",
                "total_orders",
                "total_sales",
                "total_quantity",
                "total_customers",
                "avg_selling_price",
                "product_segment",
                "recency_months",
                "avg_order_revenue",
                "avg_monthly_revenue",
            ],
            "expectations": shaped(
                [
                    "product_sk",
                    "product_number",
                    "product_name",
                    "category",
                    "subcategory",
                    "cost",
                    "last_sale_date",
                    "lifespan_months",
                    "total_orders",
                    "total_sales",
                    "total_quantity",
                    "total_customers",
                    "avg_selling_price",
                    "product_segment",
                    "recency_months",
                    "avg_order_revenue",
                    "avg_monthly_revenue",
                ]
            )
            + [
                not_null("product_sk"),
                unique("product_sk"),
                not_null("product_number"),
                ExpectColumnValuesToBeInSet(
                    column="product_segment",
                    value_set=["High-Performer", "Mid-Range", "Low-Performer"],
                ),
                ExpectColumnValuesToBeBetween(column="total_orders", min_value=1),
                non_negative("total_sales"),
                ExpectColumnValuesToBeBetween(column="total_customers", min_value=1),
                non_negative("lifespan_months"),
                non_negative("avg_order_revenue"),
                non_negative("avg_monthly_revenue"),
            ],
        },
        "analytics_report_monthly": {
            "layer": "analytics",
            "query": "SELECT order_month, line_count, order_count, customer_count, product_count, total_revenue, total_quantity, new_customer_count, avg_order_revenue FROM analytics.report_sales_monthly",
            "columns": [
                "order_month",
                "line_count",
                "order_count",
                "customer_count",
                "product_count",
                "total_revenue",
                "total_quantity",
                "new_customer_count",
                "avg_order_revenue",
            ],
            "expectations": shaped(
                [
                    "order_month",
                    "line_count",
                    "order_count",
                    "customer_count",
                    "product_count",
                    "total_revenue",
                    "total_quantity",
                    "new_customer_count",
                    "avg_order_revenue",
                ]
            )
            + [
                not_null("order_month"),
                unique("order_month"),
                ExpectColumnValuesToBeBetween(column="order_count", min_value=1),
                ExpectColumnValuesToBeBetween(column="line_count", min_value=1),
                ExpectColumnValuesToBeBetween(column="customer_count", min_value=1),
                ExpectColumnValuesToBeBetween(column="product_count", min_value=1),
                non_negative("total_revenue"),
                non_negative("new_customer_count"),
                non_negative("avg_order_revenue"),
            ],
        },
        "analytics_report_category": {
            "layer": "analytics",
            "query": "SELECT category, subcategory, product_count, order_count, customer_count, total_revenue, total_quantity, last_sale_date, avg_order_revenue, percentage_of_total FROM analytics.report_category_sales",
            "columns": [
                "category",
                "subcategory",
                "product_count",
                "order_count",
                "customer_count",
                "total_revenue",
                "total_quantity",
                "last_sale_date",
                "avg_order_revenue",
                "percentage_of_total",
            ],
            "expectations": shaped(
                [
                    "category",
                    "subcategory",
                    "product_count",
                    "order_count",
                    "customer_count",
                    "total_revenue",
                    "total_quantity",
                    "last_sale_date",
                    "avg_order_revenue",
                    "percentage_of_total",
                ]
            )
            + [
                not_null("category"),
                not_null("subcategory"),
                ExpectColumnValuesToBeBetween(column="order_count", min_value=1),
                non_negative("total_revenue"),
                non_negative("avg_order_revenue"),
                ExpectColumnValuesToBeBetween(
                    column="percentage_of_total", min_value=0, max_value=100
                ),
            ],
        },
        "analytics_monthly_snapshot": {
            "layer": "analytics",
            "query": "SELECT snapshot_month, order_count, line_count, total_revenue, total_quantity, customer_count, product_count, new_customer_count, avg_order_revenue, loaded_at FROM analytics.monthly_kpi_snapshot",
            "columns": [
                "snapshot_month",
                "order_count",
                "line_count",
                "total_revenue",
                "total_quantity",
                "customer_count",
                "product_count",
                "new_customer_count",
                "avg_order_revenue",
                "loaded_at",
            ],
            "expectations": shaped(
                [
                    "snapshot_month",
                    "order_count",
                    "line_count",
                    "total_revenue",
                    "total_quantity",
                    "customer_count",
                    "product_count",
                    "new_customer_count",
                    "avg_order_revenue",
                    "loaded_at",
                ]
            )
            + [
                not_null("snapshot_month"),
                unique("snapshot_month"),
                ExpectColumnValuesToBeBetween(column="order_count", min_value=1),
                ExpectColumnValuesToBeBetween(column="line_count", min_value=1),
                ExpectColumnValuesToBeBetween(column="customer_count", min_value=1),
                non_negative("total_revenue"),
                not_null("loaded_at"),
            ],
        },
    }


# merges every layer spec table into one asset map
def table_specs() -> dict[str, dict]:
    return {
        **source_specs(),
        **staging_specs(),
        **warehouse_specs(),
        **analytics_specs(),
    }


# tables belonging to one layer in spec order
def layer_tables(specs: dict[str, dict], layer: str) -> list[str]:
    return [name for name, spec in specs.items() if spec["layer"] == layer]


# removes GX objects that are regenerated from the table specs
def clear_generated_objects() -> None:
    for directory in GENERATED_OBJECT_DIRECTORIES:
        generated_path = GX_DIR / directory
        if generated_path.exists():
            shutil.rmtree(generated_path)


# rebuilds every GX project object from the specs above
def build() -> None:
    clear_generated_objects()
    context = gx.get_context(mode="file", project_root_dir=str(PROJECT_DIR))
    if DATASOURCE_NAME in context.data_sources.all():
        context.data_sources.delete(DATASOURCE_NAME)
    datasource = context.data_sources.add_pandas(DATASOURCE_NAME)
    specs = table_specs()
    for name, spec in specs.items():
        asset = datasource.add_dataframe_asset(name=name)
        batch_definition = asset.add_batch_definition_whole_dataframe(f"{name}_batch")
        suite = gx.ExpectationSuite(name=f"{name}_suite")
        for expectation in spec["expectations"]:
            suite.add_expectation(expectation)
        context.suites.add(suite)
        validation = gx.ValidationDefinition(
            name=f"{name}_validation",
            data=batch_definition,
            suite=suite,
        )
        context.validation_definitions.add(validation)
    for layer in LAYERS:
        layer_validations = [
            context.validation_definitions.get(f"{name}_validation")
            for name in layer_tables(specs, layer)
        ]
        checkpoint = gx.Checkpoint(
            name=f"{layer}_layer",
            validation_definitions=layer_validations,
        )
        context.checkpoints.add(checkpoint)
    master_validations = [
        context.validation_definitions.get(f"{name}_validation") for name in specs
    ]
    context.checkpoints.add(
        gx.Checkpoint(
            name=MASTER_CHECKPOINT,
            validation_definitions=master_validations,
        )
    )
    print(
        f"gx project ready: {len(specs)} validations in "
        f"{len(LAYERS)} layer checkpoints plus {MASTER_CHECKPOINT}"
    )


if __name__ == "__main__":
    build()
