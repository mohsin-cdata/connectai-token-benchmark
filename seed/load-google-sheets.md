# Easy mode: Load seed data via Google Sheets

The fastest way to run the benchmark against three real Connect AI sources.
Setup time: roughly **10-15 minutes** -- mostly a one-click sheet copy plus
three CData connection creates. No SaaS sandbox setup, no Data Loader, no
COPY INTO commands.

This path is for recipients who want to **verify the benchmark methodology
quickly**. The reproduced numbers will land near the published headline but
will differ slightly (Google Sheets has a leaner column shape than
Salesforce's 73-column Account object, so the Raw baseline will be a touch
lower than 183,541 tokens). The 95%+ reduction trend reproduces reliably.

For an **authentic reproduction** of the exact published numbers, use the
3-SaaS path (`seed/load-salesforce.md`, `seed/load-servicenow.md`,
`seed/load-snowflake.md`) instead.

---

## Step 1 - Copy the public Google Sheets

The benchmark uses three separate Google Sheets, one per source role
(ITSM / CRM / Warehouse). Each has 50 rows prefixed `BMK_` (accounts) or
`BMK-` (tickets), matching the seed CSVs in this folder.

1. Open the public benchmark workbook:
   <!-- Replace this URL once the template sheet is published -->
   `https://docs.google.com/spreadsheets/d/<TEMPLATE_SHEET_ID>/`

2. The workbook contains three tabs: `BMK_ITSM_incidents`, `BMK_CRM_accounts`,
   `BMK_WH_opportunities`.

3. Click **File &rsaquo; Make a copy** for each tab into its own new sheet in
   your Google Drive. Name the resulting three sheets:
   - `BMK ITSM incidents`
   - `BMK CRM accounts`
   - `BMK WH opportunities`

   (Three separate sheets, not one with three tabs. CData Connect AI's Google
   Sheets connector treats each spreadsheet file as a separate source, which
   is what preserves the cross-source discovery story.)

4. Note each sheet's file ID -- the long string in the URL between
   `/spreadsheets/d/` and `/edit`. You will need it during the CData
   connection step.

---

## Step 2 - Create three CData connections

In Connect AI (<a href='https://cloud.cdata.com/'>cloud.cdata.com</a>):

1. Click **Sources** in the left navigation, then **+ Add Connection**.
2. Search for **Google Sheets**, select it.
3. Complete the OAuth flow against your Google account.
4. In the connection settings, set **Spreadsheet** to the file ID of your
   `BMK ITSM incidents` sheet.
5. Name the connection `BMK_ITSM`. Click **Save & Test**.

Repeat steps 1-5 for the CRM and warehouse sheets, naming them `BMK_CRM` and
`BMK_WH` respectively.

You now have three Connect AI connections, each pointing at a separate
Google Sheet -- the same three-source shape the benchmark expects.

---

## Step 3 - Update your .env

Open `.env` and set:

```
CDATA_ITSM_CATALOG=BMK_ITSM
CDATA_ITSM_SCHEMA=GoogleSheets
CDATA_ITSM_TABLE=BMK_ITSM_incidents

CDATA_CRM_CATALOG=BMK_CRM
CDATA_CRM_SCHEMA=GoogleSheets
CDATA_CRM_TABLE=BMK_CRM_accounts

CDATA_WH_CATALOG=BMK_WH
CDATA_WH_SCHEMA=GoogleSheets
CDATA_WH_TABLE=BMK_WH_opportunities
```

The Schema for every Google Sheets-backed CData connection is literally
`GoogleSheets` (capitalised exactly that way). The Table name matches the
worksheet name in the spreadsheet (the tab name).

---

## Step 4 - Create the Derived View

The Derived View pre-joins the three sheets. In Connect AI:

1. Click **Data Explorer &rsaquo; SQL Editor**.
2. Paste this SQL (it uses the three connections you just created):

   ```sql
   SELECT
       i.number              AS ticket_number,
       i.short_description   AS ticket_summary,
       i.priority            AS ticket_priority,
       a.Name                AS AccountName,
       a.Industry            AS Industry,
       a.AnnualRevenue       AS AnnualRevenue,
       o.AMOUNT              AS OpportunityAmount,
       o.STAGE_NAME          AS StageName,
       o.IS_WON              AS IsWon
   FROM [BMK_ITSM].[GoogleSheets].[BMK_ITSM_incidents] i
   LEFT JOIN [BMK_CRM].[GoogleSheets].[BMK_CRM_accounts] a
       ON i.company = a.Id
   LEFT JOIN [BMK_WH].[GoogleSheets].[BMK_WH_opportunities] o
       ON a.Id = o.ACCOUNT_ID
   WHERE i.number LIKE 'BMK-%'
   ```

3. Click **Execute**. Verify rows return.
4. Click **Save &rsaquo; Save as Derived View**. Name it
   `BMK_Incident_Account_Revenue`. Click **Confirm**.

---

## Step 5 - Verify

Back in Data Explorer:

```sql
SELECT COUNT(*) FROM [CData].[DerivedViews].[BMK_Incident_Account_Revenue]
```

Should return `50`.

You are now ready to run the benchmark:

```powershell
python run_benchmark.py --full --runs 3
```

---

## Cleanup

When you are done, delete the three Google Sheets from your Drive and the
three CData connections from your Connect AI Sources page. No source-side
cleanup script needed -- you never touched a production SaaS account.

---

## Why this works

The benchmark measures Claude's discovery cost across **three separate
catalogs**. By giving Connect AI three Google Sheets connections (rather
than one connection with three tabs), Claude still has to walk the same
multi-catalog discovery chain to answer the user's question. The Raw
baseline still calls `getCatalogs`, `getSchemas`, `getTables`, and
`getColumns` across three sources, accumulating the same shape of input
tokens -- just slightly fewer because Google Sheets exposes a lighter
schema than enterprise Salesforce / ServiceNow / Snowflake.

The Connect AI features being measured (Custom Tools, Derived Views,
Workspaces) behave identically regardless of the underlying source type.
