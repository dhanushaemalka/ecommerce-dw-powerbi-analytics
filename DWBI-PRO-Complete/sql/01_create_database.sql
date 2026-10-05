/*
    OlistDW - SQL Server database, schemas, and audit objects
    SLIIT DWBI | Run in SQL Server Management Studio (2019+)
*/
IF DB_ID(N'OlistDW') IS NOT NULL
BEGIN
    ALTER DATABASE OlistDW SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE OlistDW;
END;
GO

CREATE DATABASE OlistDW;
GO

USE OlistDW;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'stg')  EXEC(N'CREATE SCHEMA stg');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'dw')   EXEC(N'CREATE SCHEMA dw');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'audit') EXEC(N'CREATE SCHEMA audit');
GO

CREATE TABLE audit.ETL_Log (
    LogID           INT IDENTITY(1,1) PRIMARY KEY,
    PackageName     VARCHAR(100) NOT NULL,
    TaskName        VARCHAR(100) NOT NULL,
    Status          VARCHAR(20)  NOT NULL,
    RowsAffected    INT          NULL,
    MessageText     VARCHAR(1000) NULL,
    StartedAt       DATETIME     NOT NULL DEFAULT GETDATE(),
    FinishedAt      DATETIME     NULL
);
GO

CREATE TABLE audit.RejectedRows (
    RejectID        INT IDENTITY(1,1) PRIMARY KEY,
    SourceTable     VARCHAR(100) NOT NULL,
    BusinessKey     VARCHAR(100) NULL,
    ReasonCode      VARCHAR(50)  NOT NULL,
    ReasonText      VARCHAR(500) NULL,
    RejectedAt      DATETIME     NOT NULL DEFAULT GETDATE()
);
GO
