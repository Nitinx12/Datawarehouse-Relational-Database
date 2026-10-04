# Architecture

One pipeline, one scheduler, four data layers. Airflow orders the work, `main.py` does the work, Postgres stored procedures move the data.

## 1. System map

```mermaid
flowchart LR
    MONGO[("MongoDB<br/>erp_source")] --> EXT["Spark extracts<br/>mongo_to_postgres<br/>databricks_to_postgres"]
    DATAB[("Databricks<br/>crm_source")] --> EXT
    EXT --> SRC[("source<br/>raw landing")]
    SRC --> STG[("staging<br/>cleansed")]
    STG --> WH[("warehouse<br/>dims + fact")]
    WH --> AN[("analytics<br/>marts + KPI")]
    AN --> DASH["Streamlit dashboard<br/>:8501"]
    AF["Airflow<br/>warehouse_daily"] -. orders .-> EXT & SRC & STG & WH & AN

    classDef src fill:#ddf4ff,stroke:#0969da,color:#053a7a;
    classDef load fill:#dafbe1,stroke:#1a7f37,color:#0d4d1f;
    classDef serve fill:#fff8c5,stroke:#9a6700,color:#5a3c00;
    classDef orch fill:#ede9fe,stroke:#5a3fa4,color:#2e1f5a;

    class MONGO,DATAB,EXT,SRC src;
    class STG,WH load;
    class AN,DASH serve;
    class AF orch;
```

| Layer | Schema | Written by | Consumed by |
|---|---|---|---|
| Landing | `source` | Spark jobs | Staging procedures, source-tests |
| Cleansed | `staging` | `staging.*` procedures | Warehouse procedures |
| Business | `warehouse` | `warehouse.*` procedures | Analytics, dashboard |
| Serving | `analytics` | `analytics.*` procedures | Dashboard, KPI readers |

## 2. Airflow dependencies

DAG `warehouse_daily`, schedule `0 11 * * 1-5` (`Asia/Kolkata`), `max_active_runs=1`. Each task runs `uv run main.py --only <stage>`.

```mermaid
flowchart TD
    PRE["preflight<br/>check_sources.py"] --> ETM["extract.extract_mongo<br/>run_mongo_job.py"]
    ETM --> ETD["extract.extract_databricks<br/>run_databricks_job.py"]
    ETD --> ST["source-tests<br/>retries=0"]
    ST --> SG["staging"]
    SG --> SGT["staging-tests<br/>retries=0"]
    SGT --> WH["warehouse"]
    WH --> WHT["warehouse-tests<br/>retries=0"]
    WHT --> AN["analytics"]
    AN --> ANT["analytics-tests<br/>retries=0"]
    ANT --> MS["master<br/>retries=0"]
    MS --> MAIL["summary_email<br/>ALL_DONE"]
    PRE & ETM & ETD & ST & SG & SGT & WH & WHT & AN & ANT -.-> MAIL

    classDef work fill:#ddf4ff,stroke:#0969da,color:#053a7a;
    classDef test fill:#fff8c5,stroke:#9a6700,color:#5a3c00;
    classDef gate fill:#dafbe1,stroke:#1a7f37,color:#0d4d1f;
    classDef mail fill:#ffebe9,stroke:#cf222e,color:#7a0d14;

    class PRE,ETM,ETD,SG,WH,AN work;
    class ST,SGT,WHT,ANT test;
    class MS gate;
    class MAIL mail;
```

Rules: linear chain, extracts run sequentially (two Spark JVMs exceed Docker memory in parallel). `*-tests` and `master` use `retries=0`. `summary_email` has `trigger_rule=ALL_DONE` plus direct edges from every task, then raises to keep failed runs red.

## 3. Stored procedures

Called in listed order via `run_staging_load.call_procedure()`. First failure stops the stage.

| Stage | Procedure | Target |
|---|---|---|
| staging | `staging.load_px_cat_g1v2` | `staging.px_cat_g1v2` |
| staging | `staging.load_cust_info` | `staging.cust_info` |
| staging | `staging.load_prd_info` | `staging.prd_info` |
| staging | `staging.load_cust_az12` | `staging.cust_az12` |
| staging | `staging.load_loc_a101` | `staging.loc_a101` |
| staging | `staging.load_sales_details` | `staging.sales_details` |
| warehouse | `warehouse.load_dim_customers` | `warehouse.dim_customers` |
| warehouse | `warehouse.load_dim_products` | `warehouse.dim_products` |
| warehouse | `warehouse.load_fact_sales` | `warehouse.fact_sales` |
| analytics | `analytics.load_monthly_kpi_snapshot` | `analytics.monthly_kpi_snapshot` |

```mermaid
flowchart LR
    S1["staging x6<br/>cleanse + standardize"] --> W1["warehouse x3<br/>2 dims + 1 fact"]
    W1 --> A1["analytics x1<br/>monthly KPI freeze"]

    classDef s fill:#ddf4ff,stroke:#0969da,color:#053a7a;
    classDef w fill:#dafbe1,stroke:#1a7f37,color:#0d4d1f;
    classDef a fill:#fff8c5,stroke:#9a6700,color:#5a3c00;

    class S1 s;
    class W1 w;
    class A1 a;
```

## 4. Extract path

```mermaid
flowchart TD
    MJ["run_mongo_job.py<br/>spark-submit + mongo jars"] --> SE[("source.*<br/>+ source.etl_logs<br/>watermark")]
    DJ["run_databricks_job.py<br/>spark-submit + pg jar"] --> SE

    classDef job fill:#ddf4ff,stroke:#0969da,color:#053a7a;
    classDef tbl fill:#dafbe1,stroke:#1a7f37,color:#0d4d1f;

    class MJ,DJ job;
    class SE tbl;
```

Each job tracks its watermark and run history in `source.etl_logs`. `_submit.py` resolves `spark-submit`, sets `PYSPARK_PYTHON`, defaults `SPARK_DRIVER_MEMORY=1g`.

## 5. Quality gates

Every layer runs SQL checks first, then Great Expectations. DQ failure skips GX for that layer.

```mermaid
flowchart TD
    L["layer-tests task"] --> DQ["run_dq_checks.py<br/>tests/data_quality/<layer>/*.sql"]
    DQ -- pass --> GX["run_gx_validations.run_layer()<br/>checkpoints per table"]
    DQ -- fail --> STOP["stage FAILED<br/>no retry"]
    GX --> MG["master: run_master()<br/>all tables at once"]

    classDef t fill:#fff8c5,stroke:#9a6700,color:#5a3c00;
    classDef g fill:#dafbe1,stroke:#1a7f37,color:#0d4d1f;
    classDef f fill:#ffebe9,stroke:#cf222e,color:#7a0d14;

    class L,DQ t;
    class GX,MG g;
    class STOP f;
```

## 6. Infra and observability

```mermaid
flowchart TD
    subgraph CMP["compose"]
        PG[("postgres:17<br/>datawarehouse")]
        MG2[("mongo:7<br/>erp_source")]
        SCH["airflow-scheduler"]
        WEB["airflow-webserver<br/>:8080"]
        PRM[("Prometheus<br/>:9090")]
        GR["Grafana<br/>:3000"]
    end
    SCH --> PG & MG2
    PG --> PRM
    MG2 --> PRM
    SCH --> PRM
    PRM --> GR
    PG -. run log + snapshots .-> GR

    classDef db fill:#dafbe1,stroke:#1a7f37,color:#0d4d1f;
    classDef app fill:#ddf4ff,stroke:#0969da,color:#053a7a;
    classDef obs fill:#ede9fe,stroke:#5a3fa4,color:#2e1f5a;

    class PG,MG2 db;
    class SCH,WEB app;
    class PRM,GR obs;
```

`main.py` writes `ops.pipeline_run_log` per stage and `ops.table_snapshot` per layer (`src/utils/tracking.py`). Grafana reads Postgres directly for data alerts and Prometheus for infra. Airflow sends task-failure and run-summary emails.
