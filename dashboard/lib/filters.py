import pandas as pd
import streamlit as st


# renders sidebar connection status and returns nothing
def sidebar_status(conn_ok: bool) -> None:
    with st.sidebar:
        st.subheader("Warehouse")
        if conn_ok:
            st.success("Postgres analytics connected")
        else:
            st.error("Postgres unreachable - check secrets.toml / .env")
        st.caption("Source: analytics.* views in Postgres")


# renders a sidebar multiselect bound to a dataframe column
def sidebar_multi(label: str, options: list[str], key: str) -> list[str]:
    with st.sidebar:
        return st.multiselect(label, options, default=options, key=key)


# renders a sidebar month range slider over a monthly frame
def sidebar_month_range(frame: pd.DataFrame, key: str) -> tuple:
    months = frame["order_month"].dropna().sort_values().unique()
    labels = [pd.Timestamp(m).strftime("%Y-%m") for m in months]
    with st.sidebar:
        selected = st.select_slider(
            "Order month range",
            options=labels,
            value=(labels[0], labels[-1]),
            key=key,
        )
    start = pd.Timestamp(selected[0]).to_pydatetime().date()
    end = (pd.Timestamp(selected[1]) + pd.offsets.MonthEnd(0)).date()
    return start, end


# filters a monthly frame to an inclusive date window
def filter_months(frame: pd.DataFrame, start: object, end: object) -> pd.DataFrame:
    mask = (frame["order_month"] >= pd.Timestamp(start)) & (
        frame["order_month"] <= pd.Timestamp(end)
    )
    return frame.loc[mask].reset_index(drop=True)


# filters rows to the selected values of a column, or all when empty
def filter_in(frame: pd.DataFrame, column: str, selected: list[str]) -> pd.DataFrame:
    if not selected:
        return frame.iloc[0:0]
    return frame.loc[frame[column].isin(selected)].reset_index(drop=True)


# renders a csv download button for a dataframe
def download_button(frame: pd.DataFrame, filename: str, key: str) -> None:
    st.download_button(
        "Download filtered CSV",
        frame.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )
