"""Central config for the Connect AI token benchmark.

Credentials and tenant-specific identifiers come from .env. The defaults below
are placeholders -- replace them via .env (recommended) or by editing this file.
Tenant identifiers are NEVER sent to Claude as input. They are used internally
by the script to (a) reach the right MCP endpoints and (b) build reference SQL
fragments for documentation and static count_tokens comparisons.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Credentials (from .env)
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
CDATA_EMAIL        = os.environ.get("CDATA_EMAIL", "")
CDATA_ACCESS_TOKEN = os.environ.get("CDATA_ACCESS_TOKEN", "")

# ---------------------------------------------------------------------------
# Model + pricing
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"

PRICING = {
    "input_per_mtok":  3.00,
    "output_per_mtok": 15.00,
    "model_label":     "Claude Sonnet 4.6 (May 2026 list price)",
}

PROJECTION_VOLUMES = [1_000, 10_000, 50_000, 100_000]

# ---------------------------------------------------------------------------
# MCP endpoints (from .env)
# ---------------------------------------------------------------------------
# MCP_GLOBAL_URL is the universal Connect AI MCP endpoint -- always the same.
# MCP_WORKSPACE_URL and MCP_TOOLKIT_URL are tenant-specific. Set them in .env
# after you create a Workspace and a Toolkit in your Connect AI tenant (see
# seed/load-*.md). If unset, the corresponding scenarios use synthesised tool
# surfaces and the workspace/toolkit numbers are static count_tokens
# comparisons rather than live MCP calls.
MCP_GLOBAL_URL    = os.environ.get("MCP_GLOBAL_URL",    "https://mcp.cloud.cdata.com/mcp")
MCP_WORKSPACE_URL = os.environ.get("MCP_WORKSPACE_URL", "")
MCP_TOOLKIT_URL   = os.environ.get("MCP_TOOLKIT_URL",   "")

# ---------------------------------------------------------------------------
# Source identifiers (from .env)
# ---------------------------------------------------------------------------
# These match YOUR CData Connect AI connection names. The defaults below are
# placeholders -- override them in .env to point at your tenant. The SQL
# fragments and scenarios.py tool definitions reference these so a recipient
# only changes them in one place.
CDATA_ITSM_CATALOG   = os.environ.get("CDATA_ITSM_CATALOG",   "YourServiceNowConnection")
CDATA_ITSM_SCHEMA    = os.environ.get("CDATA_ITSM_SCHEMA",    "ServiceNow")
CDATA_ITSM_TABLE     = os.environ.get("CDATA_ITSM_TABLE",     "incident")

CDATA_CRM_CATALOG    = os.environ.get("CDATA_CRM_CATALOG",    "YourSalesforceConnection")
CDATA_CRM_SCHEMA     = os.environ.get("CDATA_CRM_SCHEMA",     "Salesforce")
CDATA_CRM_TABLE      = os.environ.get("CDATA_CRM_TABLE",      "Account")

CDATA_WH_CATALOG     = os.environ.get("CDATA_WH_CATALOG",     "YourSnowflakeConnection")
CDATA_WH_SCHEMA      = os.environ.get("CDATA_WH_SCHEMA",      "SALESFORCE")
CDATA_WH_TABLE       = os.environ.get("CDATA_WH_TABLE",       "OPPORTUNITY")

DERIVED_VIEW_NAME    = os.environ.get("DERIVED_VIEW_NAME",    "BMK_Incident_Account_Revenue")

# Fully-qualified names -- used by scenarios.py and BENCHMARK-PROMPTS-AND-QUERIES.md
ITSM_FQN = f"[{CDATA_ITSM_CATALOG}].[{CDATA_ITSM_SCHEMA}].[{CDATA_ITSM_TABLE}]"
CRM_FQN  = f"[{CDATA_CRM_CATALOG}].[{CDATA_CRM_SCHEMA}].[{CDATA_CRM_TABLE}]"
WH_FQN   = f"[{CDATA_WH_CATALOG}].[{CDATA_WH_SCHEMA}].[{CDATA_WH_TABLE}]"
DV_FQN   = f"[CData].[DerivedViews].[{DERIVED_VIEW_NAME}]"

# ---------------------------------------------------------------------------
# Natural-language query + reference SQL fragments
# ---------------------------------------------------------------------------
# QUERY_NL is the single user-turn prompt Claude receives in every scenario.
# The SQL fragments are NOT sent to Claude -- they are used as static
# count_tokens baselines for the Custom Tools and Derived Views static
# comparisons, and reproduced in BENCHMARK-PROMPTS-AND-QUERIES.md for the
# methodology audit.

QUERY_NL = (
    "Show me open support tickets, the related Salesforce accounts, "
    "and their Snowflake revenue data for enterprise customers. "
    "Return up to 50 rows."
)

QUERY_SQL_DERIVED_VIEW = f"SELECT * FROM {DV_FQN} LIMIT 50"

QUERY_SQL_INCIDENTS = (
    "SELECT number, short_description, priority, state, urgency, severity, "
    "category, opened_at, company "
    f"FROM {ITSM_FQN} "
    "WHERE state = 2 AND priority IN (1,2) LIMIT 50"
)
QUERY_SQL_ACCOUNTS = (
    "SELECT Id, Name, Industry, AnnualRevenue, CustomerPriority__c, SLA__c, Active__c "
    f"FROM {CRM_FQN} LIMIT 50"
)
QUERY_SQL_OPPORTUNITY = (
    "SELECT ACCOUNT_ID, AMOUNT, STAGE_NAME, EXPECTED_REVENUE, IS_WON, FISCAL_YEAR "
    f"FROM {WH_FQN} LIMIT 50"
)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
# SYSTEM_PROMPT_BASIC is the un-hinted prompt; Raw baseline, Workspaces,
# Custom Tools, and Toolkits scenarios use it. SYSTEM_PROMPT_SKILL pre-scripts
# the workflow against the Derived View -- this is intentional (AI Skills as
# a feature works by revealing the tool name and SQL to Claude up front).

SYSTEM_PROMPT_BASIC = (
    "You are an enterprise data assistant. Use the provided tools to answer the user's "
    "question. Return results as a concise markdown summary."
)

SYSTEM_PROMPT_SKILL = (
    "You are an enterprise data assistant executing a pre-defined workflow.\n"
    f"WORKFLOW: Call the {DERIVED_VIEW_NAME} tool exactly once. Do not call any other "
    "tools. Summarise the result as a 5-bullet markdown list with no preamble."
)

# ---------------------------------------------------------------------------
# Runner defaults
# ---------------------------------------------------------------------------

OUTPUT_DIR            = os.path.join(os.path.dirname(__file__), "output")
RUNS_PER_SCENARIO     = 1
INFERENCE_MAX_TOKENS  = 1024
INFERENCE_TEMPERATURE = 0.0
