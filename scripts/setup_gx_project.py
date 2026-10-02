"""Rebuilds the GX file project: one checkpoint per layer, one validation per table."""

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
GENERATED_OBJECT_DIRECTORIES = (
    "checkpoints",
    "expectations",
    "validation_definitions",
)


# structural gate shared by every table: rows exist and columns match exactly
def shaped(columns: list[str]) -> list:
    return [
        ExpectTableRowCountToBeBetween(min_value=1),
        ExpectTableColumnsToMatchOrderedList(column_list=columns),
    ]


# source tables: structural gates over raw landed frames
def source_specs() -> dict[str, dict]:
    return {
        "source_cust_az12": {
            "layer": "source",
            "query": 'SELECT "BDATE" AS bdate, "CID" AS cid, "GEN" AS gen, updated_at, id, _loaded_at FROM source."CUST_AZ12"',
            "columns": ["bdate", "cid", "gen", "updated_at", "id", "_loaded_at"],
            "expectations": shaped(
                ["bdate", "cid", "gen", "updated_at", "id", "_loaded_at"]
            ),
        },
        "source_loc_a101": {
            "layer": "source",
            "query": 'SELECT "CID" AS cid, "CNTRY" AS cntry, updated_at, id, _loaded_at FROM source."LOC_A101"',
            "columns": ["cid", "cntry", "updated_at", "id", "_loaded_at"],
            "expectations": shaped(["cid", "cntry", "updated_at", "id", "_loaded_at"]),
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
            ),
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
            ),
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
            ),
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
            ),
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
            ),
        },
    }


# staging tables: structural gates plus load-guaranteed value checks
def staging_specs() -> dict[str, dict]:
    return {
        "staging_cust_az12": {
            "layer": "staging",
            "query": "SELECT cid, birthdate, gender, updated_at, loaded_at FROM staging.cust_az12",
            "columns": ["cid", "birthdate", "gender", "updated_at", "loaded_at"],
            "expectations": shaped(
                ["cid", "birthdate", "gender", "updated_at", "loaded_at"]
            ),
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
            + [ExpectColumnValuesToNotBeNull(column="cst_id")],
        },
        "staging_loc_a101": {
            "layer": "staging",
            "query": "SELECT cid, cntry, updated_at, loaded_at FROM staging.loc_a101",
            "columns": ["cid", "cntry", "updated_at", "loaded_at"],
            "expectations": shaped(["cid", "cntry", "updated_at", "loaded_at"]),
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
            ),
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
            ),
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
                ExpectColumnValuesToNotBeNull(column="sls_ord_num"),
                ExpectColumnValuesToBeBetween(column="sls_sales", min_value=0),
                ExpectColumnValuesToBeBetween(column="sls_quantity", min_value=0),
            ],
        },
    }


# warehouse dimensions and fact with key and measure checks
def warehouse_specs() -> dict[str, dict]:
    return {
        "warehouse_dim_customers": {
            "layer": "warehouse",
            "query": "SELECT customer_sk, customer_key, cst_id, first_name, last_name, marital_status, gender, birthdate, country, create_date FROM warehouse.dim_customers",
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
                ]
            )
            + [
                ExpectColumnValuesToNotBeNull(column="customer_key"),
                ExpectColumnValuesToBeUnique(column="customer_key"),
                ExpectColumnValuesToBeInSet(
                    column="gender", value_set=["Female", "Male", "n/a"]
                ),
            ],
        },
        "warehouse_dim_products": {
            "layer": "warehouse",
            "query": "SELECT product_sk, product_id, product_number, product_name, category_id, category, subcategory, maintenance, cost, product_line, start_date, end_date FROM warehouse.dim_products",
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
                ]
            )
            + [
                ExpectColumnValuesToNotBeNull(column="product_id"),
                ExpectColumnValuesToBeUnique(column="product_id"),
                ExpectColumnValuesToBeBetween(column="cost", min_value=0),
            ],
        },
        "warehouse_fact_sales": {
            "layer": "warehouse",
            "query": "SELECT order_number, product_key, customer_key, order_date, sales_amount, quantity, price FROM warehouse.fact_sales",
            "columns": [
                "order_number",
                "product_key",
                "customer_key",
                "order_date",
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
                    "sales_amount",
                    "quantity",
                    "price",
                ]
            )
            + [
                ExpectColumnValuesToBeBetween(column="sales_amount", min_value=0),
                ExpectColumnValuesToBeBetween(column="quantity", min_value=0),
                ExpectColumnValuesToBeBetween(column="price", min_value=0),
            ],
        },
    }


# analytics reports with segment and KPI checks
def analytics_specs() -> dict[str, dict]:
    return {
        "analytics_report_customers": {
            "layer": "analytics",
            "query": "SELECT customer_sk, customer_key, age, age_group, customer_segment, total_orders, total_sales, total_quantity, total_products, lifespan_months, recency_months, avg_order_value, avg_monthly_spend FROM analytics.report_customers",
            "columns": [
                "customer_sk",
                "customer_key",
                "age",
                "age_group",
                "customer_segment",
                "total_orders",
                "total_sales",
                "total_quantity",
                "total_products",
                "lifespan_months",
                "recency_months",
                "avg_order_value",
                "avg_monthly_spend",
            ],
            "expectations": shaped(
                [
                    "customer_sk",
                    "customer_key",
                    "age",
                    "age_group",
                    "customer_segment",
                    "total_orders",
                    "total_sales",
                    "total_quantity",
                    "total_products",
                    "lifespan_months",
                    "recency_months",
                    "avg_order_value",
                    "avg_monthly_spend",
                ]
            )
            + [
                ExpectColumnValuesToBeInSet(
                    column="customer_segment", value_set=["VIP", "Regular", "New"]
                ),
                ExpectColumnValuesToBeBetween(column="total_orders", min_value=1),
                ExpectColumnValuesToBeBetween(column="lifespan_months", min_value=0),
                ExpectColumnValuesToBeBetween(column="recency_months", min_value=0),
            ],
        },
        "analytics_report_products": {
            "layer": "analytics",
            "query": "SELECT product_sk, product_number, total_orders, total_sales, total_quantity, total_customers, avg_order_revenue, avg_monthly_revenue, product_segment, lifespan_months FROM analytics.report_products",
            "columns": [
                "product_sk",
                "product_number",
                "total_orders",
                "total_sales",
                "total_quantity",
                "total_customers",
                "avg_order_revenue",
                "avg_monthly_revenue",
                "product_segment",
                "lifespan_months",
            ],
            "expectations": shaped(
                [
                    "product_sk",
                    "product_number",
                    "total_orders",
                    "total_sales",
                    "total_quantity",
                    "total_customers",
                    "avg_order_revenue",
                    "avg_monthly_revenue",
                    "product_segment",
                    "lifespan_months",
                ]
            )
            + [
                ExpectColumnValuesToBeInSet(
                    column="product_segment",
                    value_set=["High-Performer", "Mid-Range", "Low-Performer"],
                ),
                ExpectColumnValuesToBeBetween(column="total_orders", min_value=1),
            ],
        },
        "analytics_report_monthly": {
            "layer": "analytics",
            "query": "SELECT order_month, order_count, customer_count, new_customer_count, total_revenue FROM analytics.report_sales_monthly",
            "columns": [
                "order_month",
                "order_count",
                "customer_count",
                "new_customer_count",
                "total_revenue",
            ],
            "expectations": shaped(
                [
                    "order_month",
                    "order_count",
                    "customer_count",
                    "new_customer_count",
                    "total_revenue",
                ]
            )
            + [
                ExpectColumnValuesToBeBetween(column="customer_count", min_value=1),
                ExpectColumnValuesToBeBetween(column="total_revenue", min_value=0),
            ],
        },
        "analytics_report_category": {
            "layer": "analytics",
            "query": "SELECT category, subcategory, total_revenue, percentage_of_total FROM analytics.report_category_sales",
            "columns": [
                "category",
                "subcategory",
                "total_revenue",
                "percentage_of_total",
            ],
            "expectations": shaped(
                ["category", "subcategory", "total_revenue", "percentage_of_total"]
            )
            + [
                ExpectColumnValuesToBeBetween(
                    column="percentage_of_total", min_value=0, max_value=100
                )
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
            for name, spec in specs.items()
            if spec["layer"] == layer
        ]
        checkpoint = gx.Checkpoint(
            name=f"{layer}_layer",
            validation_definitions=layer_validations,
        )
        context.checkpoints.add(checkpoint)
    print(
        f"gx project ready: {len(specs)} validations in {len(LAYERS)} layer checkpoints"
    )


if __name__ == "__main__":
    build()
