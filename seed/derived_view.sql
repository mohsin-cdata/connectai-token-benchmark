-- Connect AI Derived View - cross-source pre-join for the benchmark.
--
-- Create this view in Connect AI's Explorer:
--   1. Click Explorer in the left nav
--   2. Click SQL Editor
--   3. Paste this query (replacing connection names below with yours from .env)
--   4. Click Execute -- verify rows return
--   5. Click Save > Save as Derived View
--   6. View Name: BMK_Incident_Account_Revenue (matches DERIVED_VIEW_NAME in .env)
--   7. Click Confirm
--
-- The placeholders [ServiceNow], [Salesforce], [Snowflake] are the catalog
-- names YOU chose when creating each CData Connect AI connection. Replace
-- with your actual names (matches CDATA_*_CATALOG values in your .env).
--
-- Filters every source to BMK-prefixed rows only so the view is benchmark-
-- scoped even when your sources contain other data.

SELECT
    i.number              AS ticket_number,
    i.short_description   AS ticket_summary,
    i.priority            AS ticket_priority,
    i.state               AS ticket_state,
    i.opened_at           AS ticket_opened_at,
    a.Name                AS AccountName,
    a.Industry            AS Industry,
    a.AnnualRevenue       AS AnnualRevenue,
    a.CustomerPriority__c AS CustomerPriority,
    a.SLA__c              AS SLA,
    a.Active__c           AS Active,
    o.AMOUNT              AS OpportunityAmount,
    o.STAGE_NAME          AS StageName,
    o.EXPECTED_REVENUE    AS ExpectedRevenue,
    o.IS_WON              AS IsWon,
    o.FISCAL_YEAR         AS FiscalYear
FROM [ServiceNow].[ServiceNow].[incident] i
LEFT JOIN [Salesforce].[Salesforce].[Account] a
    ON i.company = a.Id
LEFT JOIN [Snowflake].[SALESFORCE].[OPPORTUNITY] o
    ON a.Id = o.ACCOUNT_ID
WHERE i.number LIKE 'BMK-%'
  AND a.Name LIKE 'BMK\_%' ESCAPE '\'
  AND o.ACCOUNT_ID LIKE 'BMK_%'
  AND i.state = 2
