"""Generate Olist_DWBI.pbip (Power BI Project) from Gold CSVs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJ = ROOT / "Olist_DWBI"
SM = PROJ / "Olist_DWBI.SemanticModel"
REP = PROJ / "Olist_DWBI.Report"
DEF = SM / "definition"
TDIR = DEF / "tables"
GOLD = ROOT.parent / "08_GoldLayer"
GOLD_M = str(GOLD).replace("\\", "/")

TAB = "\t"
VSCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
PSCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json"


def hid(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:20]


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\r\n")


def col_block(name: str, dtype: str, source: str | None = None, hidden=False, summarize="none", extra: list[str] | None = None) -> str:
    quoted = f"'{name}'" if any(c in name for c in " .") else name
    lines = [f"{TAB}column {quoted}", f"{TAB}{TAB}dataType: {dtype}"]
    if hidden:
        lines.append(f"{TAB}{TAB}isHidden")
    lines.append(f"{TAB}{TAB}summarizeBy: {summarize}")
    lines.append(f"{TAB}{TAB}sourceColumn: {source or name}")
    if extra:
        for e in extra:
            lines.append(f"{TAB}{TAB}{e}")
    return "\n".join(lines)


def m_csv(file_name: str, types: list[tuple[str, str]]) -> str:
    type_list = ", ".join(f'{{"{c}", {t}}}' for c, t in types)
    return f'''```
{TAB}{TAB}{TAB}let
{TAB}{TAB}{TAB}    Source = Csv.Document(File.Contents(GoldFolder & "/{file_name}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
{TAB}{TAB}{TAB}    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
{TAB}{TAB}{TAB}    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {{{type_list}}})
{TAB}{TAB}{TAB}in
{TAB}{TAB}{TAB}    ChangedType
{TAB}{TAB}```'''


def table_tmdl(name: str, measures: list[str], columns: list[str], m_source: str, extras: str = "") -> str:
    parts = [f"table {name}", ""]
    for m in measures:
        parts.append(m)
        parts.append("")
    for c in columns:
        parts.append(c)
        parts.append("")
    if extras:
        parts.append(extras.rstrip() + "\n")
    parts.append(f"{TAB}partition {name} = m")
    parts.append(f"{TAB}{TAB}mode: import")
    parts.append(f"{TAB}{TAB}source = {m_source}")
    parts.append("")
    return "\n".join(parts)


def measure(name: str, dax: str, fmt: str, desc: str) -> str:
    quoted = f"'{name}'" if any(c in name for c in " .%/") else name
    body = dax.strip()
    if "\n" in body:
        inner = "\n".join(f"{TAB}{TAB}{line}" if line else "" for line in body.split("\n"))
        return f"{TAB}/// {desc}\n{TAB}measure {quoted} = ```\n{inner}\n{TAB}{TAB}```\n{TAB}{TAB}formatString: {fmt}"
    return f"{TAB}/// {desc}\n{TAB}measure {quoted} = {body}\n{TAB}{TAB}formatString: {fmt}"


# --- Semantic model ---
def build_model() -> None:
    TDIR.mkdir(parents=True, exist_ok=True)

    dump(
        SM / "definition.pbism",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2",
            "settings": {"qnaEnabled": True},
        },
    )

    write(
        DEF / "database.tmdl",
        "database OlistDWBI\n"
        f"{TAB}compatibilityLevel: 1604\n"
        f"{TAB}compatibilityMode: powerBI\n",
    )

    write(
        DEF / "expressions.tmdl",
        "expression GoldFolder =\n"
        f'{TAB}"{GOLD_M}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n',
    )

    refs = "\n".join(
        f"ref table {t}"
        for t in [
            "FactSales",
            "FactPayment",
            "DimDate",
            "DimCustomer",
            "DimProduct",
            "DimSeller",
            "DimGeolocation",
            "DimPaymentType",
            "DimOrderStatus",
        ]
    )
    write(
        DEF / "model.tmdl",
        "model Model\n"
        f"{TAB}culture: en-US\n"
        f"{TAB}defaultPowerBIDataSourceVersion: powerBI_V3\n"
        f"{TAB}sourceQueryCulture: en-US\n"
        f"{TAB}discourageImplicitMeasures\n"
        "\n"
        "ref expression GoldFolder\n"
        f"{refs}\n",
    )

    rels = [
        ("FactSales_DimDate", "FactSales.PurchaseDateKey", "DimDate.DateKey", True),
        ("FactSales_DimCustomer", "FactSales.CustomerKey", "DimCustomer.CustomerKey", True),
        ("FactSales_DimProduct", "FactSales.ProductKey", "DimProduct.ProductKey", True),
        ("FactSales_DimSeller", "FactSales.SellerKey", "DimSeller.SellerKey", True),
        ("FactSales_DimGeo", "FactSales.CustomerGeoKey", "DimGeolocation.GeoKey", True),
        ("FactSales_DimStatus", "FactSales.OrderStatusKey", "DimOrderStatus.OrderStatusKey", True),
        ("FactSales_DimPayType", "FactSales.PaymentTypeKey", "DimPaymentType.PaymentTypeKey", False),
        ("FactPayment_DimDate", "FactPayment.PurchaseDateKey", "DimDate.DateKey", True),
        ("FactPayment_DimCustomer", "FactPayment.CustomerKey", "DimCustomer.CustomerKey", True),
        ("FactPayment_DimPayType", "FactPayment.PaymentTypeKey", "DimPaymentType.PaymentTypeKey", True),
    ]
    rel_txt = []
    for name, frm, to, active in rels:
        rel_txt.append(f"relationship {name}")
        if not active:
            rel_txt.append(f"{TAB}isActive: false")
        rel_txt.append(f"{TAB}crossFilteringBehavior: oneDirection")
        rel_txt.append(f"{TAB}fromCardinality: many")
        rel_txt.append(f"{TAB}toCardinality: one")
        rel_txt.append(f"{TAB}fromColumn: {frm}")
        rel_txt.append(f"{TAB}toColumn: {to}")
        rel_txt.append("")
    write(DEF / "relationships.tmdl", "\n".join(rel_txt))

    # DimDate
    date_cols = [
        col_block("DateKey", "int64", hidden=True, extra=["isKey"]),
        col_block("FullDate", "dateTime", extra=["formatString: yyyy-mm-dd", "dataCategory: Time"]),
        col_block("DayNumber", "int64"),
        col_block("DayName", "string", extra=["sortByColumn: DayNumber"]),
        col_block("WeekdayFlag", "string"),
        col_block("WeekendFlag", "string"),
        col_block("WeekOfYear", "int64"),
        col_block("MonthNumber", "int64"),
        col_block("MonthName", "string", extra=["sortByColumn: MonthNumber"]),
        col_block("QuarterNumber", "int64"),
        col_block("QuarterName", "string", extra=["sortByColumn: QuarterNumber"]),
        col_block("YearNumber", "int64"),
        col_block("YearMonth", "string"),
        col_block("IsHoliday", "int64"),
        col_block("HolidayName", "string"),
    ]
    hier = (
        f"{TAB}hierarchy 'Calendar'\n"
        f"{TAB}{TAB}level Year\n"
        f"{TAB}{TAB}{TAB}column: YearNumber\n"
        f"{TAB}{TAB}level Quarter\n"
        f"{TAB}{TAB}{TAB}column: QuarterName\n"
        f"{TAB}{TAB}level Month\n"
        f"{TAB}{TAB}{TAB}column: MonthName\n"
        f"{TAB}{TAB}level Date\n"
        f"{TAB}{TAB}{TAB}column: FullDate\n"
    )
    date_types = [
        ("DateKey", "Int64.Type"),
        ("FullDate", "type date"),
        ("DayNumber", "Int64.Type"),
        ("DayName", "type text"),
        ("WeekdayFlag", "type text"),
        ("WeekendFlag", "type text"),
        ("WeekOfYear", "Int64.Type"),
        ("MonthNumber", "Int64.Type"),
        ("MonthName", "type text"),
        ("QuarterNumber", "Int64.Type"),
        ("QuarterName", "type text"),
        ("YearNumber", "Int64.Type"),
        ("YearMonth", "type text"),
        ("IsHoliday", "Int64.Type"),
        ("HolidayName", "type text"),
    ]
    write(
        TDIR / "DimDate.tmdl",
        table_tmdl("DimDate", [], date_cols, m_csv("DimDate.csv", date_types), extras=hier),
    )

    cust_cols = [
        col_block("CustomerKey", "int64", hidden=True),
        col_block("CustomerID", "string"),
        col_block("CustomerUniqueID", "string"),
        col_block("CustomerCity", "string", extra=["dataCategory: City"]),
        col_block("CustomerState", "string", extra=["dataCategory: StateOrProvince"]),
        col_block("CustomerRegion", "string"),
        col_block("CustomerZipPrefix", "int64"),
        col_block("IsUnknown", "int64", hidden=True),
    ]
    write(
        TDIR / "DimCustomer.tmdl",
        table_tmdl(
            "DimCustomer",
            [],
            cust_cols,
            m_csv(
                "DimCustomer.csv",
                [
                    ("CustomerKey", "Int64.Type"),
                    ("CustomerID", "type text"),
                    ("CustomerUniqueID", "type text"),
                    ("CustomerCity", "type text"),
                    ("CustomerState", "type text"),
                    ("CustomerRegion", "type text"),
                    ("CustomerZipPrefix", "Int64.Type"),
                    ("IsUnknown", "Int64.Type"),
                ],
            ),
        ),
    )

    prod_cols = [
        col_block("ProductKey", "int64", hidden=True),
        col_block("ProductID", "string"),
        col_block("CategoryNamePortuguese", "string"),
        col_block("CategoryNameEnglish", "string"),
        col_block("WeightG", "double"),
        col_block("LengthCm", "double"),
        col_block("HeightCm", "double"),
        col_block("WidthCm", "double"),
        col_block("PhotosQty", "int64"),
        col_block("WeightClass", "string"),
        col_block("IsUnknown", "int64", hidden=True),
    ]
    write(
        TDIR / "DimProduct.tmdl",
        table_tmdl(
            "DimProduct",
            [],
            prod_cols,
            m_csv(
                "DimProduct.csv",
                [
                    ("ProductKey", "Int64.Type"),
                    ("ProductID", "type text"),
                    ("CategoryNamePortuguese", "type text"),
                    ("CategoryNameEnglish", "type text"),
                    ("WeightG", "type number"),
                    ("LengthCm", "type number"),
                    ("HeightCm", "type number"),
                    ("WidthCm", "type number"),
                    ("PhotosQty", "Int64.Type"),
                    ("WeightClass", "type text"),
                    ("IsUnknown", "Int64.Type"),
                ],
            ),
        ),
    )

    seller_cols = [
        col_block("SellerKey", "int64", hidden=True),
        col_block("SellerID", "string"),
        col_block("SellerCity", "string"),
        col_block("SellerState", "string"),
        col_block("SellerRegion", "string"),
        col_block("SellerZipPrefix", "int64"),
        col_block("IsUnknown", "int64", hidden=True),
    ]
    write(
        TDIR / "DimSeller.tmdl",
        table_tmdl(
            "DimSeller",
            [],
            seller_cols,
            m_csv(
                "DimSeller.csv",
                [
                    ("SellerKey", "Int64.Type"),
                    ("SellerID", "type text"),
                    ("SellerCity", "type text"),
                    ("SellerState", "type text"),
                    ("SellerRegion", "type text"),
                    ("SellerZipPrefix", "Int64.Type"),
                    ("IsUnknown", "Int64.Type"),
                ],
            ),
        ),
    )

    geo_cols = [
        col_block("GeoKey", "int64", hidden=True),
        col_block("ZipPrefix", "int64"),
        col_block("City", "string", extra=["dataCategory: City"]),
        col_block("State", "string", extra=["dataCategory: StateOrProvince"]),
        col_block("Latitude", "double", extra=["dataCategory: Latitude"]),
        col_block("Longitude", "double", extra=["dataCategory: Longitude"]),
        col_block("Region", "string"),
    ]
    write(
        TDIR / "DimGeolocation.tmdl",
        table_tmdl(
            "DimGeolocation",
            [],
            geo_cols,
            m_csv(
                "DimGeolocation.csv",
                [
                    ("GeoKey", "Int64.Type"),
                    ("ZipPrefix", "Int64.Type"),
                    ("City", "type text"),
                    ("State", "type text"),
                    ("Latitude", "type number"),
                    ("Longitude", "type number"),
                    ("Region", "type text"),
                ],
            ),
        ),
    )

    write(
        TDIR / "DimPaymentType.tmdl",
        table_tmdl(
            "DimPaymentType",
            [],
            [
                col_block("PaymentTypeKey", "int64", hidden=True),
                col_block("PaymentType", "string"),
                col_block("PaymentTypeGroup", "string"),
            ],
            m_csv(
                "DimPaymentType.csv",
                [
                    ("PaymentTypeKey", "Int64.Type"),
                    ("PaymentType", "type text"),
                    ("PaymentTypeGroup", "type text"),
                ],
            ),
        ),
    )

    write(
        TDIR / "DimOrderStatus.tmdl",
        table_tmdl(
            "DimOrderStatus",
            [],
            [
                col_block("OrderStatusKey", "int64", hidden=True),
                col_block("OrderStatus", "string"),
                col_block("IsDeliveredFlag", "string"),
                col_block("IsCancelledFlag", "string"),
            ],
            m_csv(
                "DimOrderStatus.csv",
                [
                    ("OrderStatusKey", "Int64.Type"),
                    ("OrderStatus", "type text"),
                    ("IsDeliveredFlag", "type text"),
                    ("IsCancelledFlag", "type text"),
                ],
            ),
        ),
    )

    sales_measures = [
        measure("Revenue", "SUM ( FactSales[LineTotal] )", "$#,##0", "Gross merchandise value from line totals"),
        measure("Items Sold", "SUM ( FactSales[Quantity] )", "#,##0", "Units sold"),
        measure("Order Count", "DISTINCTCOUNT ( FactSales[OrderID] )", "#,##0", "Distinct orders"),
        measure("AOV", "DIVIDE ( [Revenue], [Order Count] )", "$#,##0", "Average order value"),
        measure("Avg Review", "AVERAGE ( FactSales[ReviewScore] )", "0.00", "Mean review score"),
        measure("Avg Delivery Days", "AVERAGE ( FactSales[DeliveryDays] )", "0.0", "Mean days to customer"),
        measure(
            "On Time Items",
            "CALCULATE ( [Items Sold], FactSales[OnTimeFlag] = \"Y\" )",
            "#,##0",
            "Items delivered on or before estimate",
        ),
        measure("On Time Rate", "DIVIDE ( [On Time Items], [Items Sold] )", "0.0%", "Share of on-time items"),
        measure("Freight Ratio", "DIVIDE ( SUM ( FactSales[FreightValue] ), [Revenue] )", "0.0%", "Freight as share of GMV"),
        measure(
            "YoY Revenue",
            "VAR Prev =\n    CALCULATE ( [Revenue], DATEADD ( DimDate[FullDate], -1, YEAR ) )\nRETURN\n    DIVIDE ( [Revenue] - Prev, Prev )",
            "0.0%",
            "Year-over-year revenue change",
        ),
        measure(
            "Delivered Revenue",
            "CALCULATE ( [Revenue], DimOrderStatus[IsDeliveredFlag] = \"Y\" )",
            "$#,##0",
            "Revenue from delivered orders",
        ),
        measure(
            "Delivered Orders",
            "CALCULATE ( [Order Count], DimOrderStatus[IsDeliveredFlag] = \"Y\" )",
            "#,##0",
            "Distinct delivered orders",
        ),
        measure("Holiday Revenue", "CALCULATE ( [Revenue], DimDate[IsHoliday] = 1 )", "$#,##0", "Revenue on public holidays"),
        measure("Bad Review Items", "CALCULATE ( [Items Sold], FactSales[ReviewScore] < 3 )", "#,##0", "Items with review below 3"),
        measure("Bad Review Rate", "DIVIDE ( [Bad Review Items], [Items Sold] )", "0.0%", "Share of poor reviews"),
    ]

    sales_cols = [
        col_block("SalesKey", "int64", hidden=True),
        col_block("PurchaseDateKey", "int64", hidden=True),
        col_block("DeliveredDateKey", "int64", hidden=True),
        col_block("EstimatedDeliveryDateKey", "int64", hidden=True),
        col_block("CustomerKey", "int64", hidden=True),
        col_block("ProductKey", "int64", hidden=True),
        col_block("SellerKey", "int64", hidden=True),
        col_block("CustomerGeoKey", "int64", hidden=True),
        col_block("PaymentTypeKey", "int64", hidden=True),
        col_block("OrderStatusKey", "int64", hidden=True),
        col_block("OrderID", "string"),
        col_block("OrderItemID", "int64", hidden=True),
        col_block("Price", "decimal", extra=["formatString: #,##0.00"]),
        col_block("FreightValue", "decimal", extra=["formatString: #,##0.00"]),
        col_block("LineTotal", "decimal", extra=["formatString: #,##0.00"]),
        col_block("Quantity", "int64", summarize="sum"),
        col_block("DeliveryDays", "double"),
        col_block("DelayDays", "double"),
        col_block("OnTimeFlag", "string"),
        col_block("ReviewScore", "double"),
    ]
    write(
        TDIR / "FactSales.tmdl",
        table_tmdl(
            "FactSales",
            sales_measures,
            sales_cols,
            m_csv(
                "FactSales.csv",
                [
                    ("SalesKey", "Int64.Type"),
                    ("PurchaseDateKey", "Int64.Type"),
                    ("DeliveredDateKey", "Int64.Type"),
                    ("EstimatedDeliveryDateKey", "Int64.Type"),
                    ("CustomerKey", "Int64.Type"),
                    ("ProductKey", "Int64.Type"),
                    ("SellerKey", "Int64.Type"),
                    ("CustomerGeoKey", "Int64.Type"),
                    ("PaymentTypeKey", "Int64.Type"),
                    ("OrderStatusKey", "Int64.Type"),
                    ("OrderID", "type text"),
                    ("OrderItemID", "Int64.Type"),
                    ("Price", "type number"),
                    ("FreightValue", "type number"),
                    ("LineTotal", "type number"),
                    ("Quantity", "Int64.Type"),
                    ("DeliveryDays", "type number"),
                    ("DelayDays", "type number"),
                    ("OnTimeFlag", "type text"),
                    ("ReviewScore", "type number"),
                ],
            ),
        ),
    )

    pay_measures = [
        measure("Payment Value", "SUM ( FactPayment[PaymentValue] )", "$#,##0", "Sum of payment attempts"),
        measure("Payment Count", "COUNTROWS ( FactPayment )", "#,##0", "Payment attempt rows"),
        measure("Avg Installments", "AVERAGE ( FactPayment[PaymentInstallments] )", "0.0", "Mean installment count"),
    ]
    pay_cols = [
        col_block("PaymentKey", "int64", hidden=True),
        col_block("PurchaseDateKey", "int64", hidden=True),
        col_block("CustomerKey", "int64", hidden=True),
        col_block("PaymentTypeKey", "int64", hidden=True),
        col_block("OrderID", "string"),
        col_block("PaymentSequential", "int64"),
        col_block("PaymentInstallments", "int64", summarize="sum"),
        col_block("PaymentValue", "decimal", extra=["formatString: #,##0.00"]),
    ]
    write(
        TDIR / "FactPayment.tmdl",
        table_tmdl(
            "FactPayment",
            pay_measures,
            pay_cols,
            m_csv(
                "FactPayment.csv",
                [
                    ("PaymentKey", "Int64.Type"),
                    ("PurchaseDateKey", "Int64.Type"),
                    ("CustomerKey", "Int64.Type"),
                    ("PaymentTypeKey", "Int64.Type"),
                    ("OrderID", "type text"),
                    ("PaymentSequential", "Int64.Type"),
                    ("PaymentInstallments", "Int64.Type"),
                    ("PaymentValue", "type number"),
                ],
            ),
        ),
    )


def col_field(table: str, column: str) -> dict:
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": column,
        }
    }


def meas_field(table: str, measure_name: str) -> dict:
    return {
        "Measure": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": measure_name,
        }
    }


def proj(field: dict, table: str, prop: str) -> dict:
    return {"field": field, "queryRef": f"{table}.{prop}", "nativeQueryRef": prop}


def title_vco(text: str) -> dict:
    return {
        "title": [
            {
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": f"'{text}'"}}},
                }
            }
        ]
    }


def padding_vco() -> dict:
    lit = lambda n: {"expr": {"Literal": {"Value": f"{n}D"}}}
    return {
        "padding": [
            {
                "properties": {
                    "top": lit(8),
                    "bottom": lit(8),
                    "left": lit(8),
                    "right": lit(8),
                }
            }
        ]
    }


def visual(name: str, vtype: str, x, y, w, h, z, query_state: dict, extra_visual: dict | None = None, vco: dict | None = None) -> dict:
    vis: dict = {
        "visualType": vtype,
        "query": {"queryState": query_state},
        "drillFilterOtherVisuals": True,
    }
    if extra_visual:
        vis.update(extra_visual)
    if vco:
        vis["visualContainerObjects"] = vco
    return {
        "$schema": VSCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": vis,
    }


def textbox(name: str, x, y, w, h, z, text: str, size="18pt", bold=True) -> dict:
    run = {"value": text, "textStyle": {"fontSize": size}}
    if bold:
        run["textStyle"]["fontWeight"] = "bold"
    return {
        "$schema": VSCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [run]}]}}]},
        },
    }


def slicer(name: str, x, y, w, table: str, column: str, header: str) -> dict:
    v = visual(
        name,
        "slicer",
        x,
        y,
        w,
        80,
        2000,
        {"Values": {"projections": [proj(col_field(table, column), table, column)]}},
        extra_visual={
            "objects": {
                "data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}],
                "header": [
                    {
                        "properties": {
                            "show": {"expr": {"Literal": {"Value": "true"}}},
                            "text": {"expr": {"Literal": {"Value": f"'{header}'"}}},
                        }
                    }
                ],
            }
        },
        vco=padding_vco(),
    )
    return v


def save_visual(page: str, obj: dict) -> None:
    folder = REP / "definition" / "pages" / page / "visuals" / obj["name"]
    dump(folder / "visual.json", obj)


def page_json(name: str, display: str) -> dict:
    return {
        "$schema": PSCHEMA,
        "name": name,
        "displayName": display,
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
        "objects": {
            "background": [
                {
                    "properties": {
                        "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#F8FAFC'"}}}}},
                        "transparency": {"expr": {"Literal": {"Value": "0D"}}},
                    }
                }
            ]
        },
    }


def add_slicers(page: str, y=64) -> None:
    save_visual(page, slicer(hid(page, "s_year"), 16, y, 240, "DimDate", "YearNumber", "Year"))
    save_visual(page, slicer(hid(page, "s_region"), 272, y, 280, "DimCustomer", "CustomerRegion", "Region"))
    save_visual(page, slicer(hid(page, "s_status"), 568, y, 280, "DimOrderStatus", "OrderStatus", "Order status"))


def build_report() -> None:
    dump(
        PROJ / "Olist_DWBI.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "Olist_DWBI.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    dump(
        REP / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../Olist_DWBI.SemanticModel"}},
        },
    )
    dump(
        REP / "definition" / "version.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    dump(
        REP / "definition" / "report.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/2.0.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU10",
                    "reportVersionAtImport": "5.62",
                    "type": "SharedResources",
                }
            },
            "layoutOptimization": "None",
            "objects": {
                "section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}]
            },
        },
    )

    pages = [
        ("ExecutiveSummary", "1. Executive Summary"),
        ("ProductQuality", "2. Product Quality"),
        ("Logistics", "3. Logistics"),
        ("Payments", "4. Payments"),
    ]
    dump(
        REP / "definition" / "pages" / "pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [p[0] for p in pages],
            "activePageName": "ExecutiveSummary",
        },
    )
    for pid, title in pages:
        dump(REP / "definition" / "pages" / pid / "page.json", page_json(pid, title))

    # ----- Page 1 Executive -----
    p = "ExecutiveSummary"
    save_visual(p, textbox(hid(p, "title"), 16, 8, 900, 48, 100, "Olist Executive Summary", "22pt"))
    save_visual(p, textbox(hid(p, "sub"), 16, 48, 900, 24, 101, "Brazilian e-commerce warehouse  |  click Year / Region / Status to filter", "10pt", bold=False))
    add_slicers(p, 72)
    save_visual(
        p,
        visual(
            hid(p, "kpis"),
            "cardVisual",
            16,
            168,
            1248,
            120,
            500,
            {
                "Data": {
                    "projections": [
                        proj(meas_field("FactSales", "Delivered Revenue"), "FactSales", "Delivered Revenue"),
                        proj(meas_field("FactSales", "Delivered Orders"), "FactSales", "Delivered Orders"),
                        proj(meas_field("FactSales", "On Time Rate"), "FactSales", "On Time Rate"),
                        proj(meas_field("FactSales", "Avg Review"), "FactSales", "Avg Review"),
                        proj(meas_field("FactSales", "Avg Delivery Days"), "FactSales", "Avg Delivery Days"),
                    ]
                }
            },
        ),
    )
    save_visual(
        p,
        visual(
            hid(p, "month"),
            "lineChart",
            16,
            304,
            624,
            392,
            400,
            {
                "Category": {"projections": [proj(col_field("DimDate", "YearMonth"), "DimDate", "YearMonth")]},
                "Y": {"projections": [proj(meas_field("FactSales", "Delivered Revenue"), "FactSales", "Delivered Revenue")]},
            },
            vco=title_vco("Monthly delivered revenue"),
        ),
    )
    save_visual(
        p,
        visual(
            hid(p, "region"),
            "clusteredBarChart",
            656,
            304,
            608,
            392,
            401,
            {
                "Category": {"projections": [proj(col_field("DimCustomer", "CustomerRegion"), "DimCustomer", "CustomerRegion")]},
                "Y": {"projections": [proj(meas_field("FactSales", "Delivered Revenue"), "FactSales", "Delivered Revenue")]},
            },
            extra_visual={
                "query": {
                    "queryState": {
                        "Category": {"projections": [proj(col_field("DimCustomer", "CustomerRegion"), "DimCustomer", "CustomerRegion")]},
                        "Y": {"projections": [proj(meas_field("FactSales", "Delivered Revenue"), "FactSales", "Delivered Revenue")]},
                    },
                    "sortDefinition": {
                        "sort": [{"field": meas_field("FactSales", "Delivered Revenue"), "direction": "Descending"}],
                        "isDefaultSort": True,
                    },
                }
            },
            vco=title_vco("Revenue by customer region"),
        ),
    )

    # ----- Page 2 Product -----
    p = "ProductQuality"
    save_visual(p, textbox(hid(p, "title"), 16, 8, 900, 48, 100, "Product quality vs revenue", "22pt"))
    add_slicers(p, 64)
    save_visual(
        p,
        visual(
            hid(p, "catrev"),
            "clusteredBarChart",
            16,
            160,
            624,
            536,
            400,
            {
                "Category": {"projections": [proj(col_field("DimProduct", "CategoryNameEnglish"), "DimProduct", "CategoryNameEnglish")]},
                "Y": {
                    "projections": [
                        proj(meas_field("FactSales", "Revenue"), "FactSales", "Revenue"),
                    ]
                },
            },
            extra_visual={
                "query": {
                    "queryState": {
                        "Category": {"projections": [proj(col_field("DimProduct", "CategoryNameEnglish"), "DimProduct", "CategoryNameEnglish")]},
                        "Y": {"projections": [proj(meas_field("FactSales", "Revenue"), "FactSales", "Revenue")]},
                    },
                    "sortDefinition": {
                        "sort": [{"field": meas_field("FactSales", "Revenue"), "direction": "Descending"}],
                        "isDefaultSort": True,
                    },
                }
            },
            vco=title_vco("Category revenue"),
        ),
    )
    save_visual(
        p,
        visual(
            hid(p, "catqual"),
            "clusteredBarChart",
            656,
            160,
            608,
            260,
            401,
            {
                "Category": {"projections": [proj(col_field("DimProduct", "CategoryNameEnglish"), "DimProduct", "CategoryNameEnglish")]},
                "Y": {"projections": [proj(meas_field("FactSales", "Avg Review"), "FactSales", "Avg Review")]},
            },
            vco=title_vco("Average review by category"),
        ),
    )
    save_visual(
        p,
        visual(
            hid(p, "catontime"),
            "clusteredBarChart",
            656,
            436,
            608,
            260,
            402,
            {
                "Category": {"projections": [proj(col_field("DimProduct", "CategoryNameEnglish"), "DimProduct", "CategoryNameEnglish")]},
                "Y": {"projections": [proj(meas_field("FactSales", "On Time Rate"), "FactSales", "On Time Rate")]},
            },
            extra_visual={
                "query": {
                    "queryState": {
                        "Category": {"projections": [proj(col_field("DimProduct", "CategoryNameEnglish"), "DimProduct", "CategoryNameEnglish")]},
                        "Y": {"projections": [proj(meas_field("FactSales", "On Time Rate"), "FactSales", "On Time Rate")]},
                    },
                    "sortDefinition": {
                        "sort": [{"field": meas_field("FactSales", "On Time Rate"), "direction": "Ascending"}],
                        "isDefaultSort": True,
                    },
                }
            },
            vco=title_vco("On-time rate by category (worst first)"),
        ),
    )

    # ----- Page 3 Logistics -----
    p = "Logistics"
    save_visual(p, textbox(hid(p, "title"), 16, 8, 900, 48, 100, "Logistics and delivery performance", "22pt"))
    add_slicers(p, 64)
    save_visual(
        p,
        visual(
            hid(p, "holiday"),
            "clusteredColumnChart",
            16,
            160,
            408,
            260,
            400,
            {
                "Category": {"projections": [proj(col_field("DimDate", "IsHoliday"), "DimDate", "IsHoliday")]},
                "Y": {"projections": [proj(meas_field("FactSales", "Revenue"), "FactSales", "Revenue")]},
            },
            vco=title_vco("Holiday (1) vs normal (0) revenue"),
        ),
    )
    save_visual(
        p,
        visual(
            hid(p, "state"),
            "clusteredBarChart",
            440,
            160,
            824,
            260,
            401,
            {
                "Category": {"projections": [proj(col_field("DimCustomer", "CustomerState"), "DimCustomer", "CustomerState")]},
                "Y": {"projections": [proj(meas_field("FactSales", "Avg Delivery Days"), "FactSales", "Avg Delivery Days")]},
            },
            extra_visual={
                "query": {
                    "queryState": {
                        "Category": {"projections": [proj(col_field("DimCustomer", "CustomerState"), "DimCustomer", "CustomerState")]},
                        "Y": {"projections": [proj(meas_field("FactSales", "Avg Delivery Days"), "FactSales", "Avg Delivery Days")]},
                    },
                    "sortDefinition": {
                        "sort": [{"field": meas_field("FactSales", "Avg Delivery Days"), "direction": "Descending"}],
                        "isDefaultSort": True,
                    },
                }
            },
            vco=title_vco("Average delivery days by state"),
        ),
    )
    save_visual(
        p,
        visual(
            hid(p, "delaycat"),
            "clusteredBarChart",
            16,
            436,
            624,
            260,
            402,
            {
                "Category": {"projections": [proj(col_field("DimProduct", "CategoryNameEnglish"), "DimProduct", "CategoryNameEnglish")]},
                "Y": {"projections": [proj(meas_field("FactSales", "On Time Rate"), "FactSales", "On Time Rate")]},
            },
            extra_visual={
                "query": {
                    "queryState": {
                        "Category": {"projections": [proj(col_field("DimProduct", "CategoryNameEnglish"), "DimProduct", "CategoryNameEnglish")]},
                        "Y": {"projections": [proj(meas_field("FactSales", "On Time Rate"), "FactSales", "On Time Rate")]},
                    },
                    "sortDefinition": {
                        "sort": [{"field": meas_field("FactSales", "On Time Rate"), "direction": "Ascending"}],
                        "isDefaultSort": True,
                    },
                }
            },
            vco=title_vco("Slowest categories (on-time %)"),
        ),
    )
    save_visual(
        p,
        visual(
            hid(p, "badr"),
            "cardVisual",
            656,
            436,
            608,
            260,
            403,
            {
                "Data": {
                    "projections": [
                        proj(meas_field("FactSales", "Avg Delivery Days"), "FactSales", "Avg Delivery Days"),
                        proj(meas_field("FactSales", "On Time Rate"), "FactSales", "On Time Rate"),
                        proj(meas_field("FactSales", "Bad Review Rate"), "FactSales", "Bad Review Rate"),
                        proj(meas_field("FactSales", "Freight Ratio"), "FactSales", "Freight Ratio"),
                    ]
                }
            },
        ),
    )

    # ----- Page 4 Payments -----
    p = "Payments"
    save_visual(p, textbox(hid(p, "title"), 16, 8, 900, 48, 100, "Payment mix and installments", "22pt"))
    add_slicers(p, 64)
    save_visual(
        p,
        visual(
            hid(p, "donut"),
            "donutChart",
            16,
            160,
            500,
            536,
            400,
            {
                "Category": {"projections": [proj(col_field("DimPaymentType", "PaymentType"), "DimPaymentType", "PaymentType")]},
                "Y": {"projections": [proj(meas_field("FactPayment", "Payment Value"), "FactPayment", "Payment Value")]},
            },
            vco=title_vco("Payment value by type"),
        ),
    )
    save_visual(
        p,
        visual(
            hid(p, "inst"),
            "clusteredColumnChart",
            532,
            160,
            732,
            260,
            401,
            {
                "Category": {"projections": [proj(col_field("FactPayment", "PaymentInstallments"), "FactPayment", "PaymentInstallments")]},
                "Y": {"projections": [proj(meas_field("FactPayment", "Payment Count"), "FactPayment", "Payment Count")]},
            },
            vco=title_vco("How many payments use N installments"),
        ),
    )
    save_visual(
        p,
        visual(
            hid(p, "paycards"),
            "cardVisual",
            532,
            436,
            732,
            260,
            402,
            {
                "Data": {
                    "projections": [
                        proj(meas_field("FactPayment", "Payment Value"), "FactPayment", "Payment Value"),
                        proj(meas_field("FactPayment", "Payment Count"), "FactPayment", "Payment Count"),
                        proj(meas_field("FactPayment", "Avg Installments"), "FactPayment", "Avg Installments"),
                    ]
                }
            },
        ),
    )


def main() -> None:
    if PROJ.exists():
        import shutil

        shutil.rmtree(PROJ)
    build_model()
    build_report()
    # shortcut at 07_BI root
    dump(
        ROOT / "Olist_DWBI.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "Olist_DWBI/Olist_DWBI.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    print(f"Wrote {PROJ}")


if __name__ == "__main__":
    main()
