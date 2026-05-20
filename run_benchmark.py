"""Entry point for the Connect AI token-reduction benchmark.

Usage examples:
  python run_benchmark.py                    # input-only (free, count_tokens)
  python run_benchmark.py --full             # multi-turn inference vs live MCP
  python run_benchmark.py --full --runs 3    # average 3 multi-turn runs / scenario
  python run_benchmark.py --no-charts        # skip PNG/Mermaid generation
  python run_benchmark.py --skip-mcp         # use cached fixtures, synthetic dispatch
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional

import config
from benchmark import charts, mcp_client, normalizer, reporter, runner, scenarios
from benchmark.reporter import _build_rows


# ---------------------------------------------------------------------------
# Synthetic tool payloads
# ---------------------------------------------------------------------------
# For scenarios whose tools are synthesised (cached_*, custom-tool names that
# don't exist in your tenant yet), the dispatcher returns a compact JSON
# payload that simulates what the real tool would have returned. Sizes are
# tuned to match the rows recorded in the published benchmark; recipients
# should land near LOCKED_RESULTS.py without exactly matching it (multi-turn
# variance is expected).

def _synth_cross_source_rows() -> str:
    return json.dumps([
        {"number": f"BMK-INC{1000+i:04d}", "short_description": f"BMK ticket {i}",
         "priority": (i % 4) + 1, "AccountName": f"BMK_Account_{i}",
         "Industry": ["Technology", "Finance", "Healthcare"][i % 3],
         "AnnualRevenue": (i + 1) * 1_500_000,
         "OpportunityAmount": (i + 1) * 75_000, "StageName": "ClosedWon",
         "FiscalYear": 2026, "IsWon": True}
        for i in range(15)
    ])


def _synth_itsm_rows() -> str:
    return json.dumps([
        {"number": f"BMK-INC{1000+i:04d}", "short_description": f"BMK ticket {i}",
         "priority": (i % 4) + 1, "state": 2, "company": f"BMK_ACC_{i:04d}"}
        for i in range(15)
    ])


def _synth_crm_rows() -> str:
    return json.dumps([
        {"Id": f"BMK_ACC_{i:04d}", "Name": f"BMK_Account_{i}",
         "Industry": ["Technology", "Finance", "Healthcare"][i % 3],
         "AnnualRevenue": (i + 1) * 1_500_000, "SLA__c": "Platinum"}
        for i in range(15)
    ])


def _synth_warehouse_rows() -> str:
    return json.dumps([
        {"ACCOUNT_ID": f"BMK_ACC_{i:04d}", "AMOUNT": (i + 1) * 75_000,
         "STAGE_NAME": "ClosedWon", "EXPECTED_REVENUE": (i + 1) * 75_000,
         "IS_WON": True, "FISCAL_YEAR": 2026}
        for i in range(15)
    ])


# Names of synthesised tools (no live MCP backing). Matched in the dispatcher.
SYNTH_NAMES = {
    # cached / pre-fetched payloads
    "cached_incident_account_revenue":   _synth_cross_source_rows,
    # Derived View synthesised tool (when no real DV is configured)
    "query_bmk_incident_account_revenue":_synth_cross_source_rows,
    # workspace synth tools
    "query_servicenow_incident":         _synth_itsm_rows,
    "salesforce_account_full":           _synth_crm_rows,
    "query_snowflake_opportunity":       _synth_warehouse_rows,
    # Custom Tools (named tools)
    "get_incidents":                     _synth_cross_source_rows,
    "get_sf_accounts":                   _synth_crm_rows,
    "get_opportunity_revenue":           _synth_warehouse_rows,
}


def make_dispatcher(mcli_global: Optional[mcp_client.MCPClient],
                    mcli_workspace: Optional[mcp_client.MCPClient],
                    mcli_toolkit: Optional[mcp_client.MCPClient],
                    global_names: set,
                    workspace_names: set,
                    toolkit_names: set,
                    ) -> Callable[[str, Dict[str, Any]], str]:
    """Build a tool-call dispatcher for the multi-turn runner.

    Routing rules, in order:
      1. If tool name is in SYNTH_NAMES, return the synthetic payload.
      2. If name is in toolkit_names, dispatch via mcli_toolkit.
      3. If name is in workspace_names, dispatch via mcli_workspace.
      4. If name is in global_names, dispatch via mcli_global.
      5. Otherwise return an error stub.
    """
    def dispatch(name: str, args: Dict[str, Any]) -> str:
        if name in SYNTH_NAMES:
            return SYNTH_NAMES[name]()
        try:
            if name in toolkit_names and mcli_toolkit is not None:
                return json.dumps(mcli_toolkit.call_tool(name, args), default=str)
            if name in workspace_names and mcli_workspace is not None:
                return json.dumps(mcli_workspace.call_tool(name, args), default=str)
            if name in global_names and mcli_global is not None:
                return json.dumps(mcli_global.call_tool(name, args), default=str)
        except Exception as e:
            return json.dumps({"error": f"{type(e).__name__}: {e}"})
        return json.dumps({"error": f"no dispatcher for tool {name!r}"})
    return dispatch


def fetch_tools(url: str, label: str) -> List[Dict[str, Any]]:
    print(f"  Fetching tools/list from {label}: {url}")
    cli = mcp_client.MCPClient(url, config.CDATA_EMAIL, config.CDATA_ACCESS_TOKEN)
    cli.initialize()
    raw = cli.list_tools()
    norm = normalizer.normalize_tools(raw)
    print(f"    -> {len(norm)} tools")
    return norm


def main() -> int:
    parser = argparse.ArgumentParser(description="Connect AI token-reduction benchmark")
    parser.add_argument("--full",      action="store_true",
                        help="Run full multi-turn inference (input + output). Costs cents per scenario.")
    parser.add_argument("--runs",      type=int, default=config.RUNS_PER_SCENARIO,
                        help="Multi-turn runs per scenario for averaging.")
    parser.add_argument("--no-charts", action="store_true",
                        help="Skip matplotlib + Mermaid output.")
    parser.add_argument("--skip-mcp",  action="store_true",
                        help="Use cached tool list fixtures from output/_fixtures.json. "
                             "All tool calls during multi-turn dispatch fall back to "
                             "synthetic payloads -- no live source queries.")
    args = parser.parse_args()

    if not config.ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY missing - set it in .env", file=sys.stderr)
        return 2
    if not args.skip_mcp and (not config.CDATA_EMAIL or not config.CDATA_ACCESS_TOKEN):
        print("ERROR: CDATA_EMAIL or CDATA_ACCESS_TOKEN missing - set them in .env", file=sys.stderr)
        return 2

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    fixtures_path = os.path.join(config.OUTPUT_DIR, "_fixtures.json")

    print("=" * 64)
    print("  Connect AI Token Reduction Benchmark")
    print(f"  Model  : {config.MODEL}")
    print(f"  Mode   : {'FULL multi-turn (input + output)' if args.full else 'INPUT-ONLY (count_tokens)'}")
    print(f"  Runs   : {args.runs}")
    print(f"  Source : {'cached fixtures + synthetic dispatch' if args.skip_mcp else 'live MCP'}")
    print("=" * 64)

    # ---- Fetch / load tool fixtures ------------------------------------------
    mcli_global = mcli_workspace = mcli_toolkit = None
    if args.skip_mcp and os.path.exists(fixtures_path):
        with open(fixtures_path) as f:
            cache = json.load(f)
        global_tools    = cache["global"]
        workspace_tools = cache.get("workspace", [])
        toolkit_tools   = cache.get("toolkit", [])
        print("  Loaded tool fixtures from output/_fixtures.json")
    else:
        global_tools    = fetch_tools(config.MCP_GLOBAL_URL, "global")
        mcli_global     = mcp_client.MCPClient(config.MCP_GLOBAL_URL,
                                               config.CDATA_EMAIL,
                                               config.CDATA_ACCESS_TOKEN)
        mcli_global.initialize()
        workspace_tools = []
        toolkit_tools   = []
        if config.MCP_WORKSPACE_URL:
            try:
                workspace_tools = fetch_tools(config.MCP_WORKSPACE_URL, "workspace")
                mcli_workspace = mcp_client.MCPClient(config.MCP_WORKSPACE_URL,
                                                     config.CDATA_EMAIL,
                                                     config.CDATA_ACCESS_TOKEN)
                mcli_workspace.initialize()
            except Exception as e:
                print(f"  WARN: workspace fetch failed ({e}); falling back to synthetic dispatch")
        if config.MCP_TOOLKIT_URL:
            try:
                toolkit_tools = fetch_tools(config.MCP_TOOLKIT_URL, "toolkit")
                mcli_toolkit = mcp_client.MCPClient(config.MCP_TOOLKIT_URL,
                                                   config.CDATA_EMAIL,
                                                   config.CDATA_ACCESS_TOKEN)
                mcli_toolkit.initialize()
            except Exception as e:
                print(f"  WARN: toolkit fetch failed ({e}); falling back to synthetic dispatch")
        with open(fixtures_path, "w") as f:
            json.dump({"global": global_tools, "workspace": workspace_tools,
                       "toolkit": toolkit_tools}, f, indent=2)
        print(f"  Cached tool fixtures to {fixtures_path}")

    # ---- Build dispatcher + scenarios ----------------------------------------
    global_names    = {t["name"] for t in global_tools}
    workspace_names = {t["name"] for t in workspace_tools}
    toolkit_names   = {t["name"] for t in toolkit_tools}
    dispatcher = make_dispatcher(
        mcli_global, mcli_workspace, mcli_toolkit,
        global_names, workspace_names, toolkit_names,
    )

    scenario_list = scenarios.build_scenarios(global_tools, workspace_tools, toolkit_tools)

    print()
    print(f"  Running {len(scenario_list)} scenarios...")
    print("-" * 64)

    r = runner.Runner(config.ANTHROPIC_API_KEY, config.MODEL)
    results = []
    for i, s in enumerate(scenario_list):
        print(f"  [{s['brief_section']}] {s['name']} - {s['summary']}")
        res = r.run_scenario(s, runs=args.runs, full=args.full,
                             tool_dispatcher=dispatcher)
        if res.error:
            print(f"      ERROR: {res.error}")
        else:
            print(f"      input={res.input_tokens:,}  output={res.output_tokens:,}  "
                  f"total={res.total_tokens:,}  calls={res.tool_calls}")
        results.append(res)
        # Brief cooldown between scenarios to keep rate limits happy
        if args.full and i < len(scenario_list) - 1:
            time.sleep(5)

    # ---- Write + render ------------------------------------------------------
    print()
    print("=" * 64)
    print("  RESULTS")
    print("=" * 64)
    paths = reporter.write_all(results, config.OUTPUT_DIR)

    if not args.no_charts:
        rows = _build_rows(results)
        chart_paths = charts.render_all(
            rows, config.OUTPUT_DIR,
            baseline_tool_count=len(global_tools),
            optimized_tool_count=len(workspace_tools) or 1,
        )
        paths.update(chart_paths)

    print()
    print("  Wrote:")
    for k, v in paths.items():
        print(f"    {k:>10}: {v}")
    print()
    print(f"  Anchor pricing: {config.PRICING['model_label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
