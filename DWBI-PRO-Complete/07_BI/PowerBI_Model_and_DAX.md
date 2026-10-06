# Power BI model (connect to Gold CSVs or to OlistDW)

## Get data

**Preferred:** SQL Server `OlistDW` tables in schema `dw` (DirectQuery or Import).

**Fallback (no SQL Server):** import every file in `08_GoldLayer\`.

Relationships (star, single direction, many-to-one):

```
FactSales[PurchaseDateKey]     → DimDate[DateKey]
FactSales[CustomerKey]         → DimCustomer[CustomerKey]
FactSales[ProductKey]          → DimProduct[ProductKey]
FactSales[SellerKey]           → DimSeller[SellerKey]
FactSales[PaymentTypeKey]      → DimPaymentType[PaymentTypeKey]
FactSales[OrderStatusKey]      → DimOrderStatus[OrderStatusKey]
FactSales[CustomerGeoKey]      → DimGeolocation[GeoKey]
FactPayment[PurchaseDateKey]   → DimDate[DateKey]
FactPayment[CustomerKey]       → DimCustomer[CustomerKey]
FactPayment[PaymentTypeKey]    → DimPaymentType[PaymentTypeKey]
```

Hide all `*Key` columns from Report view except when debugging.

## Report pages (build these four pages)

1. **Executive** — KPIs + monthly trend + region map/bar  
2. **Product quality** — category revenue vs average review vs on-time %  
3. **Logistics** — delivery days histogram, delay by state, holiday vs normal  
4. **Payments** — mix, installments, boleto vs card  

Use a **slicer** on Year, Region, and Order Status on every page. Add **drill-through** from a category bar to page 2.

## DAX measures

```dax
Revenue := SUM ( FactSales[LineTotal] )

Items Sold := SUM ( FactSales[Quantity] )

Order Count := DISTINCTCOUNT ( FactSales[OrderID] )

AOV := DIVIDE ( [Revenue], [Order Count] )

Avg Review := AVERAGE ( FactSales[ReviewScore] )

Avg Delivery Days := AVERAGE ( FactSales[DeliveryDays] )

On Time Items :=
CALCULATE (
    [Items Sold],
    FactSales[OnTimeFlag] = "Y"
)

On Time Rate := DIVIDE ( [On Time Items], [Items Sold] )

Freight Ratio := DIVIDE ( SUM ( FactSales[FreightValue] ), [Revenue] )

YoY Revenue :=
VAR Prev =
    CALCULATE ( [Revenue], DATEADD ( DimDate[FullDate], -1, YEAR ) )
RETURN
    DIVIDE ( [Revenue] - Prev, Prev )

Delivered Revenue :=
CALCULATE ( [Revenue], DimOrderStatus[IsDeliveredFlag] = "Y" )

Holiday Revenue :=
CALCULATE ( [Revenue], DimDate[IsHoliday] = 1 )

Bad Review Items :=
CALCULATE ( [Items Sold], FactSales[ReviewScore] < 3 )

Bad Review Rate := DIVIDE ( [Bad Review Items], [Items Sold] )
```

## Example visuals

| Page | Visual | Fields |
|---|---|---|
| Executive | Card | Delivered Revenue, Order Count, On Time Rate, Avg Review |
| Executive | Line | YearMonth vs Revenue |
| Executive | Map or bar | CustomerState vs Revenue |
| Product | Clustered bar | Category vs Revenue, Avg Review |
| Logistics | Bar | Category vs On Time Rate (ascending) |
| Payments | Donut | PaymentType vs PaymentValue |

## Open the finished dashboard (do this)

The Power BI project is already built in `07_BI`.

1. Double-click `D:\DWBI-PRO\DWBI-Complete\07_BI\Olist_DWBI.pbip`  
   (or run `Open_PowerBI_Dashboard.bat` in the same folder).
2. If Power BI asks to **apply changes** or **refresh**, click **Apply** / **Refresh**. Wait until the gold CSVs finish loading (~30–60 seconds).
3. You should see four pages at the bottom: **Executive Summary**, **Product Quality**, **Logistics**, **Payments**.
4. Click the **Year**, **Region**, and **Order status** dropdowns — that is the interactive part the assignment marks.
5. For submission: **File → Save as →** `Olist_DWBI.pbix` and put screenshots of all four pages in the report.

If the file does not open, enable: **File → Options → Preview features → Store reports using enhanced metadata format (PBIR)**, then reopen the `.pbip`.

The HTML file `Olist_Executive_Dashboard.html` is only a backup preview. Submit Power BI, not HTML.
