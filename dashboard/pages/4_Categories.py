import streamlit as st
from lib import charts, filters, queries
from lib.charts import fmt_money, fmt_num
from lib.db import connection_ok

st.set_page_config(page_title="Categories", page_icon="🌳", layout="wide")

ok = connection_ok()
filters.sidebar_status(ok)
if not ok:
    st.stop()

categories = queries.load_categories()
if categories.empty:
    st.warning("analytics.report_category_sales returned no rows.")
    st.stop()

st.title("🌳 Categories")
st.caption(
    "Source: analytics.report_category_sales (lifetime rollup to category and subcategory)."
)

cats = filters.sidebar_multi(
    "Category", sorted(categories["category"].dropna().unique()), "cat-cat"
)
view = filters.filter_in(categories, "category", cats)
if view.empty:
    st.warning("No categories match the current filters.")
    st.stop()

kpi = st.columns(4)
kpi[0].metric("Categories", fmt_num(view["category"].nunique()))
kpi[1].metric("Subcategories", fmt_num(len(view)))
kpi[2].metric("Revenue", fmt_money(float(view["total_revenue"].sum())))
kpi[3].metric("Orders", fmt_num(float(view["order_count"].sum())))

st.plotly_chart(
    charts.treemap(
        view,
        ["category", "subcategory"],
        "total_revenue",
        "Revenue treemap: category to subcategory",
    ),
    use_container_width=True,
)

st.plotly_chart(
    charts.hbar(
        view,
        "total_revenue",
        "subcategory",
        "Revenue by subcategory",
        color_col="category",
    ),
    use_container_width=True,
)

with st.expander("Category detail"):
    st.dataframe(view, use_container_width=True)
    filters.download_button(view, "categories.csv", "dl-categories")
