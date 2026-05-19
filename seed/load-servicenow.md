# Load `seed/incidents.csv` into ServiceNow

**Recommended:** Personal Developer Instance (PDI). Free, ~5 minutes to provision.

1. Sign up at https://developer.servicenow.com -> Sign in -> **Get Instance**.
2. Once the instance is running, log in to its admin UI (URL like `https://dev12345.service-now.com`).

## Option 1: Import Sets (UI)

1. Navigate to **System Import Sets -> Load Data**.
2. **Create table** = checked; name = `bmk_incident_load`.
3. **Source of the import** = File. Upload `seed/incidents.csv`. Header row = checked.
4. **Submit**, then on the next screen click **Run Transform**.
5. Create a new **Transform Map**:
    - Source table: `bmk_incident_load`
    - Target table: `incident`
    - Field map (drag-drop):
        - `number` -> `number`
        - `short_description` -> `short_description`
        - `priority` -> `priority`
        - `state` -> `state`
        - `urgency` -> `urgency`
        - `severity` -> `severity`
        - `category` -> `category`
        - `opened_at` -> `opened_at`
        - `company` -> `company` (this is a reference field; use the **company name** value or a coalesce on dot-walked `account_id`)
6. Click **Transform**.

## Option 2: REST API (faster, scripted)

```powershell
# Requires: jq (or use PowerShell native ConvertFrom-Csv)
$user  = "admin"
$pass  = "<your-pdi-admin-pass>"
$base  = "https://dev12345.service-now.com/api/now/table/incident"

Import-Csv seed\incidents.csv | ForEach-Object {
    $body = $_ | ConvertTo-Json -Depth 3
    Invoke-RestMethod -Uri $base -Method Post -Body $body `
      -ContentType "application/json" `
      -Headers @{ Authorization = "Basic " + [Convert]::ToBase64String(
          [Text.Encoding]::ASCII.GetBytes("$user`:$pass")) }
}
```

## Connect AI configuration

1. In Connect AI, create a new **ServiceNow** connection pointing at your PDI's instance URL.
2. Note the **connection name** you choose - this is `catalog` in ``.env``.
3. Schema is `ServiceNow`, table is `incident`.

## Verify

```sql
SELECT COUNT(*) FROM [<your-sn-conn>].[ServiceNow].[incident]
WHERE number LIKE 'BMK-%'
```

Should return `50`.

## Company field note

The `company` column in `incidents.csv` contains the BMK_ACC_xxxx account
ID. ServiceNow's `incident.company` is a reference to the `core_company`
table. For the benchmark you have two options:
  - **Easy:** create 50 `core_company` records first (BMK_Acme Manufacturing, ...)
    and let the import resolve by display value.
  - **Easier:** change the column mapping to store the raw string in a custom
    field `u_bmk_account_id`, and the benchmark's join uses that field instead.
    Update ``.env`` `CDATA_ITSM_TABLE` to `u_bmk_account_id` to match.
