/*
    Transform + Load from stg -> dw
    Mirrors SSIS Execute SQL Tasks after staging Data Flows complete.
    Unknown members use key = 1 after IDENTITY insert of a sentinel row,
    but we insert sentinels first so IDENTITY starts at 1 for Unknown.
*/
USE OlistDW;
GO

CREATE OR ALTER PROCEDURE dw.usp_LoadDimensions
AS
BEGIN
    SET NOCOUNT ON;

    /* ---- DimDate ---- */
    TRUNCATE TABLE dw.FactPayment;
    TRUNCATE TABLE dw.FactSales;

    DELETE FROM dw.DimCustomer;
    DELETE FROM dw.DimProduct;
    DELETE FROM dw.DimSeller;
    DELETE FROM dw.DimGeolocation;
    DELETE FROM dw.DimPaymentType;
    DELETE FROM dw.DimOrderStatus;
    DELETE FROM dw.DimDate;

    IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID('dw.DimCustomer') AND last_value IS NOT NULL)
        DBCC CHECKIDENT ('dw.DimCustomer', RESEED, 0);
    IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID('dw.DimProduct') AND last_value IS NOT NULL)
        DBCC CHECKIDENT ('dw.DimProduct', RESEED, 0);
    IF EXISTS (SELECT 1 FROM sys.identity_columns WHERE object_id = OBJECT_ID('dw.DimSeller') AND last_value IS NOT NULL)
        DBCC CHECKIDENT ('dw.DimSeller', RESEED, 0);

    DECLARE @Start DATE = '2016-01-01';
    DECLARE @End   DATE = '2018-12-31';

    ;WITH Dates AS (
        SELECT @Start AS d
        UNION ALL
        SELECT DATEADD(DAY, 1, d) FROM Dates WHERE d < @End
    )
    INSERT INTO dw.DimDate (
        DateKey, FullDate, DayNumber, DayName, WeekdayFlag, WeekendFlag,
        WeekOfYear, MonthNumber, MonthName, QuarterNumber, QuarterName,
        YearNumber, YearMonth, IsHoliday, HolidayName
    )
    SELECT
        YEAR(d) * 10000 + MONTH(d) * 100 + DAY(d),
        d,
        DAY(d),
        DATENAME(WEEKDAY, d),
        CASE WHEN DATEPART(WEEKDAY, d) IN (1, 7) THEN 'N' ELSE 'Y' END,
        CASE WHEN DATEPART(WEEKDAY, d) IN (1, 7) THEN 'Y' ELSE 'N' END,
        DATEPART(ISO_WEEK, d),
        MONTH(d),
        DATENAME(MONTH, d),
        DATEPART(QUARTER, d),
        'Q' + CAST(DATEPART(QUARTER, d) AS CHAR(1)),
        YEAR(d),
        FORMAT(d, 'yyyy-MM'),
        CASE WHEN h.holiday_date IS NULL THEN 0 ELSE 1 END,
        h.english_name
    FROM Dates
    LEFT JOIN (
        SELECT holiday_date, MAX(english_name) AS english_name
        FROM stg.Holidays
        GROUP BY holiday_date
    ) h ON h.holiday_date = Dates.d
    OPTION (MAXRECURSION 0);

    INSERT INTO dw.DimDate (
        DateKey, FullDate, DayNumber, DayName, WeekdayFlag, WeekendFlag,
        WeekOfYear, MonthNumber, MonthName, QuarterNumber, QuarterName,
        YearNumber, YearMonth, IsHoliday, HolidayName
    )
    SELECT 19000101, '1900-01-01', 1, 'Monday', 'Y', 'N', 1, 1, 'January', 1, 'Q1', 1900, '1900-01', 0, NULL
    WHERE NOT EXISTS (SELECT 1 FROM dw.DimDate WHERE DateKey = 19000101);

    /* ---- DimPaymentType ---- */
    INSERT INTO dw.DimPaymentType (PaymentType, PaymentTypeGroup)
    SELECT DISTINCT
        ISNULL(NULLIF(LTRIM(RTRIM(payment_type)), ''), 'not_defined'),
        CASE
            WHEN payment_type IN ('credit_card', 'debit_card') THEN 'Card'
            WHEN payment_type = 'boleto' THEN 'Bank slip'
            WHEN payment_type = 'voucher' THEN 'Voucher'
            ELSE 'Other'
        END
    FROM stg.Payments;

    IF NOT EXISTS (SELECT 1 FROM dw.DimPaymentType WHERE PaymentType = 'unknown')
        INSERT INTO dw.DimPaymentType (PaymentType, PaymentTypeGroup) VALUES ('unknown', 'Other');

    /* ---- DimOrderStatus ---- */
    INSERT INTO dw.DimOrderStatus (OrderStatus, IsDeliveredFlag, IsCancelledFlag)
    SELECT DISTINCT
        order_status,
        CASE WHEN order_status = 'delivered' THEN 'Y' ELSE 'N' END,
        CASE WHEN order_status IN ('canceled', 'cancelled') THEN 'Y' ELSE 'N' END
    FROM stg.Orders;

    /* ---- DimGeolocation (deduplicate zip prefixes) ---- */
    INSERT INTO dw.DimGeolocation (ZipPrefix, City, State, Region, Latitude, Longitude)
    SELECT
        geolocation_zip_code_prefix,
        MAX(geolocation_city),
        MAX(geolocation_state),
        CASE MAX(geolocation_state)
            WHEN 'AC' THEN 'North' WHEN 'AP' THEN 'North' WHEN 'AM' THEN 'North'
            WHEN 'PA' THEN 'North' WHEN 'RO' THEN 'North' WHEN 'RR' THEN 'North' WHEN 'TO' THEN 'North'
            WHEN 'AL' THEN 'Northeast' WHEN 'BA' THEN 'Northeast' WHEN 'CE' THEN 'Northeast'
            WHEN 'MA' THEN 'Northeast' WHEN 'PB' THEN 'Northeast' WHEN 'PE' THEN 'Northeast'
            WHEN 'PI' THEN 'Northeast' WHEN 'RN' THEN 'Northeast' WHEN 'SE' THEN 'Northeast'
            WHEN 'DF' THEN 'Center-West' WHEN 'GO' THEN 'Center-West'
            WHEN 'MT' THEN 'Center-West' WHEN 'MS' THEN 'Center-West'
            WHEN 'ES' THEN 'Southeast' WHEN 'MG' THEN 'Southeast'
            WHEN 'RJ' THEN 'Southeast' WHEN 'SP' THEN 'Southeast'
            WHEN 'PR' THEN 'South' WHEN 'RS' THEN 'South' WHEN 'SC' THEN 'South'
            ELSE 'Unknown'
        END,
        AVG(geolocation_lat),
        AVG(geolocation_lng)
    FROM stg.Geolocation
    GROUP BY geolocation_zip_code_prefix;

    /* ---- Unknown members ---- */
    SET IDENTITY_INSERT dw.DimCustomer ON;
    INSERT INTO dw.DimCustomer (CustomerKey, CustomerID, CustomerUniqueID, CustomerCity, CustomerState, CustomerRegion, CustomerZipPrefix, IsUnknown)
    VALUES (-1, 'UNKNOWN', 'UNKNOWN', 'Unknown', 'XX', 'Unknown', 0, 1);
    SET IDENTITY_INSERT dw.DimCustomer OFF;

    INSERT INTO dw.DimCustomer (CustomerID, CustomerUniqueID, CustomerCity, CustomerState, CustomerRegion, CustomerZipPrefix, IsUnknown)
    SELECT
        c.customer_id,
        c.customer_unique_id,
        LOWER(LTRIM(RTRIM(c.customer_city))),
        UPPER(LTRIM(RTRIM(c.customer_state))),
        CASE UPPER(LTRIM(RTRIM(c.customer_state)))
            WHEN 'AC' THEN 'North' WHEN 'AP' THEN 'North' WHEN 'AM' THEN 'North'
            WHEN 'PA' THEN 'North' WHEN 'RO' THEN 'North' WHEN 'RR' THEN 'North' WHEN 'TO' THEN 'North'
            WHEN 'AL' THEN 'Northeast' WHEN 'BA' THEN 'Northeast' WHEN 'CE' THEN 'Northeast'
            WHEN 'MA' THEN 'Northeast' WHEN 'PB' THEN 'Northeast' WHEN 'PE' THEN 'Northeast'
            WHEN 'PI' THEN 'Northeast' WHEN 'RN' THEN 'Northeast' WHEN 'SE' THEN 'Northeast'
            WHEN 'DF' THEN 'Center-West' WHEN 'GO' THEN 'Center-West'
            WHEN 'MT' THEN 'Center-West' WHEN 'MS' THEN 'Center-West'
            WHEN 'ES' THEN 'Southeast' WHEN 'MG' THEN 'Southeast'
            WHEN 'RJ' THEN 'Southeast' WHEN 'SP' THEN 'Southeast'
            WHEN 'PR' THEN 'South' WHEN 'RS' THEN 'South' WHEN 'SC' THEN 'South'
            ELSE 'Unknown'
        END,
        c.customer_zip_code_prefix,
        0
    FROM stg.Customers c;

    SET IDENTITY_INSERT dw.DimProduct ON;
    INSERT INTO dw.DimProduct (ProductKey, ProductID, CategoryNamePortuguese, CategoryNameEnglish, WeightClass, IsUnknown)
    VALUES (-1, 'UNKNOWN', 'unknown', 'Unknown', 'Unknown', 1);
    SET IDENTITY_INSERT dw.DimProduct OFF;

    INSERT INTO dw.DimProduct (
        ProductID, CategoryNamePortuguese, CategoryNameEnglish,
        WeightG, LengthCm, HeightCm, WidthCm, PhotosQty, WeightClass, IsUnknown
    )
    SELECT
        p.product_id,
        ISNULL(p.product_category_name, 'unknown'),
        ISNULL(t.product_category_name_english,
               CASE p.product_category_name
                    WHEN 'pc_gamer' THEN 'pc_gamer'
                    WHEN 'portateis_cozinha_e_preparadores_de_alimentos' THEN 'portable_kitchen_food_preparers'
                    ELSE 'Other'
               END),
        p.product_weight_g,
        p.product_length_cm,
        p.product_height_cm,
        p.product_width_cm,
        p.product_photos_qty,
        CASE
            WHEN p.product_weight_g IS NULL THEN 'Unknown'
            WHEN p.product_weight_g < 500 THEN 'Light'
            WHEN p.product_weight_g < 2000 THEN 'Medium'
            ELSE 'Heavy'
        END,
        0
    FROM stg.Products p
    LEFT JOIN stg.CategoryTranslation t
        ON p.product_category_name = t.product_category_name;

    SET IDENTITY_INSERT dw.DimSeller ON;
    INSERT INTO dw.DimSeller (SellerKey, SellerID, SellerCity, SellerState, SellerRegion, SellerZipPrefix, IsUnknown)
    VALUES (-1, 'UNKNOWN', 'Unknown', 'XX', 'Unknown', 0, 1);
    SET IDENTITY_INSERT dw.DimSeller OFF;

    INSERT INTO dw.DimSeller (SellerID, SellerCity, SellerState, SellerRegion, SellerZipPrefix, IsUnknown)
    SELECT
        s.seller_id,
        LOWER(LTRIM(RTRIM(s.seller_city))),
        UPPER(LTRIM(RTRIM(s.seller_state))),
        CASE UPPER(LTRIM(RTRIM(s.seller_state)))
            WHEN 'AC' THEN 'North' WHEN 'AP' THEN 'North' WHEN 'AM' THEN 'North'
            WHEN 'PA' THEN 'North' WHEN 'RO' THEN 'North' WHEN 'RR' THEN 'North' WHEN 'TO' THEN 'North'
            WHEN 'AL' THEN 'Northeast' WHEN 'BA' THEN 'Northeast' WHEN 'CE' THEN 'Northeast'
            WHEN 'MA' THEN 'Northeast' WHEN 'PB' THEN 'Northeast' WHEN 'PE' THEN 'Northeast'
            WHEN 'PI' THEN 'Northeast' WHEN 'RN' THEN 'Northeast' WHEN 'SE' THEN 'Northeast'
            WHEN 'DF' THEN 'Center-West' WHEN 'GO' THEN 'Center-West'
            WHEN 'MT' THEN 'Center-West' WHEN 'MS' THEN 'Center-West'
            WHEN 'ES' THEN 'Southeast' WHEN 'MG' THEN 'Southeast'
            WHEN 'RJ' THEN 'Southeast' WHEN 'SP' THEN 'Southeast'
            WHEN 'PR' THEN 'South' WHEN 'RS' THEN 'South' WHEN 'SC' THEN 'South'
            ELSE 'Unknown'
        END,
        s.seller_zip_code_prefix,
        0
    FROM stg.Sellers s;
END;
GO

CREATE OR ALTER PROCEDURE dw.usp_LoadFacts
AS
BEGIN
    SET NOCOUNT ON;

    ;WITH PrimaryPay AS (
        SELECT order_id, payment_type,
               ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY payment_sequential) AS rn
        FROM stg.Payments
    ),
    AvgReview AS (
        SELECT order_id, AVG(CAST(review_score AS DECIMAL(4,2))) AS review_score
        FROM stg.Reviews
        GROUP BY order_id
    )
    INSERT INTO dw.FactSales (
        PurchaseDateKey, DeliveredDateKey, EstimatedDeliveryDateKey,
        CustomerKey, ProductKey, SellerKey, CustomerGeoKey, PaymentTypeKey, OrderStatusKey,
        OrderID, OrderItemID, Price, FreightValue, LineTotal, Quantity,
        DeliveryDays, DelayDays, OnTimeFlag, ReviewScore
    )
    SELECT
        ISNULL(dd_p.DateKey, 19000101),
        dd_d.DateKey,
        dd_e.DateKey,
        ISNULL(c.CustomerKey, -1),
        ISNULL(p.ProductKey, -1),
        ISNULL(s.SellerKey, -1),
        g.GeoKey,
        ISNULL(pt.PaymentTypeKey, (SELECT TOP 1 PaymentTypeKey FROM dw.DimPaymentType WHERE PaymentType = 'unknown')),
        os.OrderStatusKey,
        i.order_id,
        i.order_item_id,
        i.price,
        i.freight_value,
        i.price + i.freight_value,
        1,
        CASE WHEN o.order_delivered_customer_date IS NULL THEN NULL
             ELSE DATEDIFF(DAY, o.order_purchase_timestamp, o.order_delivered_customer_date) END,
        CASE WHEN o.order_delivered_customer_date IS NULL OR o.order_estimated_delivery_date IS NULL THEN NULL
             ELSE DATEDIFF(DAY, o.order_estimated_delivery_date, o.order_delivered_customer_date) END,
        CASE
            WHEN o.order_delivered_customer_date IS NULL OR o.order_estimated_delivery_date IS NULL THEN NULL
            WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date THEN 'Y'
            ELSE 'N'
        END,
        r.review_score
    FROM stg.OrderItems i
    INNER JOIN stg.Orders o ON o.order_id = i.order_id
    LEFT JOIN dw.DimCustomer c ON c.CustomerID = o.customer_id
    LEFT JOIN dw.DimProduct p ON p.ProductID = i.product_id
    LEFT JOIN dw.DimSeller s ON s.SellerID = i.seller_id
    LEFT JOIN dw.DimOrderStatus os ON os.OrderStatus = o.order_status
    LEFT JOIN dw.DimDate dd_p ON dd_p.FullDate = CAST(o.order_purchase_timestamp AS DATE)
    LEFT JOIN dw.DimDate dd_d ON dd_d.FullDate = CAST(o.order_delivered_customer_date AS DATE)
    LEFT JOIN dw.DimDate dd_e ON dd_e.FullDate = CAST(o.order_estimated_delivery_date AS DATE)
    LEFT JOIN dw.DimGeolocation g ON g.ZipPrefix = c.CustomerZipPrefix
    LEFT JOIN PrimaryPay pay ON pay.order_id = i.order_id AND pay.rn = 1
    LEFT JOIN dw.DimPaymentType pt ON pt.PaymentType = pay.payment_type
    LEFT JOIN AvgReview r ON r.order_id = i.order_id;

    INSERT INTO dw.FactPayment (
        PurchaseDateKey, CustomerKey, PaymentTypeKey, OrderID,
        PaymentSequential, PaymentInstallments, PaymentValue
    )
    SELECT
        ISNULL(dd.DateKey, 19000101),
        ISNULL(c.CustomerKey, -1),
        ISNULL(pt.PaymentTypeKey, (SELECT TOP 1 PaymentTypeKey FROM dw.DimPaymentType WHERE PaymentType = 'unknown')),
        pay.order_id,
        pay.payment_sequential,
        pay.payment_installments,
        pay.payment_value
    FROM stg.Payments pay
    INNER JOIN stg.Orders o ON o.order_id = pay.order_id
    LEFT JOIN dw.DimCustomer c ON c.CustomerID = o.customer_id
    LEFT JOIN dw.DimPaymentType pt ON pt.PaymentType = pay.payment_type
    LEFT JOIN dw.DimDate dd ON dd.FullDate = CAST(o.order_purchase_timestamp AS DATE);
END;
GO
