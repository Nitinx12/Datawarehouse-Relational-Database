-- ===========================================================================
-- Analysis : cohort analysis
-- Purpose : tracks retention and revenue by customer acquisition cohort.
-- Run : psql -d datawarehouse -f sql/analytics/analysis/cohort_analysis.sql
-- ===========================================================================

-- ===========================================================================
-- Customers acquired in each cohort month.
-- ===========================================================================
WITH customer_cohorts AS (
    SELECT
        fact_sales.customer_key,
        DATE_TRUNC('month', MIN(fact_sales.order_date))::DATE AS cohort_month
    FROM warehouse.fact_sales AS fact_sales
    WHERE fact_sales.order_date IS NOT NULL
        AND fact_sales.customer_key IS NOT NULL

    GROUP BY
        fact_sales.customer_key
)

SELECT
    customer_cohorts.cohort_month,
    COUNT(*) AS cohort_size
FROM customer_cohorts

GROUP BY
    customer_cohorts.cohort_month

ORDER BY
    customer_cohorts.cohort_month ASC;

-- ===========================================================================
-- Retention and revenue by cohort month and months since acquisition.
-- ===========================================================================
WITH customer_cohorts AS (
    SELECT
        fact_sales.customer_key,
        DATE_TRUNC('month', MIN(fact_sales.order_date))::DATE AS cohort_month
    FROM warehouse.fact_sales AS fact_sales
    WHERE fact_sales.order_date IS NOT NULL
        AND fact_sales.customer_key IS NOT NULL

    GROUP BY
        fact_sales.customer_key
),

cohort_sizes AS (
    SELECT
        customer_cohorts.cohort_month,
        COUNT(*) AS cohort_size
    FROM customer_cohorts

    GROUP BY
        customer_cohorts.cohort_month
),

cohort_activity AS (
    SELECT
        customer_cohorts.cohort_month,
        fact_sales.customer_key,
        fact_sales.order_number,
        fact_sales.sales_amount,
        (
            DATE_PART('year', AGE(DATE_TRUNC('month', fact_sales.order_date), customer_cohorts.cohort_month)) * 12
            + DATE_PART('month', AGE(DATE_TRUNC('month', fact_sales.order_date), customer_cohorts.cohort_month))
        )::INT AS cohort_age_months
    FROM warehouse.fact_sales AS fact_sales
    LEFT JOIN customer_cohorts
        ON fact_sales.customer_key = customer_cohorts.customer_key
    WHERE fact_sales.order_date IS NOT NULL
        AND fact_sales.customer_key IS NOT NULL
)

SELECT
    cohort_activity.cohort_month,
    cohort_activity.cohort_age_months,
    cohort_sizes.cohort_size,
    COUNT(DISTINCT cohort_activity.customer_key) AS active_customers,
    ROUND(COUNT(DISTINCT cohort_activity.customer_key)::NUMERIC / cohort_sizes.cohort_size * 100, 1) AS retention_pct,
    COUNT(DISTINCT cohort_activity.order_number) AS orders,
    SUM(cohort_activity.sales_amount) AS revenue
FROM cohort_activity
LEFT JOIN cohort_sizes
    ON cohort_activity.cohort_month = cohort_sizes.cohort_month

GROUP BY
    cohort_activity.cohort_month,
    cohort_activity.cohort_age_months,
    cohort_sizes.cohort_size

ORDER BY
    cohort_activity.cohort_month ASC,
    cohort_activity.cohort_age_months ASC;
