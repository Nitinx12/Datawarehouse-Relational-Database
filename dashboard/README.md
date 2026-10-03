# Retail Analytics Dashboard

Streamlit + Plotly dashboard over the Postgres analytics layer (`analytics.report_*`).

## Pages

- Overview (`home.py`) - revenue, orders, customers, AOV with MoM deltas
- Sales Trends - month filter, new customers, AOV, MoM growth
- Products - category / segment / search filters, top-N bar, segment donuts, price-vs-revenue bubble
- Customers - segment / age-group / search filters, top-N bar, lifespan scatter
- Categories - revenue treemap, subcategory bars, share table

## Run

```powershell
uv pip install --python .venv\Scripts\python.exe -r dashboard/requirements.txt
.venv\Scripts\python.exe -m streamlit run dashboard/home.py
```

Connection uses `dashboard/.streamlit/secrets.toml` first, then the repo root `.env`.
Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` for local overrides.
