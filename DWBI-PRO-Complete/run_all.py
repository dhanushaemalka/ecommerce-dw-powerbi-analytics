"""
SLIIT DWBI - Olist e-commerce data warehouse builder
Run from any folder:  python run_all.py

Reads the original CSVs from the parent project folder (d:\\DWBI-PRO)
and writes every prepared source, profile table, star-schema database,
OLAP result set, and BI dashboard into DWBI-Complete/.
"""
from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT.parent  # original CSVs live next to DWBI-Complete
PREP = ROOT / "01_PreparedSources"
PROF = ROOT / "02_Profiling"
GOLD = ROOT / "08_GoldLayer"
BI = ROOT / "07_BI"
OLAP = ROOT / "olap"
DB_PATH = ROOT / "OlistDW.sqlite"
METRICS_PATH = BI / "dashboard_metrics.json"

REGION = {
    "AC": "North", "AP": "North", "AM": "North", "PA": "North",
    "RO": "North", "RR": "North", "TO": "North",
    "AL": "Northeast", "BA": "Northeast", "CE": "Northeast", "MA": "Northeast",
    "PB": "Northeast", "PE": "Northeast", "PI": "Northeast", "RN": "Northeast",
    "SE": "Northeast",
    "DF": "Center-West", "GO": "Center-West", "MT": "Center-West", "MS": "Center-West",
    "ES": "Southeast", "MG": "Southeast", "RJ": "Southeast", "SP": "Southeast",
    "PR": "South", "RS": "South", "SC": "South",
}

MANUAL_TRANSLATION = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_food_preparers",
}

FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def read_csv(name: str) -> pd.DataFrame:
    path = RAW / FILES[name]
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin1")
    print(f"[OK] {name:22s} {len(df):>9,} rows  {len(df.columns):>2} cols")
    return df


def profile(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    banner("TASK 1 - DATASET OVERVIEW")
    rows = []
    for name, df in dfs.items():
        print(f"\n--- {name}: {len(df):,} records, {len(df.columns)} attributes ---")
        summary = pd.DataFrame({
            "dtype": df.dtypes.astype(str),
            "non_null": df.notna().sum(),
            "nulls": df.isna().sum(),
            "null_pct": (df.isna().mean() * 100).round(2),
            "distinct": [df[c].nunique(dropna=True) for c in df.columns],
        })
        print(summary.to_string())
        for col in df.columns:
            rows.append({
                "table": name,
                "attribute": col,
                "dtype": str(df[col].dtype),
                "records": len(df),
                "null_count": int(df[col].isna().sum()),
                "null_pct": round(float(df[col].isna().mean() * 100), 2),
                "distinct_values": int(df[col].nunique(dropna=True)),
            })
    table = pd.DataFrame(rows)
    PROF.mkdir(parents=True, exist_ok=True)
    table.to_csv(PROF / "task1_attribute_summary.csv", index=False)
    print("\nSaved 02_Profiling/task1_attribute_summary.csv")
    return table


def prepare_sources(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    banner("TASK 2 - MULTI-SOURCE PREPARATION")
    PREP.mkdir(parents=True, exist_ok=True)
    (PREP / "csv").mkdir(exist_ok=True)
    (PREP / "excel").mkdir(exist_ok=True)
    (PREP / "json").mkdir(exist_ok=True)
    (PREP / "xml").mkdir(exist_ok=True)
    (PREP / "relational").mkdir(exist_ok=True)

    # CSV transactional sources
    for name in ["orders", "order_items", "payments", "reviews"]:
        dfs[name].to_csv(PREP / "csv" / FILES[name], index=False, encoding="utf-8")
        print(f"CSV source  -> {name}")

    # Excel lookup
    xlsx = PREP / "excel" / "product_category_name_translation.xlsx"
    dfs["category_translation"].to_excel(xlsx, index=False)
    print(f"Excel source -> {xlsx.name}")

    # XML lookup (same translation, second source type)
    root = ET.Element("categories")
    for _, rec in dfs["category_translation"].iterrows():
        node = ET.SubElement(root, "category")
        ET.SubElement(node, "portuguese").text = str(rec["product_category_name"])
        ET.SubElement(node, "english").text = str(rec["product_category_name_english"])
    xml_path = PREP / "xml" / "product_category_name_translation.xml"
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)
    print(f"XML source  -> {xml_path.name}")

    # JSON holidays (API-shaped). Try live API, else seed file.
    holidays = []
    try:
        import urllib.request
        for year in (2016, 2017, 2018):
            url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/BR"
            with urllib.request.urlopen(url, timeout=8) as resp:
                holidays.extend(json.loads(resp.read().decode("utf-8")))
        print(f"JSON/API source -> fetched {len(holidays)} holidays live")
    except Exception as exc:
        seed = ROOT / "sources_seed" / "holidays_BR_2016_2018.json"
        holidays = json.loads(seed.read_text(encoding="utf-8"))
        print(f"JSON source -> offline seed ({len(holidays)} holidays) [{exc.__class__.__name__}]")

    holiday_path = PREP / "json" / "holidays_BR_2016_2018.json"
    holiday_path.write_text(json.dumps(holidays, indent=2, ensure_ascii=False), encoding="utf-8")
    holiday_df = pd.DataFrame(holidays)
    holiday_df.to_csv(PREP / "csv" / "holidays_BR_2016_2018.csv", index=False)

    # Relational OLTP-style source (master data)
    oltp = PREP / "relational" / "olist_oltp.sqlite"
    conn = sqlite3.connect(oltp)
    for name in ["customers", "products", "sellers", "geolocation"]:
        dfs[name].to_sql(name, conn, if_exists="replace", index=False)
        print(f"Relational source -> {name}")
    conn.close()

    return holiday_df


def integrity_checks(dfs: dict[str, pd.DataFrame]) -> None:
    banner("PREP - QUALITY AND INTEGRITY")
    order_ids = set(dfs["orders"]["order_id"])
    for name in ["order_items", "payments", "reviews"]:
        missing = set(dfs[name]["order_id"]) - order_ids
        print(f"{name:12s}: {len(missing)} order_id values not in orders")

    print("customers vs orders:", len(set(dfs["orders"]["customer_id"]) - set(dfs["customers"]["customer_id"])), "missing")
    print("products vs items :", len(set(dfs["order_items"]["product_id"]) - set(dfs["products"]["product_id"])), "missing")
    print("sellers vs items  :", len(set(dfs["order_items"]["seller_id"]) - set(dfs["sellers"]["seller_id"])), "missing")

    trans = set(dfs["category_translation"]["product_category_name"].dropna())
    prod_cats = set(dfs["products"]["product_category_name"].dropna())
    unmatched = prod_cats - trans
    print("Untranslated categories:", unmatched or "{}")

    geo = dfs["geolocation"]
    print(f"geolocation rows={len(geo):,} unique zip={geo['geolocation_zip_code_prefix'].nunique():,}")


def date_key(ts) -> int:
    if pd.isna(ts):
        return 19000101
    d = pd.Timestamp(ts).normalize()
    return int(d.year * 10000 + d.month * 100 + d.day)


def weight_class(w):
    if pd.isna(w):
        return "Unknown"
    if w < 500:
        return "Light"
    if w < 2000:
        return "Medium"
    return "Heavy"


def build_warehouse(dfs: dict[str, pd.DataFrame], holiday_df: pd.DataFrame) -> dict:
    banner("TASK 4/5 - STAR SCHEMA ETL")
    GOLD.mkdir(parents=True, exist_ok=True)

    orders = dfs["orders"].copy()
    for col in [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")

    items = dfs["order_items"].copy()
    items["shipping_limit_date"] = pd.to_datetime(items["shipping_limit_date"], errors="coerce")
    payments = dfs["payments"].copy()
    reviews = dfs["reviews"].copy()
    products = dfs["products"].copy()
    customers = dfs["customers"].copy()
    sellers = dfs["sellers"].copy()
    geo = dfs["geolocation"].copy()
    trans = dfs["category_translation"].copy()

    holiday_dates = set(pd.to_datetime(holiday_df["date"]).dt.normalize())
    holiday_names = {
        pd.Timestamp(r["date"]).normalize(): r.get("name")
        for _, r in holiday_df.iterrows()
    }

    start = pd.Timestamp("2016-01-01")
    end = pd.Timestamp("2018-12-31")
    cal = pd.date_range(start, end, freq="D")
    dim_date = pd.DataFrame({
        "DateKey": [d.year * 10000 + d.month * 100 + d.day for d in cal],
        "FullDate": cal.date,
        "DayNumber": cal.day,
        "DayName": cal.day_name(),
        "WeekdayFlag": ["N" if d.dayofweek >= 5 else "Y" for d in cal],
        "WeekendFlag": ["Y" if d.dayofweek >= 5 else "N" for d in cal],
        "WeekOfYear": cal.isocalendar().week.astype(int),
        "MonthNumber": cal.month,
        "MonthName": cal.month_name(),
        "QuarterNumber": cal.quarter,
        "QuarterName": ["Q" + str(q) for q in cal.quarter],
        "YearNumber": cal.year,
        "YearMonth": cal.strftime("%Y-%m"),
        "IsHoliday": [1 if d.normalize() in holiday_dates else 0 for d in cal],
        "HolidayName": [holiday_names.get(d.normalize()) for d in cal],
    })
    unknown_date = pd.DataFrame([{
        "DateKey": 19000101, "FullDate": pd.Timestamp("1900-01-01").date(),
        "DayNumber": 1, "DayName": "Monday", "WeekdayFlag": "Y", "WeekendFlag": "N",
        "WeekOfYear": 1, "MonthNumber": 1, "MonthName": "January",
        "QuarterNumber": 1, "QuarterName": "Q1", "YearNumber": 1900,
        "YearMonth": "1900-01", "IsHoliday": 0, "HolidayName": None,
    }])
    dim_date = pd.concat([unknown_date, dim_date], ignore_index=True)

    dim_geo = (
        geo.groupby("geolocation_zip_code_prefix", as_index=False)
        .agg(
            City=("geolocation_city", "max"),
            State=("geolocation_state", "max"),
            Latitude=("geolocation_lat", "mean"),
            Longitude=("geolocation_lng", "mean"),
        )
        .rename(columns={"geolocation_zip_code_prefix": "ZipPrefix"})
    )
    dim_geo["Region"] = dim_geo["State"].map(REGION).fillna("Unknown")
    dim_geo.insert(0, "GeoKey", range(1, len(dim_geo) + 1))

    dim_customer = customers.copy()
    dim_customer["customer_city"] = dim_customer["customer_city"].astype(str).str.strip().str.lower()
    dim_customer["customer_state"] = dim_customer["customer_state"].astype(str).str.strip().str.upper()
    dim_customer["CustomerRegion"] = dim_customer["customer_state"].map(REGION).fillna("Unknown")
    dim_customer = dim_customer.rename(columns={
        "customer_id": "CustomerID",
        "customer_unique_id": "CustomerUniqueID",
        "customer_city": "CustomerCity",
        "customer_state": "CustomerState",
        "customer_zip_code_prefix": "CustomerZipPrefix",
    })
    unknown_c = pd.DataFrame([{
        "CustomerID": "UNKNOWN", "CustomerUniqueID": "UNKNOWN",
        "CustomerCity": "unknown", "CustomerState": "XX",
        "CustomerRegion": "Unknown", "CustomerZipPrefix": 0, "IsUnknown": 1,
    }])
    dim_customer["IsUnknown"] = 0
    dim_customer = pd.concat([unknown_c, dim_customer], ignore_index=True)
    dim_customer.insert(0, "CustomerKey", range(1, len(dim_customer) + 1))

    trans_map = dict(zip(trans["product_category_name"], trans["product_category_name_english"]))
    dim_product = products.copy()
    dim_product["CategoryNamePortuguese"] = dim_product["product_category_name"].fillna("unknown")
    dim_product["CategoryNameEnglish"] = dim_product["product_category_name"].map(trans_map)
    dim_product["CategoryNameEnglish"] = dim_product["CategoryNameEnglish"].fillna(
        dim_product["product_category_name"].map(MANUAL_TRANSLATION)
    ).fillna("Other")
    dim_product["WeightClass"] = dim_product["product_weight_g"].map(weight_class)
    dim_product = dim_product.rename(columns={
        "product_id": "ProductID",
        "product_weight_g": "WeightG",
        "product_length_cm": "LengthCm",
        "product_height_cm": "HeightCm",
        "product_width_cm": "WidthCm",
        "product_photos_qty": "PhotosQty",
    })[
        ["ProductID", "CategoryNamePortuguese", "CategoryNameEnglish",
         "WeightG", "LengthCm", "HeightCm", "WidthCm", "PhotosQty", "WeightClass"]
    ]
    unknown_p = pd.DataFrame([{
        "ProductID": "UNKNOWN", "CategoryNamePortuguese": "unknown",
        "CategoryNameEnglish": "Unknown", "WeightG": None, "LengthCm": None,
        "HeightCm": None, "WidthCm": None, "PhotosQty": None,
        "WeightClass": "Unknown", "IsUnknown": 1,
    }])
    dim_product["IsUnknown"] = 0
    dim_product = pd.concat([unknown_p, dim_product], ignore_index=True)
    dim_product.insert(0, "ProductKey", range(1, len(dim_product) + 1))

    dim_seller = sellers.copy()
    dim_seller["seller_city"] = dim_seller["seller_city"].astype(str).str.strip().str.lower()
    dim_seller["seller_state"] = dim_seller["seller_state"].astype(str).str.strip().str.upper()
    dim_seller["SellerRegion"] = dim_seller["seller_state"].map(REGION).fillna("Unknown")
    dim_seller = dim_seller.rename(columns={
        "seller_id": "SellerID",
        "seller_city": "SellerCity",
        "seller_state": "SellerState",
        "seller_zip_code_prefix": "SellerZipPrefix",
    })
    unknown_s = pd.DataFrame([{
        "SellerID": "UNKNOWN", "SellerCity": "unknown", "SellerState": "XX",
        "SellerRegion": "Unknown", "SellerZipPrefix": 0, "IsUnknown": 1,
    }])
    dim_seller["IsUnknown"] = 0
    dim_seller = pd.concat([unknown_s, dim_seller], ignore_index=True)
    dim_seller.insert(0, "SellerKey", range(1, len(dim_seller) + 1))

    pay_types = pd.DataFrame({"PaymentType": sorted(payments["payment_type"].fillna("not_defined").unique())})
    pay_types["PaymentTypeGroup"] = pay_types["PaymentType"].map(
        lambda x: "Card" if x in ("credit_card", "debit_card")
        else "Bank slip" if x == "boleto"
        else "Voucher" if x == "voucher"
        else "Other"
    )
    if "unknown" not in set(pay_types["PaymentType"]):
        pay_types = pd.concat(
            [pd.DataFrame([{"PaymentType": "unknown", "PaymentTypeGroup": "Other"}]), pay_types],
            ignore_index=True,
        )
    pay_types.insert(0, "PaymentTypeKey", range(1, len(pay_types) + 1))

    statuses = pd.DataFrame({"OrderStatus": sorted(orders["order_status"].unique())})
    statuses["IsDeliveredFlag"] = statuses["OrderStatus"].map(lambda s: "Y" if s == "delivered" else "N")
    statuses["IsCancelledFlag"] = statuses["OrderStatus"].map(lambda s: "Y" if s in ("canceled", "cancelled") else "N")
    statuses.insert(0, "OrderStatusKey", range(1, len(statuses) + 1))

    primary_pay = (
        payments.sort_values(["order_id", "payment_sequential"])
        .drop_duplicates("order_id", keep="first")[["order_id", "payment_type"]]
    )
    avg_review = reviews.groupby("order_id", as_index=False)["review_score"].mean()

    fact = items.merge(orders, on="order_id", how="inner")
    fact = fact.merge(primary_pay, on="order_id", how="left")
    fact = fact.merge(avg_review, on="order_id", how="left")

    cmap = dict(zip(dim_customer["CustomerID"], dim_customer["CustomerKey"]))
    pmap = dict(zip(dim_product["ProductID"], dim_product["ProductKey"]))
    smap = dict(zip(dim_seller["SellerID"], dim_seller["SellerKey"]))
    stmap = dict(zip(statuses["OrderStatus"], statuses["OrderStatusKey"]))
    ptmap = dict(zip(pay_types["PaymentType"], pay_types["PaymentTypeKey"]))
    zip_to_geo = dict(zip(dim_geo["ZipPrefix"], dim_geo["GeoKey"]))
    cust_zip = dict(zip(dim_customer["CustomerID"], dim_customer["CustomerZipPrefix"]))

    unk_c = int(dim_customer.loc[dim_customer["CustomerID"] == "UNKNOWN", "CustomerKey"].iloc[0])
    unk_p = int(dim_product.loc[dim_product["ProductID"] == "UNKNOWN", "ProductKey"].iloc[0])
    unk_s = int(dim_seller.loc[dim_seller["SellerID"] == "UNKNOWN", "SellerKey"].iloc[0])
    unk_pt = int(pay_types.loc[pay_types["PaymentType"] == "unknown", "PaymentTypeKey"].iloc[0])

    fact["PurchaseDateKey"] = fact["order_purchase_timestamp"].map(date_key)
    fact["DeliveredDateKey"] = fact["order_delivered_customer_date"].map(date_key)
    fact["EstimatedDeliveryDateKey"] = fact["order_estimated_delivery_date"].map(date_key)
    fact["CustomerKey"] = fact["customer_id"].map(cmap).fillna(unk_c).astype(int)
    fact["ProductKey"] = fact["product_id"].map(pmap).fillna(unk_p).astype(int)
    fact["SellerKey"] = fact["seller_id"].map(smap).fillna(unk_s).astype(int)
    fact["OrderStatusKey"] = fact["order_status"].map(stmap).astype(int)
    fact["PaymentTypeKey"] = fact["payment_type"].map(ptmap).fillna(unk_pt).astype(int)
    fact["CustomerGeoKey"] = fact["customer_id"].map(cust_zip).map(zip_to_geo)
    fact["Price"] = fact["price"].astype(float)
    fact["FreightValue"] = fact["freight_value"].astype(float)
    fact["LineTotal"] = fact["Price"] + fact["FreightValue"]
    fact["Quantity"] = 1
    fact["DeliveryDays"] = (
        fact["order_delivered_customer_date"] - fact["order_purchase_timestamp"]
    ).dt.days
    fact["DelayDays"] = (
        fact["order_delivered_customer_date"] - fact["order_estimated_delivery_date"]
    ).dt.days
    fact["OnTimeFlag"] = fact["DelayDays"].map(
        lambda x: None if pd.isna(x) else ("Y" if x <= 0 else "N")
    )
    fact["ReviewScore"] = fact["review_score"]
    fact["OrderID"] = fact["order_id"]
    fact["OrderItemID"] = fact["order_item_id"]
    fact.insert(0, "SalesKey", range(1, len(fact) + 1))

    fact_sales = fact[[
        "SalesKey", "PurchaseDateKey", "DeliveredDateKey", "EstimatedDeliveryDateKey",
        "CustomerKey", "ProductKey", "SellerKey", "CustomerGeoKey", "PaymentTypeKey",
        "OrderStatusKey", "OrderID", "OrderItemID", "Price", "FreightValue", "LineTotal",
        "Quantity", "DeliveryDays", "DelayDays", "OnTimeFlag", "ReviewScore",
    ]]

    pay_fact = payments.merge(orders[["order_id", "customer_id", "order_purchase_timestamp"]], on="order_id", how="inner")
    pay_fact["PurchaseDateKey"] = pay_fact["order_purchase_timestamp"].map(date_key)
    pay_fact["CustomerKey"] = pay_fact["customer_id"].map(cmap).fillna(unk_c).astype(int)
    pay_fact["PaymentTypeKey"] = pay_fact["payment_type"].map(ptmap).fillna(unk_pt).astype(int)
    pay_fact = pay_fact.rename(columns={
        "order_id": "OrderID",
        "payment_sequential": "PaymentSequential",
        "payment_installments": "PaymentInstallments",
        "payment_value": "PaymentValue",
    })
    pay_fact.insert(0, "PaymentKey", range(1, len(pay_fact) + 1))
    fact_payment = pay_fact[[
        "PaymentKey", "PurchaseDateKey", "CustomerKey", "PaymentTypeKey",
        "OrderID", "PaymentSequential", "PaymentInstallments", "PaymentValue",
    ]]

    tables = {
        "DimDate": dim_date,
        "DimCustomer": dim_customer,
        "DimProduct": dim_product,
        "DimSeller": dim_seller,
        "DimGeolocation": dim_geo,
        "DimPaymentType": pay_types,
        "DimOrderStatus": statuses,
        "FactSales": fact_sales,
        "FactPayment": fact_payment,
    }

    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    for name, df in tables.items():
        df.to_sql(name, conn, index=False, if_exists="replace")
        df.to_csv(GOLD / f"{name}.csv", index=False)
        print(f"Loaded {name:16s} {len(df):>9,} rows")
    conn.close()
    print(f"SQLite warehouse -> {DB_PATH}")
    return tables


def analytics(tables: dict) -> dict:
    banner("OLAP / BI METRICS")
    OLAP.mkdir(parents=True, exist_ok=True)
    BI.mkdir(parents=True, exist_ok=True)

    fact = tables["FactSales"].copy()
    dim_date = tables["DimDate"]
    dim_prod = tables["DimProduct"]
    dim_cust = tables["DimCustomer"]
    dim_status = tables["DimOrderStatus"]
    dim_pay = tables["DimPaymentType"]
    dim_seller = tables["DimSeller"]

    fact = fact.merge(dim_date[["DateKey", "YearNumber", "QuarterName", "MonthName", "MonthNumber", "YearMonth", "IsHoliday"]],
                      left_on="PurchaseDateKey", right_on="DateKey", how="left")
    fact = fact.merge(dim_prod[["ProductKey", "CategoryNameEnglish", "WeightClass"]], on="ProductKey", how="left")
    fact = fact.merge(dim_cust[["CustomerKey", "CustomerState", "CustomerRegion", "CustomerCity"]], on="CustomerKey", how="left")
    fact = fact.merge(dim_status, on="OrderStatusKey", how="left")
    fact = fact.merge(dim_pay, on="PaymentTypeKey", how="left")
    fact = fact.merge(dim_seller[["SellerKey", "SellerState", "SellerRegion"]], on="SellerKey", how="left")

    delivered = fact[fact["IsDeliveredFlag"] == "Y"].copy()

    rollup = (
        delivered.groupby(["YearNumber", "QuarterName"], as_index=False)
        .agg(Revenue=("LineTotal", "sum"), Items=("Quantity", "sum"), Orders=("OrderID", "nunique"))
        .sort_values(["YearNumber", "QuarterName"])
    )
    rollup.to_csv(OLAP / "rollup_year_quarter.csv", index=False)

    drill = (
        delivered[delivered["YearNumber"] == 2017]
        .groupby(["MonthNumber", "MonthName"], as_index=False)
        .agg(Revenue=("LineTotal", "sum"), Orders=("OrderID", "nunique"))
        .sort_values("MonthNumber")
    )
    drill.to_csv(OLAP / "drilldown_2017_month.csv", index=False)

    slice_se = (
        delivered[delivered["CustomerRegion"] == "Southeast"]
        .groupby("CategoryNameEnglish", as_index=False)
        .agg(Revenue=("LineTotal", "sum"))
        .sort_values("Revenue", ascending=False)
        .head(15)
    )
    slice_se.to_csv(OLAP / "slice_southeast_category.csv", index=False)

    dice = (
        delivered[(delivered["YearNumber"] == 2018) & (delivered["PaymentType"] == "credit_card")]
        .groupby("CustomerState", as_index=False)
        .agg(Revenue=("LineTotal", "sum"), AvgReview=("ReviewScore", "mean"))
        .sort_values("Revenue", ascending=False)
    )
    dice.to_csv(OLAP / "dice_2018_creditcard_state.csv", index=False)

    pivot = delivered.pivot_table(
        index="CustomerRegion", columns="YearNumber", values="LineTotal", aggfunc="sum", fill_value=0
    ).reset_index()
    pivot.to_csv(OLAP / "pivot_region_year.csv", index=False)

    ontime = delivered.dropna(subset=["OnTimeFlag"]).copy()
    kpi_cat = (
        ontime.groupby("CategoryNameEnglish", as_index=False)
        .agg(
            Items=("Quantity", "sum"),
            OnTimePct=("OnTimeFlag", lambda s: (s == "Y").mean() * 100),
            AvgDeliveryDays=("DeliveryDays", "mean"),
            AvgReview=("ReviewScore", "mean"),
            Revenue=("LineTotal", "sum"),
        )
    )
    kpi_cat = kpi_cat[kpi_cat["Items"] >= 200].sort_values("OnTimePct")
    kpi_cat.to_csv(OLAP / "kpi_ontime_by_category.csv", index=False)

    holiday = (
        fact.groupby("IsHoliday", as_index=False)
        .agg(Orders=("OrderID", "nunique"), Revenue=("LineTotal", "sum"), AvgReview=("ReviewScore", "mean"))
    )
    holiday.to_csv(OLAP / "holiday_vs_normal.csv", index=False)

    top_cat = (
        delivered.groupby("CategoryNameEnglish", as_index=False)
        .agg(Revenue=("LineTotal", "sum"), Orders=("OrderID", "nunique"), AvgReview=("ReviewScore", "mean"))
        .sort_values("Revenue", ascending=False)
        .head(10)
    )
    pay_mix = (
        tables["FactPayment"].merge(dim_pay, on="PaymentTypeKey")
        .groupby("PaymentType", as_index=False)
        .agg(PaymentValue=("PaymentValue", "sum"), Txn=("OrderID", "nunique"))
        .sort_values("PaymentValue", ascending=False)
    )
    monthly = (
        delivered.groupby("YearMonth", as_index=False)
        .agg(Revenue=("LineTotal", "sum"), Orders=("OrderID", "nunique"))
        .sort_values("YearMonth")
    )
    region = (
        delivered.groupby("CustomerRegion", as_index=False)
        .agg(Revenue=("LineTotal", "sum"), Orders=("OrderID", "nunique"), AvgReview=("ReviewScore", "mean"))
        .sort_values("Revenue", ascending=False)
    )

    quality = {
        "fact_sales_rows": int(len(tables["FactSales"])),
        "fact_payment_rows": int(len(tables["FactPayment"])),
        "dim_customer_rows": int(len(tables["DimCustomer"])),
        "dim_product_rows": int(len(tables["DimProduct"])),
        "dim_seller_rows": int(len(tables["DimSeller"])),
        "dim_date_rows": int(len(tables["DimDate"])),
        "unknown_customer_facts": int((tables["FactSales"]["CustomerKey"] == int(tables["DimCustomer"].loc[tables["DimCustomer"]["CustomerID"]=="UNKNOWN","CustomerKey"].iloc[0])).sum()),
        "unknown_product_facts": int((tables["FactSales"]["ProductKey"] == int(tables["DimProduct"].loc[tables["DimProduct"]["ProductID"]=="UNKNOWN","ProductKey"].iloc[0])).sum()),
        "unknown_seller_facts": int((tables["FactSales"]["SellerKey"] == int(tables["DimSeller"].loc[tables["DimSeller"]["SellerID"]=="UNKNOWN","SellerKey"].iloc[0])).sum()),
        "total_revenue_delivered": float(delivered["LineTotal"].sum()),
        "total_orders_delivered": int(delivered["OrderID"].nunique()),
        "avg_review": float(delivered["ReviewScore"].mean()),
        "ontime_rate": float((ontime["OnTimeFlag"] == "Y").mean() * 100),
        "avg_delivery_days": float(delivered["DeliveryDays"].mean()),
    }

    metrics = {
        "kpis": quality,
        "monthly": monthly.to_dict(orient="records"),
        "top_categories": top_cat.to_dict(orient="records"),
        "payment_mix": pay_mix.to_dict(orient="records"),
        "region": region.to_dict(orient="records"),
        "rollup": rollup.to_dict(orient="records"),
        "holiday": holiday.to_dict(orient="records"),
        "kpi_slowest_categories": kpi_cat.head(8).to_dict(orient="records"),
    }
    METRICS_PATH.write_text(json.dumps(metrics, default=float, indent=2), encoding="utf-8")
    print("Saved BI metrics and OLAP CSV result sets")
    print(json.dumps(quality, indent=2))
    return metrics


def write_dashboard(metrics: dict) -> None:
    k = metrics["kpis"]
    template = (BI / "dashboard_template.html").read_text(encoding="utf-8")
    html = (
        template.replace("__METRICS__", json.dumps(metrics, default=float))
        .replace("__REV__", f"R$ {k['total_revenue_delivered']:,.0f}")
        .replace("__ORD__", f"{k['total_orders_delivered']:,}")
        .replace("__ONT__", f"{k['ontime_rate']:.1f}%")
        .replace("__REVW__", f"{k['avg_review']:.2f} / 5")
        .replace("__DAYS__", f"{k['avg_delivery_days']:.1f}")
    )
    out = BI / "Olist_Executive_Dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"Dashboard -> {out}")


def main() -> None:
    for folder in [PREP, PROF, GOLD, BI, OLAP]:
        folder.mkdir(parents=True, exist_ok=True)

    dfs = {name: read_csv(name) for name in FILES}
    profile(dfs)
    integrity_checks(dfs)
    holiday_df = prepare_sources(dfs)
    tables = build_warehouse(dfs, holiday_df)
    metrics = analytics(tables)
    write_dashboard(metrics)
    banner("PROJECT BUILD COMPLETE")
    print("Open 07_BI/Olist_Executive_Dashboard.html")
    print("SQL Server scripts are in sql/")
    print("Report is in docs/DWBI_Assignment_Report.md")


if __name__ == "__main__":
    main()
