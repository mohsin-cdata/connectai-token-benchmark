# Connect AI Token Reduction Benchmark - Final Results

- **Model:** `claude-sonnet-4-6` (Claude Sonnet 4.6 (May 2026 list price))
- **Pricing:** $3.00 / MTok input, $15.00 / MTok output (Claude Sonnet 4.6 list price, May 2026)
- **Query:** Show me open support tickets, the related Salesforce accounts, and their Snowflake revenue data for enterprise customers. Return up to 50 rows.
- **Methodology:** Each scenario measured across multiple independent runs (4-16 per scenario) at temperature=0, max_tokens=1024, max_turns=6 (10 for Raw baseline). Real multi-turn execution against live Connect AI MCP - the script fires Claude planning, executes the resulting tool calls against the corresponding MCP endpoint, feeds tool_results back, repeats until end_turn or max_turns. Median used for high-variance scenarios (Raw baseline, Derived Views) where Claude's discovery path varies; mean used for deterministic scenarios.

## Headline table (paste-ready for the blog)

| Feature | § | Total tokens | Tool calls | Reduction | $ / query | $ / mo @1K | $ / mo @10K | $ / mo @50K | $ / mo @100K | Runs | Aggregation | Variance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Raw baseline | §2 | 183,541 | 22 | — | $0.5957 | $0.00 | $0.00 | $0.00 | $0.00 | 6 | median | 32.4% |
| Derived Views | §3.1 | 40,983 | 4 | 77.7% | $0.1462 | $449.50 | $4495.02 | $22475.10 | $44950.20 | 16 | median | 81.9% |
| Workspaces | §3.2 | 11,713 | 3 | 93.6% | $0.0488 | $546.91 | $5469.09 | $27345.45 | $54690.90 | 6 | mean | 0.1% |
| Jobs / Caching | §3.3 | 19,778 | 2 | 89.2% | $0.0752 | $520.51 | $5205.09 | $26025.45 | $52050.90 | 4 | mean | 0.0% |
| Custom Tools | §3.4 | 4,427 | 1 | 97.6% | $0.0267 | $569.05 | $5690.55 | $28452.75 | $56905.50 | 6 | mean | 0.8% |
| Toolkits | §3.5 | 16,384 | 3 | 91.1% | $0.0628 | $532.91 | $5329.08 | $26645.40 | $53290.80 | 6 | mean | 0.0% |
| AI Skills | §3.6 | 16,940 | 1 | 90.8% | $0.0580 | $537.68 | $5376.84 | $26884.20 | $53768.40 | 6 | mean | 0.2% |
| Combined (all features) | §4 | 11,791 | 3 | 93.6% | $0.0489 | $546.81 | $5468.10 | $27340.50 | $54681.00 | 6 | mean | 0.2% |

## Full breakdown including input/output split

| Feature | § | Input | Output | Total | Calls | Wall (s) | Reduction | Cost/q | Var % | Runs |
|---|---|---|---|---|---|---|---|---|---|---|
| Raw baseline | §2 | 179,912 | 3,732 | 183,541 | 22 | 242.8 | — | $0.5957 | 32.4% | 6 |
| Derived Views | §3.1 | 39,038 | 1,940 | 40,983 | 4 | 50.7 | 77.7% | $0.1462 | 81.9% | 16 |
| Workspaces | §3.2 | 10,574 | 1,139 | 11,713 | 3 | 30.5 | 93.6% | $0.0488 | 0.1% | 6 |
| Jobs / Caching | §3.3 | 18,454 | 1,323 | 19,778 | 2 | 34.1 | 89.2% | $0.0752 | 0.0% | 4 |
| Custom Tools | §3.4 | 3,312 | 1,115 | 4,427 | 1 | 19.1 | 97.6% | $0.0267 | 0.8% | 6 |
| Toolkits | §3.5 | 15,246 | 1,138 | 16,384 | 3 | 30.3 | 91.1% | $0.0628 | 0.0% | 6 |
| AI Skills | §3.6 | 16,339 | 601 | 16,940 | 1 | 20.2 | 90.8% | $0.0580 | 0.2% | 6 |
| Combined (all features) | §4 | 10,662 | 1,128 | 11,791 | 3 | 29.0 | 93.6% | $0.0489 | 0.2% | 6 |

## Methodology notes per scenario

- **Raw baseline** (§2): Real multi-turn, global MCP, basic prompt. Claude does full discovery (getCatalogs -> getInstructions -> getSchemas -> getTables -> getColumns -> queryData chain). Median across 6 runs accounts for Claude's variable discovery path.
- **Derived Views** (§3.1): Real multi-turn, global MCP + system-prompt hint pointing at the BMK_Incident_Account_Revenue Derived View. Median across 16 runs; majority cluster at 40-45K with occasional outliers (28K-65K) when Claude varies its discovery path before reaching the view.
- **Workspaces** (§3.2): Real multi-turn, Toolkit MCP filtered to 3 named Custom Tools.
- **Jobs / Caching** (§3.3): Real cached queries via global MCP. ServiceNow.incident + Salesforce.Account cached in PostgreSQL via Connect AI Jobs (Status: Success). Snowflake excluded - relational source can't be cached.
- **Custom Tools** (§3.4): Real multi-turn, Toolkit MCP filtered to single get_incidents Custom Tool.
- **Toolkits** (§3.5): Real multi-turn, full Toolkit MCP (16 tools: 13 source-prefixed universal tools + 3 named Custom Tools).
- **AI Skills** (§3.6): Real multi-turn, global MCP (11 tools) + tightened skill-style system prompt that pre-specifies the SQL and forbids retry/discovery.
- **Combined (all features)** (§4): Real multi-turn, Toolkit MCP filtered to 3 named Custom Tools + skill-style system prompt forcing single direct invocation.

## Summary takeaways

- **Strongest single feature: Custom Tools - 97.6% reduction.**
  Drops cost from $0.596/query to $0.027/query - $5691/mo saved at 10,000 queries, $56906/mo at 100,000.
- Cost saving math = (baseline cost/query - scenario cost/query) x monthly volume.
- Batch (-50%) and prompt caching (-90% input) compound on top of the savings shown.
