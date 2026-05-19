-- Cleanup script - removes ONLY benchmark-seeded rows (anything BMK-prefixed).
--
-- Run after the benchmark to leave your source clean. Each block targets one
-- source family; uncomment the block for your active profile.
--
-- WARNING: This is a DELETE script. Read each block before running.
-- Connect AI's read-only PAT cannot execute these - they need a write-enabled
-- user. Run via your source's native UI/CLI, not via Connect AI.

-- =========================================================================
-- PROFILE A
-- =========================================================================

-- ServiceNow (run via REST or via System Definition -> Scripts -> Background)
-- gr = new GlideRecord('incident');
-- gr.addEncodedQuery('numberSTARTSWITHBMK-');
-- gr.deleteMultiple();

-- Salesforce (Apex / Anonymous):
-- DELETE [SELECT Id FROM Account WHERE Name LIKE 'BMK\_%' ESCAPE '\'];

-- Snowflake:
-- DELETE FROM SALESFORCE.OPPORTUNITY WHERE ACCOUNT_ID LIKE 'BMK_%';

-- =========================================================================
-- PROFILE B
-- =========================================================================

-- Jira Service Management (REST API, server admin only):
-- DELETE /rest/api/3/issue/{issueIdOrKey} for each BMK-* key

-- HubSpot (API):
-- POST https://api.hubapi.com/crm/v3/objects/companies/batch/archive
--   body: {"inputs": [{"id": "<id-of-BMK_-company>"} ...]}

-- Databricks SQL:
-- DELETE FROM default.opportunity WHERE account_id LIKE 'BMK_%';

-- =========================================================================
-- PROFILE C
-- =========================================================================

-- Zendesk (REST API):
-- DELETE /api/v2/tickets/{id}.json  for each BMK ticket

-- Dynamics 365 (Power Automate / OData):
-- DELETE /api/data/v9.2/accounts(<accountid>)  for each BMK_ account

-- BigQuery:
-- DELETE FROM `<project>.benchmark.opportunity` WHERE account_id LIKE 'BMK_%';

-- =========================================================================
-- CONNECT AI - DERIVED VIEW
-- =========================================================================

-- The Derived View itself is metadata, not data. Drop it via the Connect AI
-- UI: Catalogs -> CData -> DerivedViews -> BMK_Incident_Account_Revenue -> Delete.
