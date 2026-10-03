import plotly.express as px
import streamlit as st
from lib import charts, filters, queries
from lib.charts import fmt_money, fmt_num
from lib.db import connection_ok

st.set_page_config(page_title="Products", page_icon="📦", layout="wide")

ok = connection_ok()
filters.sidebar_status(ok)
if not ok:
    st.stop()

products = queries.load_products()
if products.empty:
    st.warning("analytics.report_products returned no rows.")
    st.stop()

st.title("📦 Products")
st.caption("Source: analytics.report_products (lifetime KPIs per product).")

cats = filters.sidebar_multi(
    "Category", sorted(products["category"].dropna().unique()), "prod-cat"
)
segs = filters.sidebar_multi(
    "Product segment", sorted(products["product_segment"].dropna().unique()), "prod-seg"
)
with st.sidebar:
    top_n = st.slider("Top N products", 5, 30, 10, key="prod-topn")
    search = st.text_input("Search product name", key="prod-search").strip().lower()

view = filters.filter_in(products, "category", cats)
view = filters.filter_in(view, "product_segment", segs)
if search:
    view = view.loc[
        view["product_name"].str.lower().str.contains(search, na=False)
    ].reset_index(drop=True)
if view.empty:
    st.warning("No products match the current filters.")
    st.stop()

kpi = st.columns(4)
kpi[0].metric("Products", fmt_num(len(view)))
kpi[1].metric("Revenue", fmt_money(float(view["total_sales"].sum())))
kpi[2].metric("Units sold", fmt_num(float(view["total_quantity"].sum())))
kpi[3].metric("Avg selling price", fmt_money(float(view["avg_selling_price"].mean())))

top = view.nlargest(top_n, "total_sales")
st.plotly_chart(
    charts.hbar(
        top, "total_sales", "product_name", f"Top {len(top)} products by revenue"
    ),
    use_container_width=True,
)

left, right = st.columns(2)
with left:
    seg = view.groupby("product_segment", as_index=False)["total_sales"].sum()
    st.plotly_chart(
        charts.donut(
            seg, "product_segment", "total_sales", "Revenue by product segment"
        ),
        use_container_width=True,
    )
with right:
    by_cat = view.groupby("category", as_index=False)["total_sales"].sum()
    st.plotly_chart(
        charts.donut(by_cat, "category", "total_sales", "Revenue by category"),
        use_container_width=True,
    )

fig = px.scatter(
    view,
    x="avg_selling_price",
    y="total_sales",
    size="total_quantity",
    color="product_segment",
    hover_name="product_name",
    title="Price vs revenue (bubble = units sold)",
)
st.plotly_chart(charts.style_fig(fig, height=440), use_container_width=True)

with st.expander("Product detail"):
    cols = [
        "product_name",
        "category",
        "subcategory",
        "product_segment",
        "total_orders",
        "total_sales",
        "total_quantity",
        "avg_selling_price",
        "recency_months",
    ]
    st.dataframe(view[cols], use_container_width=True)
    filters.download_button(view[cols], "products.csv", "dl-products")
