import plotly.express as px
import streamlit as st
from lib import charts, filters, queries
from lib.charts import fmt_money, fmt_num
from lib.db import connection_ok

st.set_page_config(page_title="Customers", page_icon="👥", layout="wide")

ok = connection_ok()
filters.sidebar_status(ok)
if not ok:
    st.stop()

customers = queries.load_customers()
if customers.empty:
    st.warning("analytics.report_customers returned no rows.")
    st.stop()

st.title("👥 Customers")
st.caption("Source: analytics.report_customers (lifetime KPIs per customer).")

segs = filters.sidebar_multi(
    "Customer segment",
    sorted(customers["customer_segment"].dropna().unique()),
    "cust-seg",
)
ages = filters.sidebar_multi(
    "Age group", sorted(customers["age_group"].dropna().unique()), "cust-age"
)
with st.sidebar:
    top_n = st.slider("Top N customers", 5, 30, 10, key="cust-topn")
    search = st.text_input("Search customer name", key="cust-search").strip().lower()

view = filters.filter_in(customers, "customer_segment", segs)
view = filters.filter_in(view, "age_group", ages)
if search:
    view = view.loc[
        view["customer_name"].str.lower().str.contains(search, na=False)
    ].reset_index(drop=True)
if view.empty:
    st.warning("No customers match the current filters.")
    st.stop()

kpi = st.columns(4)
kpi[0].metric("Customers", fmt_num(len(view)))
kpi[1].metric("Revenue", fmt_money(float(view["total_sales"].sum())))
kpi[2].metric("Orders", fmt_num(float(view["total_orders"].sum())))
kpi[3].metric("Avg order value", fmt_money(float(view["avg_order_value"].mean())))

left, right = st.columns(2)
with left:
    seg = view.groupby("customer_segment", as_index=False)["total_sales"].sum()
    st.plotly_chart(
        charts.donut(seg, "customer_segment", "total_sales", "Revenue by segment"),
        use_container_width=True,
    )
with right:
    age = view.groupby("age_group", as_index=False).agg(
        customers=("customer_name", "count"), total_sales=("total_sales", "sum")
    )
    fig = px.bar(
        age,
        x="age_group",
        y="customers",
        title="Customers by age group",
        color="age_group",
    )
    st.plotly_chart(charts.style_fig(fig), use_container_width=True)

top = view.nlargest(top_n, "total_sales")
st.plotly_chart(
    charts.hbar(
        top, "total_sales", "customer_name", f"Top {len(top)} customers by revenue"
    ),
    use_container_width=True,
)

fig = px.scatter(
    view.sample(min(len(view), 2000), random_state=42),
    x="lifespan_months",
    y="total_sales",
    color="customer_segment",
    title="Lifespan vs revenue (2k customer sample)",
    hover_name="customer_name",
)
st.plotly_chart(charts.style_fig(fig, height=440), use_container_width=True)

with st.expander("Customer detail"):
    cols = [
        "customer_name",
        "age_group",
        "customer_segment",
        "total_orders",
        "total_sales",
        "avg_order_value",
        "lifespan_months",
        "recency_months",
    ]
    st.dataframe(view[cols], use_container_width=True)
    filters.download_button(view[cols], "customers.csv", "dl-customers")
