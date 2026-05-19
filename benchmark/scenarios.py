"""Define the 8 benchmark scenarios mapped to brief sections.

Tool sources used per scenario:

  - Global MCP        : universal CData tools (queryData, getCatalogs, ...)         (live)
  - Toolkit MCP       : 13 source-prefixed tools + named Custom Tools              (live)
  - Workspace MCP     : returns Method not found for tools/list at present, so tool
                        defs below are synthesised to mirror the 4 typical workspace
                        assets (Account, incident, OPPORTUNITY, Derived View).

Tool descriptions reference source TYPES (ServiceNow, Salesforce, Snowflake) but
do NOT reference your tenant connection names or catalog paths. Those live in
config.py and never appear in Claude's prompt input.
"""
from typing import Any, Dict, List

import config
from benchmark.normalizer import filter_tools


def _user_msg(text: str) -> List[Dict[str, Any]]:
    return [{"role": "user", "content": text}]


# ---------------------------------------------------------------------------
# Synthetic tool defs (mirror typical workspace assets)
# ---------------------------------------------------------------------------

def _t_servicenow_incident() -> Dict[str, Any]:
    cols = ["number","short_description","priority","state","urgency","severity",
            "category","opened_at","company","assigned_to","resolved_at","caller_id",
            "sys_updated_on","close_code","resolution_notes","impact","subcategory"]
    return {
        "name": "query_servicenow_incident",
        "description": (
            "Query the ServiceNow incident table. Returns ITSM ticket records with "
            "status, priority, category, and account references. Use to find open "
            "or recently-updated tickets for cross-system reporting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "where": {"type": "string", "description": "WHERE clause"},
                "limit": {"type": "integer", "default": 50},
                **{c: {"type": "string", "description": f"ServiceNow incident.{c}"} for c in cols},
            },
        },
    }


def _t_salesforce_account_full() -> Dict[str, Any]:
    """Section 3.4 baseline: the unscoped 73-column Salesforce Account tool."""
    sf_columns = [
        "Id","IsDeleted","MasterRecordId","Name","Type","ParentId","BillingStreet",
        "BillingCity","BillingState","BillingPostalCode","BillingCountry","BillingLatitude",
        "BillingLongitude","BillingGeocodeAccuracy","BillingAddress","ShippingStreet",
        "ShippingCity","ShippingState","ShippingPostalCode","ShippingCountry",
        "ShippingLatitude","ShippingLongitude","ShippingGeocodeAccuracy","ShippingAddress",
        "Phone","Fax","AccountNumber","Website","PhotoUrl","Sic","Industry","AnnualRevenue",
        "NumberOfEmployees","Ownership","TickerSymbol","Description","Rating","Site",
        "OwnerId","CreatedDate","CreatedById","LastModifiedDate","LastModifiedById",
        "SystemModstamp","LastActivityDate","LastViewedDate","LastReferencedDate",
        "Jigsaw","JigsawCompanyId","CleanStatus","AccountSource","DunsNumber","Tradestyle",
        "NaicsCode","NaicsDesc","YearStarted","SicDesc","DandbCompanyId","OperatingHoursId",
        "CustomerPriority__c","SLA__c","Active__c","NumberofLocations__c","UpsellOpportunity__c",
        "SLASerialNumber__c","SLAExpirationDate__c","TaxId__c","Region__c","Tier__c",
        "AccountManager__c","RenewalDate__c","CreditRating__c","SegmentName__c","ContractType__c",
    ]
    props = {c: {"type": "string", "description": f"Salesforce Account.{c}"} for c in sf_columns}
    return {
        "name": "salesforce_account_full",
        "description": (
            "Query the Salesforce Account object. Returns all 73 standard and custom fields "
            "for matching account records. Use this to look up account profile, billing, "
            "ownership, revenue, SLA, and territory information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "where":  {"type": "string", "description": "SOQL WHERE clause"},
                "limit":  {"type": "integer", "description": "Max rows", "default": 100},
                "fields": {"type": "array", "items": {"type": "string"},
                           "description": "Subset of available fields to return"},
                **props,
            },
        },
    }


def _t_salesforce_account_scoped() -> Dict[str, Any]:
    return {
        "name": "get_sf_accounts",
        "description": (
            "Return Salesforce enterprise accounts with revenue, SLA, and priority. "
            "Use for account-level revenue lookups only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "Id":                  {"type": "string"},
                "Name":                {"type": "string"},
                "Industry":            {"type": "string"},
                "AnnualRevenue":       {"type": "number"},
                "CustomerPriority__c": {"type": "string"},
                "SLA__c":              {"type": "string"},
                "Active__c":           {"type": "string"},
            },
        },
    }


def _t_snowflake_opportunity() -> Dict[str, Any]:
    cols = ["ID","ACCOUNT_ID","NAME","AMOUNT","STAGE_NAME","EXPECTED_REVENUE",
            "FISCAL_YEAR","FISCAL_QUARTER","CLOSE_DATE","IS_WON","IS_CLOSED",
            "PROBABILITY","TYPE","LEAD_SOURCE","NEXT_STEP","CAMPAIGN_ID",
            "OWNER_ID","CREATED_DATE","LAST_MODIFIED_DATE","_FIVETRAN_SYNCED",
            "TOTAL_OPPORTUNITY_QUANTITY","HASOPENACTIVITY","HASOVERDUETASK"]
    return {
        "name": "query_snowflake_opportunity",
        "description": (
            "Query the Snowflake OPPORTUNITY warehouse table. Returns deal records with "
            "revenue, stage, fiscal period, and account references. Use for pipeline "
            "and won-revenue reporting joined to Salesforce Account by ACCOUNT_ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "where": {"type": "string", "description": "WHERE clause"},
                "limit": {"type": "integer", "default": 50},
                **{c: {"type": "string", "description": f"OPPORTUNITY.{c}"} for c in cols},
            },
        },
    }


def _t_derived_view() -> Dict[str, Any]:
    """Section 3.1 optimised: pre-joined cross-source view."""
    return {
        "name": "query_bmk_incident_account_revenue",
        "description": (
            "Pre-joined view of open ServiceNow incidents enriched with their Salesforce "
            "account profile (Industry, AnnualRevenue, SLA, CustomerPriority) and the "
            "matched Snowflake opportunity revenue (Amount, StageName, FiscalYear, IsWon). "
            "Returns 50 rows per call. Use for any cross-source enterprise-customer ticket "
            "report - this single tool replaces three chained source queries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 50},
            },
        },
    }


def _t_cached_payload() -> Dict[str, Any]:
    """Section 3.3 cached path: pre-fetched, pre-formatted payload tool."""
    return {
        "name": "cached_incident_account_revenue",
        "description": (
            "Return the pre-fetched, cached cross-source result. Backed by Connect AI's "
            "Caching feature against ServiceNow.incident and Salesforce.Account (Snowflake "
            "is not cached - relational source). Pre-formatted compact payload; no live "
            "source query, no schema discovery, no tool_use round-trip overhead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 50},
            },
        },
    }


# ---------------------------------------------------------------------------
# Scenario builder
# ---------------------------------------------------------------------------

def build_scenarios(global_tools: List[Dict[str, Any]],
                    workspace_tools: List[Dict[str, Any]],
                    toolkit_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """All 8 scenarios.

    workspace_tools is unused at the moment - the Workspace MCP endpoint does not
    enumerate via tools/list (Connect AI quirk). We synthesise tool defs that mirror
    the 4 typical workspace assets (incident, Account, OPPORTUNITY, Derived View).
    """
    nl_query = config.QUERY_NL

    sn_tool   = _t_servicenow_incident()
    sf_tool   = _t_salesforce_account_full()    # workspace exposes the full Account
    snow_tool = _t_snowflake_opportunity()
    dv_tool   = _t_derived_view()

    workspace_synth_tools = [sn_tool, sf_tool, snow_tool, dv_tool]

    workspace_collapsed = filter_tools(toolkit_tools, ["workspace"]) or [dv_tool]

    scenarios = [
        {
            "name":           "Raw baseline",
            "brief_section":  "§2",
            "summary":        f"Global MCP, all {len(global_tools)} universal tools exposed (no Connect AI features)",
            "tools":          global_tools,
            "system":         config.SYSTEM_PROMPT_BASIC,
            "messages":       _user_msg(nl_query),
        },
        {
            "name":           "Derived Views",
            "brief_section":  "§3.1",
            "summary":        "1 pre-joined view tool replaces 3 raw source tools",
            "tools":          [dv_tool],
            "_baseline_tools":[sn_tool, sf_tool, snow_tool],
            "system":         config.SYSTEM_PROMPT_BASIC,
            "messages":       _user_msg(nl_query),
            "static_only":    True,
            "note":           "Static comparison: 3 raw source-tool defs vs 1 Derived View tool def.",
        },
        {
            "name":           "Workspaces",
            "brief_section":  "§3.2",
            "summary":        "Workspace-scoped surface, 4 asset-level tools",
            "tools":          workspace_synth_tools,
            "system":         config.SYSTEM_PROMPT_BASIC,
            "messages":       _user_msg(nl_query),
            "note":           "Workspace MCP endpoint does not enumerate via tools/list; "
                              "tool defs synthesised to mirror its 4 actual assets.",
        },
        {
            "name":           "Jobs / Caching",
            "brief_section":  "§3.3",
            "summary":        "Cached pre-fetched payload; eliminates live tool call",
            "tools":          [_t_cached_payload()],
            "system":         config.SYSTEM_PROMPT_BASIC,
            "messages":       _user_msg(nl_query),
            "note":           "Snowflake excluded from Connect AI caching (relational source); "
                              "ServiceNow + Salesforce cache jobs are queued.",
        },
        {
            "name":           "Custom Tools",
            "brief_section":  "§3.4",
            "summary":        "Scoped 6-col tool replaces 73-col raw schema",
            "tools":          [_t_salesforce_account_scoped()],
            "_baseline_tools":[_t_salesforce_account_full()],
            "system":         config.SYSTEM_PROMPT_BASIC,
            "messages":       _user_msg(nl_query),
            "static_only":    True,
        },
        {
            "name":           "Toolkits",
            "brief_section":  "§3.5",
            "summary":        f"Toolkit MCP, {len(toolkit_tools)} curated tools",
            "tools":          toolkit_tools,
            "system":         config.SYSTEM_PROMPT_BASIC,
            "messages":       _user_msg(nl_query),
        },
        {
            "name":           "AI Skills",
            "brief_section":  "§3.6",
            "summary":        "Constrained system prompt + 1 tool, skips planning",
            "tools":          [dv_tool],
            "system":         config.SYSTEM_PROMPT_SKILL,
            "messages":       _user_msg(nl_query),
        },
        {
            "name":           "Combined (all features)",
            "brief_section":  "§4",
            "summary":        "Workspace + Derived View + Caching + Skill prompt stacked",
            "tools":          [_t_cached_payload()],
            "system":         config.SYSTEM_PROMPT_SKILL,
            "messages":       _user_msg(nl_query),
        },
    ]
    return scenarios
