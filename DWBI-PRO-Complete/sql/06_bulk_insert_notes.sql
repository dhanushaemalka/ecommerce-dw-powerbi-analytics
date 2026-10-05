/*
    Optional: land prepared CSVs into staging without SSIS.
    Adjust the folder path. Enable xp / use BULK INSERT from a path SQL Server can read.
    Alternative: Import Flat File wizard in SSMS for each stg table.
*/
USE OlistDW;
GO

-- Example (enable if the SQL Server service account can read the folder):
-- BULK INSERT stg.Orders
-- FROM 'D:\DWBI-PRO\DWBI-Complete\01_PreparedSources\csv\olist_orders_dataset.csv'
-- WITH (FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', CODEPAGE = '65001', TABLOCK, FORMAT = 'CSV');
GO
