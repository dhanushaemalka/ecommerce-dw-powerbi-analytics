/*
    OLAP-style queries (slice, dice, roll-up, drill-down, pivot)
    Use these as SSAS cube validation AND Excel / SQL evidence.
*/
USE OlistDW;
GO

/* 1. ROLL-UP: Year -> Quarter revenue */
SELECT
    d.YearNumber,
    d.QuarterName,
    SUM(f.LineTotal) AS Revenue,
    SUM(f.Quantity)  AS ItemsSold,
    COUNT(DISTINCT f.OrderID) AS Orders
FROM dw.FactSales f
JOIN dw.DimDate d ON d.DateKey = f.PurchaseDateKey
JOIN dw.DimOrderStatus s ON s.OrderStatusKey = f.OrderStatusKey
WHERE s.IsDeliveredFlag = 'Y'
GROUP BY d.YearNumber, d.QuarterName
ORDER BY d.YearNumber, d.QuarterName;

/* 2. DRILL-DOWN: Year 2017 by month */
SELECT
    d.YearMonth,
    d.MonthName,
    SUM(f.LineTotal) AS Revenue
FROM dw.FactSales f
JOIN dw.DimDate d ON d.DateKey = f.PurchaseDateKey
WHERE d.YearNumber = 2017
GROUP BY d.YearMonth, d.MonthName, d.MonthNumber
ORDER BY d.MonthNumber;

/* 3. SLICE: Southeast customers only */
SELECT
    p.CategoryNameEnglish,
    SUM(f.LineTotal) AS Revenue
FROM dw.FactSales f
JOIN dw.DimCustomer c ON c.CustomerKey = f.CustomerKey
JOIN dw.DimProduct p ON p.ProductKey = f.ProductKey
WHERE c.CustomerRegion = 'Southeast'
GROUP BY p.CategoryNameEnglish
ORDER BY Revenue DESC;

/* 4. DICE: 2018 + credit card + delivered */
SELECT
    c.CustomerState,
    SUM(f.LineTotal) AS Revenue,
    AVG(CAST(f.ReviewScore AS FLOAT)) AS AvgReview
FROM dw.FactSales f
JOIN dw.DimDate d ON d.DateKey = f.PurchaseDateKey
JOIN dw.DimCustomer c ON c.CustomerKey = f.CustomerKey
JOIN dw.DimPaymentType pt ON pt.PaymentTypeKey = f.PaymentTypeKey
JOIN dw.DimOrderStatus s ON s.OrderStatusKey = f.OrderStatusKey
WHERE d.YearNumber = 2018
  AND pt.PaymentType = 'credit_card'
  AND s.IsDeliveredFlag = 'Y'
GROUP BY c.CustomerState
ORDER BY Revenue DESC;

/* 5. PIVOT: revenue by region across years */
SELECT *
FROM (
    SELECT c.CustomerRegion, d.YearNumber, f.LineTotal
    FROM dw.FactSales f
    JOIN dw.DimCustomer c ON c.CustomerKey = f.CustomerKey
    JOIN dw.DimDate d ON d.DateKey = f.PurchaseDateKey
    JOIN dw.DimOrderStatus s ON s.OrderStatusKey = f.OrderStatusKey
    WHERE s.IsDeliveredFlag = 'Y'
) src
PIVOT (
    SUM(LineTotal) FOR YearNumber IN ([2016], [2017], [2018])
) p
ORDER BY CustomerRegion;

/* 6. KPI: on-time delivery rate by category */
SELECT
    p.CategoryNameEnglish,
    COUNT(*) AS DeliveredItems,
    SUM(CASE WHEN f.OnTimeFlag = 'Y' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS OnTimePct,
    AVG(CAST(f.DeliveryDays AS FLOAT)) AS AvgDeliveryDays,
    AVG(CAST(f.ReviewScore AS FLOAT)) AS AvgReview
FROM dw.FactSales f
JOIN dw.DimProduct p ON p.ProductKey = f.ProductKey
JOIN dw.DimOrderStatus s ON s.OrderStatusKey = f.OrderStatusKey
WHERE s.IsDeliveredFlag = 'Y'
  AND f.OnTimeFlag IS NOT NULL
GROUP BY p.CategoryNameEnglish
HAVING COUNT(*) >= 200
ORDER BY OnTimePct ASC;

/* 7. Holiday vs non-holiday sales */
SELECT
    CASE WHEN d.IsHoliday = 1 THEN 'Holiday' ELSE 'Non-holiday' END AS DayType,
    COUNT(DISTINCT f.OrderID) AS Orders,
    SUM(f.LineTotal) AS Revenue,
    AVG(CAST(f.ReviewScore AS FLOAT)) AS AvgReview
FROM dw.FactSales f
JOIN dw.DimDate d ON d.DateKey = f.PurchaseDateKey
GROUP BY CASE WHEN d.IsHoliday = 1 THEN 'Holiday' ELSE 'Non-holiday' END;

/* 8. Quality check: orphan facts */
SELECT 'Missing customer' AS Issue, COUNT(*) AS RowsFound
FROM dw.FactSales WHERE CustomerKey = -1
UNION ALL
SELECT 'Missing product', COUNT(*) FROM dw.FactSales WHERE ProductKey = -1
UNION ALL
SELECT 'Missing seller', COUNT(*) FROM dw.FactSales WHERE SellerKey = -1
UNION ALL
SELECT 'Missing purchase date', COUNT(*) FROM dw.FactSales WHERE PurchaseDateKey = 19000101;
GO
