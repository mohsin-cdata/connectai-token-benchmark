# Easy mode: Load seed data via Google Sheets

The fastest way to run the benchmark against three real Connect AI sources.
Setup time: roughly **10-15 minutes** -- three sheet copies plus three CData
connection creates. No SaaS sandbox setup, no Data Loader, no `COPY INTO`.

This path is for recipients who want to **verify the benchmark methodology
quickly**. Reproduced numbers will land near the published headline but
will differ slightly (Google Sheets has a leaner column shape than
Salesforce's 73-column Account object, so the Raw baseline will be a touch
lower than 183,541 tokens). The 95%+ reduction trend reproduces reliably.

For an **authentic reproduction** of the exact published numbers, use the
3-SaaS path (`seed/load-salesforce.md`, `seed/load-servicenow.md`,
`seed/load-snowflake.md`) instead.

---

## Step 1 - Copy the three template Google Sheets

The benchmark uses three separate Google Sheets, one per source role.
Each contains 50 rows prefixed `BMK_` (accounts) or `BMK-` (tickets),
matching the seed CSVs in this folder.

| Role | Template URL | Columns |
| :-- | :-- | :-- |
| **CRM** (accounts) | https://docs.google.com/spreadsheets/d/1KCZEr5bH8jNCwNudT-1bvyGkLO1FlJrZXNKFMaHN7Zs/edit | id, name, industry, annual_revenue, sla, customer_priority, active, segment |
| **ITSM** (incidents) | https://docs.google.com/spreadsheets/d/12Ah5Wj9E5ZKi6V5h5i3QubENKeObxbHNsewEeSpeIc0/edit | number, short_description, priority, state, urgency, severity, category, opened_at, company |
| **Warehouse** (opportunities) | https://docs.google.com/spreadsheets/d/1Y0ndX-_U46yEWeU6CE9L95YmsfH13RfawjeHasuMH9w/edit | account_id, opportunity_id, amount, stage_name, expected_revenue, is_won, fiscal_year, close_date |

For each template:

1. Open the URL.
2. Click **File &rsaquo; Make a copy** -- Google will copy it into your own Drive.
3. (Optional) Rename the copy so you can find it later -- e.g.
   `BMK Benchmark - CRM Accounts`.
4. Note the file ID from the URL (the long string between `/d/` and `/edit`).
   You will paste it into Connect AI in the next step.

The default worksheet (tab) name inside each copy will match the role,
so you do not need to rename anything inside the workbook.

---

## Step 2 - Create three Connect AI connections

In Connect AI (<a href='https://cloud.cdata.com/'>cloud.cdata.com</a>):

1. Click **Sources** in the left navigation, then **+ Add Connection**.
2. Search for **Google Sheets**, select it.
3. On the **Basic Settings** tab, fill in:
   - **Connection Name** = `BMK_CRM`
   - **Auth Scheme** = `OAuth`
   - **Spreadsheet Id** = the file ID of your **CRM** copy (the long string
     between `/d/` and `/edit` in the URL)
   - **Spreadsheet** = `accounts` (the worksheet/tab name -- optional but
     recommended; narrows discovery to just this one tab)
   - **Folder Name** = leave empty
4. Click **Sign in** to complete the Google OAuth flow against the account
   that owns the copied sheet.
5. Click **Save & Test**. The Status should change to **Authenticated**.

Repeat steps 1-5 twice more for the other two roles:

| Connection Name | Spreadsheet Id | Spreadsheet (tab) |
| :-- | :-- | :-- |
| `BMK_ITSM` | file ID of your **incidents** copy | `incidents` |
| `BMK_WH`   | file ID of your **opportunities** copy | `opportunities` |

You now have three Connect AI connections, each pointing at a separate
Google Sheets workbook -- the three-catalog shape the benchmark expects.

---

## Step 3 - Identify the worksheet (table) name

Each Google Sheets workbook has one worksheet inside (the imported CSV).
In Connect AI, that worksheet becomes a **table** within the connection.

For each connection, open the **Tables** tab inside Connect AI and confirm
the table name. It is usually identical to the worksheet (tab) name in
your Google Sheets copy -- something like `accounts`, `incidents`, or
`opportunities`.

Whatever they are, those exact strings go into your `.env` in Step 4.

---

## Step 4 - Update your .env

Open `.env` and set:

```
CDATA_ITSM_CATALOG=BMK_ITSM
CDATA_ITSM_SCHEMA=GoogleSheets
CDATA_ITSM_TABLE=incidents

CDATA_CRM_CATALOG=BMK_CRM
CDATA_CRM_SCHEMA=GoogleSheets
CDATA_CRM_TABLE=accounts

CDATA_WH_CATALOG=BMK_WH
CDATA_WH_SCHEMA=GoogleSheets
CDATA_WH_TABLE=opportunities
```

Replace the **TABLE** values if your worksheet tabs ended up with different
names than the templates'.

The **SCHEMA** value is literally `GoogleSheets` for every Google Sheets
connection (capitalised exactly that way -- that is the schema name
Connect AI uses internally).

---

## Step 5 - Create the Derived View

The Derived View pre-joins the three workbooks into one cross-source view.
In Connect AI:

1. Click **Explorer &rsaquo; SQL Editor**.
2. Paste this SQL (it references the three connections you just created):

   ```sql
   SELECT
       i.number              AS ticket_number,
       i.short_description   AS ticket_summary,
       i.priority            AS ticket_priority,
       a.name                AS AccountName,
       a.industry            AS Industry,
       a.annual_revenue      AS AnnualRevenue,
       o.amount              AS OpportunityAmount,
       o.stage_name          AS StageName,
       o.is_won              AS IsWon
   FROM [BMK_ITSM].[GoogleSheets].[incidents] i
   LEFT JOIN [BMK_CRM].[GoogleSheets].[accounts] a
       ON i.company = a.id
   LEFT JOIN [BMK_WH].[GoogleSheets].[opportunities] o
       ON a.id = o.account_id
   WHERE i.number LIKE 'BMK-%'
   ```

3. Click **Execute**. Verify rows return.
4. Click **Save &rsaquo; Save as Derived View**. Name it
   `BMK_Incident_Account_Revenue`. Click **Confirm**.

---

## Step 6 - Verify

Back in Explorer:

```sql
SELECT COUNT(*) FROM [CData].[DerivedViews].[BMK_Incident_Account_Revenue]
```

Should return roughly `50` (a few rows may drop if any opportunities are
missing matching accounts -- the LEFT JOIN handles that gracefully).

You are now ready to run the benchmark:

```powershell
python run_benchmark.py --full --runs 3
```

---

## Cleanup

When you are done:

1. Delete the three Google Sheets copies from your Drive.
2. Delete the three CData connections from Sources.
3. Delete the Derived View from `CData &rsaquo; DerivedViews`.

No source-side cleanup script needed -- the benchmark never touched a
production SaaS account.

---

## Why this works

The benchmark measures Claude's discovery cost across **three separate
catalogs**. By using three Google Sheets connections (rather than one
connection with three tabs), Claude still has to walk the same
multi-catalog discovery chain to answer the user's question. The Raw
baseline calls `getCatalogs`, `getSchemas`, `getTables`, and `getColumns`
across three sources, accumulating the same shape of input tokens -- just
slightly fewer because Google Sheets exposes a lighter schema than
enterprise Salesforce / ServiceNow / Snowflake objects.

The Connect AI features being measured (Custom Tools, Derived Views,
Workspaces, etc.) behave identically regardless of the underlying source
type.
