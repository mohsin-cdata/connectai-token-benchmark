# Load `seed/accounts.csv` into Salesforce

**Recommended:** use a Salesforce Developer Edition org. Free, permanent, separate from any production.

1. Sign up at https://developer.salesforce.com/signup (takes ~2 minutes).
2. Verify the email; log into your new org.
3. Choose one of the import paths below.

## Option 1: Data Loader (UI, easiest)

1. Download Data Loader from Setup -> Data Loader.
2. Launch it, click **Insert**.
3. Log in with your developer-org credentials.
4. Choose **Account** as the object.
5. Browse to `seed/accounts.csv` and click **Next**.
6. Click **Create or Edit a Map** and map columns:
    - `name` -> `Name`
    - `industry` -> `Industry`
    - `annual_revenue` -> `AnnualRevenue`
    - `sla` -> `SLA__c`  (you may need to create this custom field first)
    - `customer_priority` -> `CustomerPriority__c`
    - `active` -> `Active__c`
    - `segment` -> (skip)
7. Save the map, choose an output dir, click **Finish**.

## Option 2: SFDX CLI

```powershell
# 1. Install sf CLI: https://developer.salesforce.com/tools/sfdxcli
sf auth web login --alias bmk-dev
sf data import bulk --sobject Account --file seed\accounts.csv --target-org bmk-dev
```

## Option 3: Workbench (web, no install)

1. Open https://workbench.developerforce.com -> login with your dev org.
2. Data -> Insert -> Account -> Single file -> upload `seed/accounts.csv`.
3. Map fields, run.

## Connect AI configuration

1. In Connect AI, create a new **Salesforce** connection. The OAuth flow targets your developer org.
2. Note the **connection name** you choose - that's what goes into ``.env`` as the `CDATA_*_CATALOG` value.
3. By default the schema is `Salesforce` and the table is `Account`. Leave those as-is unless you renamed something.

## Verify

In Connect AI's query window:

```sql
SELECT COUNT(*) FROM [<your-sf-conn>].[Salesforce].[Account]
WHERE Name LIKE 'BMK\_%' ESCAPE '\'
```

Should return `50`.

## Custom fields

If `SLA__c`, `CustomerPriority__c`, or `Active__c` don't exist in your dev org, create them under
Setup -> Object Manager -> Account -> Fields & Relationships -> New. Picklist type, simple text values.
The benchmark works without these fields too - the seed data just won't fill them in.
