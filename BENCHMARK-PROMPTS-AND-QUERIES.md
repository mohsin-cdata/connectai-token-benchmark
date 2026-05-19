# Benchmark - All Queries and Prompts

References of every prompt, system message, and SQL query used to produce the
locked results in `connectai-token-benchmark/LOCKED_RESULTS.py`.

Sources:
- `connectai-token-benchmark/config.py`
- `connectai-token-benchmark/benchmark/scenarios.py`
- `connectai-token-benchmark/test_real_multiturn_v5.py` (Workspaces, Custom Tools, Caching, AI Skills, Combined - 6 runs each)
- `connectai-token-benchmark/test_variance_v7.py` (Raw baseline, Derived Views, Toolkits)
- `connectai-token-benchmark/test_dv_4more.py` + `test_pass3.py` (extra Derived View runs - same prompt as v7)

---

## 1. Model and run config

| Setting | Value |
| --- | --- |
| Model | `claude-sonnet-4-6` |
| Temperature | `0.0` |
| Max tokens per turn | `1024` |
| Max turns | `6` (10 for Raw baseline) |
| Max tool-result chars (truncation) | `8000` |
| Pricing | $3.00 / MTok input, $15.00 / MTok output |
| Inter-scenario cooldown | `75s` |
| Initial warm-up sleep | `30s` |

---

## 2. The single natural-language user prompt (all 8 scenarios)

```
Show me open support tickets, the related Salesforce accounts, and their Snowflake
revenue data for enterprise customers. Return up to 50 rows.
```

Defined as `config.QUERY_NL`. Used verbatim as the single user-turn message in every
scenario - the only thing that varies is the system prompt and the tool surface.

---

## 3. System prompts (5 distinct)

### 3.1 `SYS_BASIC` - used for Raw baseline, Derived Views (v7), Workspaces, Custom Tools, Toolkits

```
You are an enterprise data assistant. Use the provided tools to answer the user's
question. Return a concise markdown summary.
```

### 3.2 `SYS_DERIVED_HINT` - used for Derived Views (variance v7 + extra DV runs)

```
You are an enterprise data assistant. A pre-joined Derived View named
'BMK_Incident_Account_Revenue' lives at catalog 'CData', schema 'DerivedViews'.
It pre-joins ServiceNow open incidents with Salesforce Account profile and
Snowflake opportunity revenue. Prefer this single source. Use queryData with
one SELECT against [CData].[DerivedViews].[BMK_Incident_Account_Revenue].
Return a concise markdown summary.
```

### 3.3 `SYS_AI_SKILL_TIGHT` - used for AI Skills

```
You are an enterprise data assistant executing a strictly pre-defined skill workflow.
WORKFLOW (do not deviate, do not retry, do not discover):
  STEP 1: Call queryData EXACTLY ONCE with this SQL:
          SELECT * FROM [CData].[DerivedViews].[BMK_Incident_Account_Revenue] LIMIT 50
  STEP 2: Render the result as a 5-bullet markdown summary. No preamble.
  STEP 3: Stop. Do not call any other tool. Do not retry on error - just report the error.
```

### 3.4 `SYS_CACHING_SKILL` - used for Jobs / Caching

```
You are an enterprise data assistant. The cross-source enterprise customer data is
available pre-fetched and cached as a single tool. Call it once, summarise the result.
  STEP 1: Call cached_incident_account_revenue with limit=50.
  STEP 2: Render the cached result as a 5-bullet markdown summary. No preamble.
  STEP 3: Stop.
```

### 3.5 `SYS_COMBINED` - used for Combined (all features)

```
You are an enterprise data assistant.
WORKFLOW:
  STEP 1: Call get_incidents (no arguments) to retrieve open ServiceNow incidents.
  STEP 2: Render the result as a 5-bullet markdown summary. No preamble.
  STEP 3: Stop. Do not call any other tool.
```

---

## 4. SQL queries

### 4.1 Derived View definition (saved in Connect AI as `CData.DerivedViews.BMK_Incident_Account_Revenue`)

```sql
SELECT i.number, i.short_description, i.priority, i.state,
    i.urgency, i.severity, i.category, i.opened_at,
    a.Name AS AccountName, a.Industry, a.AnnualRevenue,
    a.CustomerPriority__c, a.SLA__c, a.Active__c,
    o.AMOUNT AS OpportunityRevenue, o.STAGE_NAME,
    o.EXPECTED_REVENUE, o.IS_WON, o.FISCAL_YEAR
FROM [${CDATA_ITSM_CATALOG}].[ServiceNow].[incident] i
LEFT JOIN [${CDATA_CRM_CATALOG}].[Salesforce].[Account] a
    ON i.company = a.Id
LEFT JOIN [${CDATA_WH_CATALOG}].[SALESFORCE].[OPPORTUNITY] o
    ON a.Id = o.ACCOUNT_ID
WHERE i.state = 2 LIMIT 50
```

### 4.2 SQL Claude is instructed to issue against the Derived View (AI Skills + DV scenarios)

```sql
SELECT * FROM [CData].[DerivedViews].[BMK_Incident_Account_Revenue] LIMIT 50
```

### 4.3 Source-level SQL fragments (used as comparison baselines in static scenarios and as Claude's own queries during the Raw baseline multi-turn discovery)

```sql
-- ServiceNow incidents (open, P1/P2)
SELECT number, short_description, priority, state, urgency, severity,
       category, opened_at, company
FROM [${CDATA_ITSM_CATALOG}].[ServiceNow].[incident]
WHERE state = 2 AND priority IN (1,2) LIMIT 50

-- Salesforce Account (enterprise profile + SLA)
SELECT Id, Name, Industry, AnnualRevenue, CustomerPriority__c, SLA__c, Active__c
FROM [${CDATA_CRM_CATALOG}].[Salesforce].[Account] LIMIT 50

-- Snowflake Opportunity (revenue per account)
SELECT ACCOUNT_ID, AMOUNT, STAGE_NAME, EXPECTED_REVENUE, IS_WON, FISCAL_YEAR
FROM [${CDATA_WH_CATALOG}].[SALESFORCE].[OPPORTUNITY] LIMIT 50
```

---

## 5. Synthetic / scripted tool definitions

These are tool defs the script declares to Claude (not pulled from a live MCP). They
exist either to (a) simulate a Connect AI feature whose live path was unavailable, or
(b) act as a static-token comparison baseline.

### 5.1 `cached_incident_account_revenue` (Jobs / Caching)

```json
{
  "name": "cached_incident_account_revenue",
  "description": "Returns the pre-fetched, cached cross-source enterprise customer dataset. Backed by Connect AI Caching (ServiceNow.incident + Salesforce.Account replicated to PostgreSQL warehouse). Pre-formatted compact payload - no live source query, no schema discovery, no tool_use round-trip overhead.",
  "input_schema": {
    "type": "object",
    "properties": { "limit": { "type": "integer", "default": 50 } }
  }
}
```

Claude's `tool_use` for this tool is intercepted by the script and answered with a
synthetic payload of 15 cached rows (ticket / description / priority / state /
account_name / industry / annual_revenue / opportunity_amount / stage_name).

### 5.2 `query_bm_incident_account_revenue` (Derived View - static comparison baseline)

```json
{
  "name": "query_bm_incident_account_revenue",
  "description": "Pre-joined view of open ServiceNow incidents enriched with their Salesforce account profile (Industry, AnnualRevenue, SLA, CustomerPriority) and the matched Snowflake opportunity revenue (Amount, StageName, FiscalYear, IsWon). Returns 50 rows per call. Use for any cross-source enterprise-customer ticket report - this single tool replaces three chained source queries.",
  "input_schema": {
    "type": "object",
    "properties": { "limit": { "type": "integer", "default": 50 } }
  }
}
```

### 5.3 Static-comparison source tools

Used in the static `count_tokens` comparisons that produce the per-feature reduction
numbers in the brief:

- `query_servicenow_incident` - 17 ServiceNow incident columns
- `salesforce_account_full` - all 73 Salesforce Account columns (raw schema)
- `get_sf_accounts` - 7-column Salesforce Account scoped tool (Custom Tools winner)
- `query_snowflake_opportunity` - 23 Snowflake OPPORTUNITY columns

Full column lists are in `connectai-token-benchmark/benchmark/scenarios.py` lines
25-129. The Custom Tools static comparison is `salesforce_account_full` (73 cols)
vs `get_sf_accounts` (7 cols).

---

## 6. Live MCP endpoints (tools come from these where applicable)

| Endpoint | URL | Tools listed |
| --- | --- | --- |
| Global | `https://mcp.cloud.cdata.com/mcp` | 11 universal CData tools (queryData, getCatalogs, getSchemas, getTables, getColumns, getProcedures, getProcedureParameters, executeProcedure, etc.) |
| Workspace | `https://mcp.cloud.cdata.com/mcp/workspaces/` | `tools/list` returns "Method not found" - workspace tool surface synthesised in script (see `_t_*` defs) |
| Toolkit | `https://mcp.cloud.cdata.com/mcp/toolkits/` | 16 tools = 13 source-prefixed universal tools + 3 named Custom Tools (`get_incidents`, `get_sf_accounts`, `get_opportunity_revenue`) |

Auth on every MCP call: `Authorization: Basic base64(email:PAT)`.

---

## 7. Per-scenario wiring (locked configuration)

| Scenario | System prompt | Endpoint | Tools fed | Runs | Aggregation | Source script |
| --- | --- | --- | --- | --- | --- | --- |
| Raw baseline (§2) | `SYS_BASIC` | Global | 11 (all) | 6 | median | `test_variance_v7.py` |
| Derived Views (§3.1) | `SYS_DERIVED_HINT` | Global | 11 (all) | 16 | median | `test_variance_v7.py` + extras |
| Workspaces (§3.2) | `SYS_BASIC` | Toolkit | 3 (filter: `get_incidents`, `get_sf_accounts`, `get_opportunity_revenue`) | 6 | mean | `test_real_multiturn_v5.py` |
| Jobs / Caching (§3.3) | `SYS_CACHING_SKILL` | Synthetic | 1 (`cached_incident_account_revenue`) | 4 | mean | `test_real_multiturn_v5.py` |
| Custom Tools (§3.4) | `SYS_BASIC` | Toolkit | 1 (filter: `get_incidents`) | 6 | mean | `test_real_multiturn_v5.py` |
| Toolkits (§3.5) | `SYS_BASIC` | Toolkit | 16 (all) | 6 | mean | `test_variance_v7.py` |
| AI Skills (§3.6) | `SYS_AI_SKILL_TIGHT` | Global | 11 (all) | 6 | mean | `test_real_multiturn_v5.py` |
| Combined (§4) | `SYS_COMBINED` | Toolkit | 3 (Custom Tools subset) | 6 | mean | `test_real_multiturn_v5.py` |

`messages` is identical across all rows: a single user turn containing the §2 NL prompt.

---

## 8. Multi-turn loop semantics (real scenarios)

For every non-static scenario the runner does:

```
messages = [{"role": "user", "content": QUERY_NL}]
for turn in 1..MAX_TURNS:
    resp = anthropic.messages.create(
        model="claude-sonnet-4-6", system=<scenario.system>, tools=<scenario.tools>,
        messages=messages, max_tokens=1024, temperature=0.0
    )
    if resp.stop_reason == "end_turn" or no tool_use blocks: break
    messages.append({"role": "assistant", "content": resp.content})
    for tool_use in resp.tool_use_blocks:
        result = mcp_client.call_tool(tool_use.name, tool_use.input)   # or synthetic
        if len(result_json) > 8000: truncate
    messages.append({"role": "user", "content": [tool_results...]})
```

`input_tokens` and `output_tokens` are summed across every turn; that sum is what
LOCKED_RESULTS reports.

---

## 9. Headline numbers reproduced (so the recipient can sanity-check)

Source: `connectai-token-benchmark/LOCKED_RESULTS.py`.

| Scenario | Input | Output | Total | Tool calls | vs Raw |
| ---: | ---: | ---: | ---: | ---: | ---: |
| Raw baseline | 179,912 | 3,732 | 183,541 | 22 | - |
| Derived Views | 39,038 | 1,940 | 40,983 | 4 | -77.7% |
| Workspaces | 10,574 | 1,139 | 11,713 | 3 | -93.6% |
| Jobs / Caching | 18,454 | 1,323 | 19,778 | 2 | -89.2% |
| Custom Tools | 3,312 | 1,115 | 4,427 | 1 | -97.6% |
| Toolkits | 15,246 | 1,138 | 16,384 | 3 | -91.1% |
| AI Skills | 16,339 | 601 | 16,940 | 1 | -90.8% |
| Combined | 10,662 | 1,128 | 11,791 | 3 | -93.6% |
