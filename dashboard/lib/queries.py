import pandas as pd

from .db import run_query


# monthly orders, revenue, and customer growth trend
def monthly_sql() -> str:
    return """
        SELECT
            order_month,
            line_count,
            order_count,
            customer_count,
            product_count,
            total_revenue,
            total_quantity,
            new_customer_count,
            avg_order_revenue
        FROM analytics.report_sales_monthly
        ORDER BY order_month
    """


# revenue and demand rolled up to category and subcategory
def category_sql() -> str:
    return """
        SELECT
            category,
            subcategory,
            product_count,
            order_count,
            customer_count,
            total_revenue,
            total_quantity,
            last_sale_date,
            avg_order_revenue,
            percentage_of_total
        FROM analytics.report_category_sales
        ORDER BY total_revenue DESC
    """


# lifetime kpis and segments per product
def products_sql() -> str:
    return """
        SELECT
            product_sk,
            product_number,
            product_name,
            category,
            subcategory,
            cost,
            last_sale_date,
            lifespan_months,
            total_orders,
            total_sales,
            total_quantity,
            total_customers,
            avg_selling_price,
            product_segment,
            recency_months,
            avg_order_revenue,
            avg_monthly_revenue
        FROM analytics.report_products
        ORDER BY total_sales DESC
    """


# lifetime kpis and segments per customer
def customers_sql() -> str:
    return """
        SELECT
            customer_sk,
            customer_key,
            cst_id,
            customer_name,
            birthdate,
            age,
            last_order_date,
            total_orders,
            total_sales,
            total_quantity,
            total_products,
            lifespan_months,
            age_group,
            customer_segment,
            recency_months,
            avg_order_value,
            avg_monthly_spend
        FROM analytics.report_customers
        ORDER BY total_sales DESC
    """


# loads any analytics query into a dataframe with numeric coercion
def load_frame(sql: str, numeric: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(run_query(sql))
    for column in numeric:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


# loads the monthly sales trend with month-over-month growth columns
def load_monthly() -> pd.DataFrame:
    frame = load_frame(
        monthly_sql(),
        [
            "line_count",
            "order_count",
            "customer_count",
            "product_count",
            "total_revenue",
            "total_quantity",
            "new_customer_count",
            "avg_order_revenue",
        ],
    )
    if not frame.empty:
        frame["order_month"] = pd.to_datetime(frame["order_month"])
        frame = frame.sort_values("order_month").reset_index(drop=True)
        frame["revenue_mom_pct"] = frame["total_revenue"].pct_change() * 100
        frame["orders_mom_pct"] = frame["order_count"].pct_change() * 100
    return frame


# loads the category and subcategory rollup
def load_categories() -> pd.DataFrame:
    return load_frame(
        category_sql(),
        [
            "product_count",
            "order_count",
            "customer_count",
            "total_revenue",
            "total_quantity",
            "avg_order_revenue",
            "percentage_of_total",
        ],
    )


# loads the product report
def load_products() -> pd.DataFrame:
    return load_frame(
        products_sql(),
        [
            "cost",
            "total_orders",
            "total_sales",
            "total_quantity",
            "total_customers",
            "avg_selling_price",
            "avg_order_revenue",
            "avg_monthly_revenue",
        ],
    )


# loads the customer report
def load_customers() -> pd.DataFrame:
    return load_frame(
        customers_sql(),
        [
            "age",
            "total_orders",
            "total_sales",
            "total_quantity",
            "total_products",
            "avg_order_value",
            "avg_monthly_spend",
        ],
    )
