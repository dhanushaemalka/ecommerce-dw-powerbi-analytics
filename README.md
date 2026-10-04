# E-Commerce Data Warehouse & Business Intelligence Analytics (DWBI)

An end-to-end Data Warehousing & Business Intelligence (DWBI) solution built on the Brazilian Olist E-Commerce dataset. This project covers the full analytics engineering lifecycle—from multi-source ingestion, data profiling, and star schema dimensional modeling, to OLAP multi-dimensional analytics and interactive Power BI executive dashboards.

---

## 🏗️ Project Architecture & Pipeline

```mermaid
flowchart LR
    subgraph Sources [Heterogeneous Sources]
        A1[CSV] & A2[Excel] & A3[JSON] & A4[Relational SQLite] & A5[XML]
    end

    subgraph Staging [Data Staging & Profiling]
        B1[Profiling & Quality Checks]
        B2[Staging DB Tables]
    end

    subgraph DW [Data Warehouse - Star Schema]
        C1[DimCustomer]
        C2[DimProduct]
        C3[DimSeller]
        C4[DimDate]
        C5[DimGeolocation]
        C6[FactSales & FactPayment]
    end

    subgraph Analytics [OLAP & BI Layer]
        D1[OLAP Cubes: Slice / Dice / Rollup / Drilldown]
        D2[Power BI Model & Executive Dashboards]
    end

    Sources --> Staging
    Staging --> DW
    DW --> Analytics
```

---

## 📁 Repository Structure

```text
DWBI-PROJECT/
├── DWBI-PRO-Complete/
│   ├── 01_PreparedSources/      # Multi-source formatted datasets (CSV, JSON, Excel, XML, DB)
│   ├── 02_Profiling/            # Data quality & attribute profiling reports
│   ├── sql/                     # DDL, Staging, Star Schema & ETL SQL scripts
│   ├── 08_GoldLayer/            # Processed dimension and fact tables (Gold layer)
│   ├── olap/                    # Analytical queries & OLAP operations
│   ├── 07_BI/                   # Power BI files (.pbip), DAX metrics & Executive HTML reports
│   ├── run_all.py               # End-to-end automated ETL pipeline script
│   └── requirements.txt         # Python dependencies
└── README.md
```

---

## 🚀 Quickstart

1. **Install Dependencies:**
   ```bash
   pip install -r DWBI-PRO-Complete/requirements.txt
   ```

2. **Run End-to-End Pipeline:**
   ```bash
   python DWBI-PRO-Complete/run_all.py
   ```
