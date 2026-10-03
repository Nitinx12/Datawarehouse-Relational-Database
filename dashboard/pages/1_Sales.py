import plotly.express as px
import streamlit as st
from lib import charts, filters, queries
from lib.charts import fmt_money, fmt_num, kpi_delta
from lib.db import connection_ok

st.set_page_config(page_title="Sales Trends", page_icon="📈", layout="wide")

ok = connection_ok()
filters.sidebar_status(ok)
if not ok:
    st.stop()

monthly = queries.load_monthly()
if monthly.empty:
    st.warning("analytics.report_sales_monthly returned no rows.")
    st.stop()

st.title("📈 Sales Trends")
st.caption(
    "Source: analytics.report_sales_monthly. Filter by order month in the sidebar."
)

start, end = filters.sidebar_month_range(monthly, "sales-range")
view = filters.filter_months(monthly, start, end)
if view.empty:
    st.warning("No months in the selected range.")
    st.stop()

revenue = float(view["total_revenue"].sum())
orders = int(view["order_count"].sum())
new_cust = int(view["new_customer_count"].sum())
aov = revenue / orders if orders else 0
rev_delta, rev_dir = kpi_delta(
    float(view.iloc[-1]["total_revenue"]), float(view.iloc[0]["total_revenue"])
)

kpi = st.columns(4)
kpi[0].metric("Revenue in range", fmt_money(revenue), rev_delta, delta_color=rev_dir)
kpi[1].metric("Orders", fmt_num(orders))
kpi[2].metric("New customers", fmt_num(new_cust))
kpi[3].metric("Avg order value", fmt_money(aov))

st.plotly_chart(
    charts.area_trend(view, "order_month", "total_revenue", "Revenue by month"),
    use_container_width=True,
)

left, right = st.columns(2)
with left:
    fig = px.bar(
        view, x="order_month", y="new_customer_count", title="New customers per month"
    )
    st.plotly_chart(charts.style_fig(fig), use_container_width=True)
with right:
    fig = px.line(
        view,
        x="order_month",
        y="avg_order_revenue",
        title="Average order revenue",
        markers=True,
    )
    st.plotly_chart(charts.style_fig(fig), use_container_width=True)

growth = view[["order_month", "revenue_mom_pct"]].dropna()
fig = px.bar(
    growth,
    x="order_month",
    y="revenue_mom_pct",
    title="Month-over-month revenue growth (%)",
    color="revenue_mom_pct",
    color_continuous_scale=["#E76F51", "#F2F4F7", "#0E6E6E"],
)
st.plotly_chart(charts.style_fig(fig), use_container_width=True)

with st.expander("Monthly detail"):
    st.dataframe(view, use_container_width=True)
    filters.download_button(view, "sales_monthly.csv", "dl-sales")
