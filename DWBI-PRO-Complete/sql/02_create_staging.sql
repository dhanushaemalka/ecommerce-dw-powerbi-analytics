/*
    Staging layer - land source data with almost no transformation.
    SSIS Data Flow destinations map 1:1 onto these tables.
*/
USE OlistDW;
GO

IF OBJECT_ID(N'stg.Customers', N'U') IS NOT NULL DROP TABLE stg.Customers;
IF OBJECT_ID(N'stg.Orders', N'U') IS NOT NULL DROP TABLE stg.Orders;
IF OBJECT_ID(N'stg.OrderItems', N'U') IS NOT NULL DROP TABLE stg.OrderItems;
IF OBJECT_ID(N'stg.Payments', N'U') IS NOT NULL DROP TABLE stg.Payments;
IF OBJECT_ID(N'stg.Reviews', N'U') IS NOT NULL DROP TABLE stg.Reviews;
IF OBJECT_ID(N'stg.Products', N'U') IS NOT NULL DROP TABLE stg.Products;
IF OBJECT_ID(N'stg.Sellers', N'U') IS NOT NULL DROP TABLE stg.Sellers;
IF OBJECT_ID(N'stg.Geolocation', N'U') IS NOT NULL DROP TABLE stg.Geolocation;
IF OBJECT_ID(N'stg.CategoryTranslation', N'U') IS NOT NULL DROP TABLE stg.CategoryTranslation;
IF OBJECT_ID(N'stg.Holidays', N'U') IS NOT NULL DROP TABLE stg.Holidays;
GO

CREATE TABLE stg.Customers (
    customer_id                 VARCHAR(50),
    customer_unique_id          VARCHAR(50),
    customer_zip_code_prefix    INT,
    customer_city               VARCHAR(100),
    customer_state              VARCHAR(10)
);

CREATE TABLE stg.Orders (
    order_id                        VARCHAR(50),
    customer_id                     VARCHAR(50),
    order_status                    VARCHAR(30),
    order_purchase_timestamp        DATETIME,
    order_approved_at               DATETIME NULL,
    order_delivered_carrier_date    DATETIME NULL,
    order_delivered_customer_date   DATETIME NULL,
    order_estimated_delivery_date   DATETIME NULL
);

CREATE TABLE stg.OrderItems (
    order_id            VARCHAR(50),
    order_item_id       INT,
    product_id          VARCHAR(50),
    seller_id           VARCHAR(50),
    shipping_limit_date DATETIME,
    price               DECIMAL(12,2),
    freight_value       DECIMAL(12,2)
);

CREATE TABLE stg.Payments (
    order_id                VARCHAR(50),
    payment_sequential      INT,
    payment_type            VARCHAR(30),
    payment_installments    INT,
    payment_value           DECIMAL(12,2)
);

CREATE TABLE stg.Reviews (
    review_id               VARCHAR(50),
    order_id                VARCHAR(50),
    review_score            INT,
    review_comment_title    NVARCHAR(200) NULL,
    review_comment_message  NVARCHAR(MAX) NULL,
    review_creation_date    DATETIME,
    review_answer_timestamp DATETIME
);

CREATE TABLE stg.Products (
    product_id                      VARCHAR(50),
    product_category_name           VARCHAR(100) NULL,
    product_name_lenght             INT NULL,
    product_description_lenght      INT NULL,
    product_photos_qty              INT NULL,
    product_weight_g                FLOAT NULL,
    product_length_cm               FLOAT NULL,
    product_height_cm               FLOAT NULL,
    product_width_cm                FLOAT NULL
);

CREATE TABLE stg.Sellers (
    seller_id               VARCHAR(50),
    seller_zip_code_prefix  INT,
    seller_city             VARCHAR(100),
    seller_state            VARCHAR(10)
);

CREATE TABLE stg.Geolocation (
    geolocation_zip_code_prefix INT,
    geolocation_lat             FLOAT,
    geolocation_lng             FLOAT,
    geolocation_city            VARCHAR(100),
    geolocation_state           VARCHAR(10)
);

/* Excel source */
CREATE TABLE stg.CategoryTranslation (
    product_category_name           VARCHAR(100),
    product_category_name_english   VARCHAR(100)
);

/* JSON / REST API source */
CREATE TABLE stg.Holidays (
    holiday_date    DATE,
    local_name      NVARCHAR(150),
    english_name    NVARCHAR(150),
    country_code    VARCHAR(5)
);
GO
