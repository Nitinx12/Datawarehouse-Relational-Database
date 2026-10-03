import streamlit as st
from lib import charts, filters, queries
from lib.charts import fmt_money, fmt_num, kpi_delta
from lib.db import connection_ok

st.set_page_config(page_title="Retail Overview", page_icon="🏠", layout="wide")

ok = connection_ok()
filters.sidebar_status(ok)
if not ok:
    st.stop()

monthly = queries.load_monthly()
categories = queries.load_categories()
products = queries.load_products()
customers = queries.load_customers()
if monthly.empty:
    st.warning("analytics.report_sales_monthly returned no rows.")
    st.stop()

st.title("🏠 Retail Performance Overview")
st.caption(
    "Live KPIs from the Postgres analytics layer (analytics.report_*). Use the sidebar on each page to filter."
)

total_revenue = float(monthly["total_revenue"].sum())
total_orders = int(monthly["order_count"].sum())
total_customers = int(monthly["customer_count"].sum())
avg_order = total_revenue / total_orders if total_orders else 0
last, prev = (
    monthly.iloc[-1],
    monthly.iloc[-2] if len(monthly) > 1 else monthly.iloc[-1],
)

rev_delta, rev_dir = kpi_delta(
    float(last["total_revenue"]), float(prev["total_revenue"])
)
ord_delta, ord_dir = kpi_delta(float(last["order_count"]), float(prev["order_count"]))

kpi = st.columns(4)
kpi[0].metric("Total revenue", fmt_money(total_revenue), rev_delta, delta_color=rev_dir)
kpi[1].metric("Total orders", fmt_num(total_orders), ord_delta, delta_color=ord_dir)
kpi[2].metric("Active customers", fmt_num(total_customers))
kpi[3].metric("Avg order value", fmt_money(avg_order))
st.caption(
    f"Latest month {last['order_month'].strftime('%Y-%m')}: {fmt_money(float(last['total_revenue']))} across {int(last['order_count']):,} orders."
)

left, right = st.columns(2)
with left:
    st.plotly_chart(
        charts.area_trend(monthly, "order_month", "total_revenue", "Revenue trend"),
        use_container_width=True,
    )
with right:
    st.plotly_chart(
        charts.area_trend(
            monthly, "order_month", "order_count", "Order volume trend", color="#2A9D8F"
        ),
        use_container_width=True,
    )

left, right = st.columns(2)
with left:
    by_cat = categories.groupby("category", as_index=False)["total_revenue"].sum()
    st.plotly_chart(
        charts.donut(by_cat, "category", "total_revenue", "Revenue share by category"),
        use_container_width=True,
    )
with right:
    top_sub = categories.nlargest(8, "total_revenue")
    st.plotly_chart(
        charts.hbar(
            top_sub, "total_revenue", "subcategory", "Top subcategories by revenue"
        ),
        use_container_width=True,
    )

st.subheader("Customer & product mix")
left, right = st.columns(2)
with left:
    seg = customers.groupby("customer_segment", as_index=False)["total_sales"].sum()
    st.plotly_chart(
        charts.donut(
            seg, "customer_segment", "total_sales", "Revenue by customer segment"
        ),
        use_container_width=True,
    )
with right:
    seg = products.groupby("product_segment", as_index=False)["total_sales"].sum()
    st.plotly_chart(
        charts.donut(
            seg, "product_segment", "total_sales", "Revenue by product segment"
        ),
        use_container_width=True,
    )

with st.expander("Monthly detail"):
    st.dataframe(monthly, use_container_width=True)
    filters.download_button(monthly, "monthly_overview.csv", "dl-overview")
