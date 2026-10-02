-- ===========================================================================
-- Analysis : retention and churn analysis
-- Purpose : snapshots lifecycle status using 3 and 6 month inactivity thresholds.
-- Run : psql -d datawarehouse -f sql/analytics/analysis/retention_churn_analysis.sql
-- ===========================================================================

-- ===========================================================================
-- Customer counts and rates by lifecycle status as of the latest order date.
-- ===========================================================================
WITH bounds AS (
    SELECT
        MAX(fact_sales.order_date)::DATE AS max_order_date
    FROM warehouse.fact_sales AS fact_sales
),

customer_recency AS (
    SELECT
        fact_sales.customer_key,
        MIN(fact_sales.order_date)::DATE AS first_order_date,
        MAX(fact_sales.order_date)::DATE AS last_order_date,
        COUNT(DISTINCT fact_sales.order_number) AS total_orders,
        (
            DATE_PART('year', AGE(bounds.max_order_date, MAX(fact_sales.order_date))) * 12
            + DATE_PART('month', AGE(bounds.max_order_date, MAX(fact_sales.order_date)))
        )::INT AS months_since_last_order,
        (
            DATE_PART('year', AGE(bounds.max_order_date, MIN(fact_sales.order_date))) * 12
            + DATE_PART('month', AGE(bounds.max_order_date, MIN(fact_sales.order_date)))
        )::INT AS months_since_first_order
    FROM warehouse.fact_sales AS fact_sales
    CROSS JOIN bounds
    WHERE fact_sales.order_date IS NOT NULL
        AND fact_sales.customer_key IS NOT NULL

    GROUP BY
        fact_sales.customer_key,
        bounds.max_order_date
),

customer_status AS (
    SELECT
        customer_recency.customer_key,
        CASE
            WHEN customer_recency.months_since_first_order < 3 THEN 'New'
            WHEN customer_recency.months_since_last_order > 6 THEN 'Churned'
            WHEN customer_recency.months_since_last_order > 3 THEN 'Dormant'
            ELSE 'Active'
        END AS customer_status
    FROM customer_recency
)

SELECT
    customer_status.customer_status,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER () * 100, 1) AS pct_of_customers
FROM customer_status

GROUP BY
    customer_status.customer_status

ORDER BY
    customer_count DESC;

-- ===========================================================================
-- Repeat customer rate across all customers with known identity.
-- ===========================================================================
WITH customer_orders AS (
    SELECT
        fact_sales.customer_key,
        COUNT(DISTINCT fact_sales.order_number) AS total_orders
    FROM warehouse.fact_sales AS fact_sales
    WHERE fact_sales.customer_key IS NOT NULL

    GROUP BY
        fact_sales.customer_key
)

SELECT
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE customer_orders.total_orders > 1) AS repeat_customers,
    ROUND(COUNT(*) FILTER (WHERE customer_orders.total_orders > 1)::NUMERIC / COUNT(*) * 100, 1) AS repeat_rate_pct
FROM customer_orders;

-- ===========================================================================
-- Resurrected customers ordered recently after a gap above 180 days.
-- ===========================================================================
WITH bounds AS (
    SELECT
        MAX(fact_sales.order_date)::DATE AS max_order_date
    FROM warehouse.fact_sales AS fact_sales
),

ordered_purchases AS (
    SELECT DISTINCT
        fact_sales.customer_key,
        fact_sales.order_date::DATE AS order_day
    FROM warehouse.fact_sales AS fact_sales
    WHERE fact_sales.order_date IS NOT NULL
        AND fact_sales.customer_key IS NOT NULL
),

purchase_gaps AS (
    SELECT
        ordered_purchases.customer_key,
        ordered_purchases.order_day,
        ordered_purchases.order_day - LAG(ordered_purchases.order_day) OVER (
            PARTITION BY ordered_purchases.customer_key
            ORDER BY ordered_purchases.order_day
        ) AS gap_days
    FROM ordered_purchases
),

resurrected_customers AS (
    SELECT
        purchase_gaps.customer_key
    FROM purchase_gaps
    CROSS JOIN bounds

    GROUP BY
        purchase_gaps.customer_key,
        bounds.max_order_date

    HAVING MAX(purchase_gaps.order_day) > bounds.max_order_date - 90
        AND MAX(purchase_gaps.gap_days) > 180
)

SELECT
    COUNT(*) AS resurrected_customers
FROM resurrected_customers;
