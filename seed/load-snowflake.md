# Load `seed/opportunities.csv` into Snowflake

**Recommended:** Snowflake free 30-day trial with $400 credit. Sign up at https://signup.snowflake.com.

Once your trial is provisioned, run the following from the Snowflake web UI worksheet.

## Step 1 - Create the warehouse, database, schema

```sql
USE ROLE ACCOUNTADMIN;
CREATE WAREHOUSE IF NOT EXISTS BMK_WH WITH WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;
CREATE DATABASE IF NOT EXISTS BENCHMARK_DB;
CREATE SCHEMA   IF NOT EXISTS BENCHMARK_DB.SALESFORCE;
USE WAREHOUSE BMK_WH;
USE DATABASE  BENCHMARK_DB;
USE SCHEMA    SALESFORCE;
```

## Step 2 - Create the table

```sql
CREATE OR REPLACE TABLE OPPORTUNITY (
    ACCOUNT_ID        STRING,
    OPPORTUNITY_ID    STRING,
    AMOUNT            NUMBER(18,2),
    STAGE_NAME        STRING,
    EXPECTED_REVENUE  NUMBER(18,2),
    IS_WON            BOOLEAN,
    FISCAL_YEAR       NUMBER,
    CLOSE_DATE        DATE
);
```

## Step 3 - Stage the CSV and copy in

```sql
-- Web UI: click "Files" -> upload seed/opportunities.csv into your user stage
-- Then:
CREATE OR REPLACE FILE FORMAT BMK_CSV
  TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1;

COPY INTO OPPORTUNITY (ACCOUNT_ID, OPPORTUNITY_ID, AMOUNT, STAGE_NAME,
                       EXPECTED_REVENUE, IS_WON, FISCAL_YEAR, CLOSE_DATE)
FROM @~/opportunities.csv
FILE_FORMAT = BMK_CSV
ON_ERROR = 'CONTINUE';
```

Alternatively, use SnowSQL CLI:

```powershell
snowsql -a <account> -u <user> -d BENCHMARK_DB -s SALESFORCE -w BMK_WH `
  -q "PUT file://seed/opportunities.csv @~ AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
snowsql -a <account> -u <user> -d BENCHMARK_DB -s SALESFORCE -w BMK_WH `
  -q "COPY INTO OPPORTUNITY FROM @~/opportunities.csv FILE_FORMAT = BMK_CSV"
```

## Connect AI configuration

1. In Connect AI, create a new **Snowflake** connection. Use your account URL, the BMK_WH warehouse, the BENCHMARK_DB database, the SALESFORCE schema.
2. Note the **connection name** - this is `catalog` in ``.env``.
3. Schema = `SALESFORCE`, table = `OPPORTUNITY`.

## Verify

```sql
SELECT COUNT(*) FROM [<your-sf-conn>].[SALESFORCE].[OPPORTUNITY]
WHERE ACCOUNT_ID LIKE 'BMK_%'
```

Should return `50`.

## Cost note

XSMALL warehouse auto-suspends after 60 seconds idle. Loading 50 rows uses
~0.001 credits. Running the benchmark uses ~0.01 credits total. You'll
spend well under $1 from the trial credit allocation.
