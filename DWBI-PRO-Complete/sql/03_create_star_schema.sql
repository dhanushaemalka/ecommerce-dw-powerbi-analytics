/*
    Star schema (dw schema)
    Grain of FactSales: one row per order line (order_id + order_item_id)
*/
USE OlistDW;
GO

IF OBJECT_ID(N'dw.FactSales', N'U') IS NOT NULL DROP TABLE dw.FactSales;
IF OBJECT_ID(N'dw.FactPayment', N'U') IS NOT NULL DROP TABLE dw.FactPayment;
IF OBJECT_ID(N'dw.DimDate', N'U') IS NOT NULL DROP TABLE dw.DimDate;
IF OBJECT_ID(N'dw.DimCustomer', N'U') IS NOT NULL DROP TABLE dw.DimCustomer;
IF OBJECT_ID(N'dw.DimProduct', N'U') IS NOT NULL DROP TABLE dw.DimProduct;
IF OBJECT_ID(N'dw.DimSeller', N'U') IS NOT NULL DROP TABLE dw.DimSeller;
IF OBJECT_ID(N'dw.DimGeolocation', N'U') IS NOT NULL DROP TABLE dw.DimGeolocation;
IF OBJECT_ID(N'dw.DimPaymentType', N'U') IS NOT NULL DROP TABLE dw.DimPaymentType;
IF OBJECT_ID(N'dw.DimOrderStatus', N'U') IS NOT NULL DROP TABLE dw.DimOrderStatus;
GO

CREATE TABLE dw.DimDate (
    DateKey         INT          NOT NULL PRIMARY KEY,
    FullDate        DATE         NOT NULL,
    DayNumber       TINYINT      NOT NULL,
    DayName         VARCHAR(15)  NOT NULL,
    WeekdayFlag     CHAR(1)      NOT NULL,
    WeekendFlag     CHAR(1)      NOT NULL,
    WeekOfYear      TINYINT      NOT NULL,
    MonthNumber     TINYINT      NOT NULL,
    MonthName       VARCHAR(15)  NOT NULL,
    QuarterNumber   TINYINT      NOT NULL,
    QuarterName     CHAR(2)      NOT NULL,
    YearNumber      SMALLINT     NOT NULL,
    YearMonth       CHAR(7)      NOT NULL,
    IsHoliday       BIT          NOT NULL DEFAULT 0,
    HolidayName     NVARCHAR(150) NULL
);

CREATE TABLE dw.DimCustomer (
    CustomerKey             INT IDENTITY(1,1) PRIMARY KEY,
    CustomerID              VARCHAR(50)  NOT NULL,
    CustomerUniqueID        VARCHAR(50)  NOT NULL,
    CustomerCity            VARCHAR(100) NULL,
    CustomerState           VARCHAR(10)  NULL,
    CustomerRegion          VARCHAR(20)  NULL,
    CustomerZipPrefix       INT          NULL,
    IsUnknown               BIT          NOT NULL DEFAULT 0
);

CREATE TABLE dw.DimProduct (
    ProductKey                  INT IDENTITY(1,1) PRIMARY KEY,
    ProductID                   VARCHAR(50)  NOT NULL,
    CategoryNamePortuguese      VARCHAR(100) NULL,
    CategoryNameEnglish         VARCHAR(100) NULL,
    WeightG                     FLOAT        NULL,
    LengthCm                    FLOAT        NULL,
    HeightCm                    FLOAT        NULL,
    WidthCm                     FLOAT        NULL,
    PhotosQty                   INT          NULL,
    WeightClass                 VARCHAR(20)  NULL,
    IsUnknown                   BIT          NOT NULL DEFAULT 0
);

CREATE TABLE dw.DimSeller (
    SellerKey           INT IDENTITY(1,1) PRIMARY KEY,
    SellerID            VARCHAR(50)  NOT NULL,
    SellerCity          VARCHAR(100) NULL,
    SellerState         VARCHAR(10)  NULL,
    SellerRegion        VARCHAR(20)  NULL,
    SellerZipPrefix     INT          NULL,
    IsUnknown           BIT          NOT NULL DEFAULT 0
);

CREATE TABLE dw.DimGeolocation (
    GeoKey          INT IDENTITY(1,1) PRIMARY KEY,
    ZipPrefix       INT          NOT NULL,
    City            VARCHAR(100) NULL,
    State           VARCHAR(10)  NULL,
    Region          VARCHAR(20)  NULL,
    Latitude        FLOAT        NULL,
    Longitude       FLOAT        NULL
);

CREATE TABLE dw.DimPaymentType (
    PaymentTypeKey      INT IDENTITY(1,1) PRIMARY KEY,
    PaymentType         VARCHAR(30) NOT NULL,
    PaymentTypeGroup    VARCHAR(30) NOT NULL
);

CREATE TABLE dw.DimOrderStatus (
    OrderStatusKey      INT IDENTITY(1,1) PRIMARY KEY,
    OrderStatus         VARCHAR(30) NOT NULL,
    IsDeliveredFlag     CHAR(1)     NOT NULL,
    IsCancelledFlag     CHAR(1)     NOT NULL
);

CREATE TABLE dw.FactSales (
    SalesKey                    BIGINT IDENTITY(1,1) PRIMARY KEY,
    PurchaseDateKey             INT          NOT NULL,
    DeliveredDateKey            INT          NULL,
    EstimatedDeliveryDateKey    INT          NULL,
    CustomerKey                 INT          NOT NULL,
    ProductKey                  INT          NOT NULL,
    SellerKey                   INT          NOT NULL,
    CustomerGeoKey              INT          NULL,
    PaymentTypeKey              INT          NULL,
    OrderStatusKey              INT          NOT NULL,
    OrderID                     VARCHAR(50)  NOT NULL,  -- degenerate
    OrderItemID                 INT          NOT NULL,  -- degenerate
    Price                       DECIMAL(12,2) NOT NULL,
    FreightValue                DECIMAL(12,2) NOT NULL,
    LineTotal                   DECIMAL(12,2) NOT NULL,
    Quantity                    INT           NOT NULL DEFAULT 1,
    DeliveryDays                INT           NULL,
    DelayDays                   INT           NULL,
    OnTimeFlag                  CHAR(1)       NULL,
    ReviewScore                 DECIMAL(4,2)  NULL,
    CONSTRAINT FK_FactSales_PurchaseDate FOREIGN KEY (PurchaseDateKey) REFERENCES dw.DimDate(DateKey),
    CONSTRAINT FK_FactSales_Customer     FOREIGN KEY (CustomerKey)     REFERENCES dw.DimCustomer(CustomerKey),
    CONSTRAINT FK_FactSales_Product      FOREIGN KEY (ProductKey)      REFERENCES dw.DimProduct(ProductKey),
    CONSTRAINT FK_FactSales_Seller       FOREIGN KEY (SellerKey)       REFERENCES dw.DimSeller(SellerKey),
    CONSTRAINT FK_FactSales_Status       FOREIGN KEY (OrderStatusKey)  REFERENCES dw.DimOrderStatus(OrderStatusKey)
);

CREATE TABLE dw.FactPayment (
    PaymentKey              BIGINT IDENTITY(1,1) PRIMARY KEY,
    PurchaseDateKey         INT           NOT NULL,
    CustomerKey             INT           NOT NULL,
    PaymentTypeKey          INT           NOT NULL,
    OrderID                 VARCHAR(50)   NOT NULL,
    PaymentSequential       INT           NOT NULL,
    PaymentInstallments     INT           NOT NULL,
    PaymentValue            DECIMAL(12,2) NOT NULL,
    CONSTRAINT FK_FactPayment_Date    FOREIGN KEY (PurchaseDateKey) REFERENCES dw.DimDate(DateKey),
    CONSTRAINT FK_FactPayment_Cust    FOREIGN KEY (CustomerKey)     REFERENCES dw.DimCustomer(CustomerKey),
    CONSTRAINT FK_FactPayment_Type    FOREIGN KEY (PaymentTypeKey)  REFERENCES dw.DimPaymentType(PaymentTypeKey)
);
GO

CREATE UNIQUE INDEX IX_DimCustomer_BK ON dw.DimCustomer(CustomerID);
CREATE UNIQUE INDEX IX_DimProduct_BK  ON dw.DimProduct(ProductID);
CREATE UNIQUE INDEX IX_DimSeller_BK   ON dw.DimSeller(SellerID);
CREATE UNIQUE INDEX IX_DimGeo_Zip     ON dw.DimGeolocation(ZipPrefix);
CREATE UNIQUE INDEX IX_DimPayType     ON dw.DimPaymentType(PaymentType);
CREATE UNIQUE INDEX IX_DimStatus      ON dw.DimOrderStatus(OrderStatus);
CREATE INDEX IX_FactSales_Date        ON dw.FactSales(PurchaseDateKey);
CREATE INDEX IX_FactSales_Product     ON dw.FactSales(ProductKey);
CREATE INDEX IX_FactSales_Customer    ON dw.FactSales(CustomerKey);
CREATE INDEX IX_FactSales_Order       ON dw.FactSales(OrderID);
GO
