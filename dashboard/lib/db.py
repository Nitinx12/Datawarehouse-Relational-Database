import os

import psycopg
import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

load_dotenv()


# resolves one postgres setting from secrets.toml first, then environment
def _setting(key: str, default: str) -> str:
    try:
        return str(st.secrets["postgres"][key.lower()])
    except (StreamlitSecretNotFoundError, KeyError):
        return os.getenv(f"POSTGRES_{key.upper()}", default)


# opens a cached postgres connection shared across reruns
@st.cache_resource(show_spinner=False)
def get_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=_setting("host", "localhost"),
        port=int(_setting("port", "5432")),
        dbname=_setting("dbname", "datawarehouse"),
        user=_setting("user", "postgres"),
        password=_setting("password", ""),
        connect_timeout=10,
    )


# runs a read-only query against the analytics layer and returns rows
@st.cache_data(ttl=600, show_spinner="Loading analytics layer...")
def run_query(sql: str) -> list[dict]:
    conn = get_connection()
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql)
        return list(cur.fetchall())


# pings the warehouse so pages can show connection status
def connection_ok() -> bool:
    try:
        get_connection().execute("SELECT 1")
        return True
    except (psycopg.Error, OSError):
        st.cache_resource.clear()
        return False
