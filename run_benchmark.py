"""Entry point for the Connect AI token-reduction benchmark.

Usage examples:
  python run_benchmark.py                    # input-only mode (free, count_tokens)
  python run_benchmark.py --full             # input + output via real inference
  python run_benchmark.py --full --runs 3    # average of 3 inference runs per scenario
  python run_benchmark.py --no-charts        # skip PNG/Mermaid generation
  python run_benchmark.py --skip-mcp         # use cached tools.json fixtures (offline)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

import config
from benchmark import charts, mcp_client, normalizer, reporter, runner, scenarios
from benchmark.reporter import _build_rows


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
                        help="Run full inference (input + output tokens). Costs cents.")
    parser.add_argument("--runs",      type=int, default=config.RUNS_PER_SCENARIO,
                        help="Inference runs per scenario for averaging.")
    parser.add_argument("--no-charts", action="store_true",
                        help="Skip matplotlib + Mermaid output.")
    parser.add_argument("--skip-mcp",  action="store_true",
                        help="Use cached tool list fixtures from output/_fixtures.json.")
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
    print(f"  Mode   : {'FULL (input + output)' if args.full else 'INPUT-ONLY (count_tokens)'}")
    print(f"  Runs   : {args.runs}")
    print("=" * 64)

    if args.skip_mcp and os.path.exists(fixtures_path):
        with open(fixtures_path) as f:
            cache = json.load(f)
        global_tools    = cache["global"]
        workspace_tools = cache["workspace"]
        toolkit_tools   = cache["toolkit"]
        print("  Loaded tool fixtures from output/_fixtures.json")
    else:
        global_tools    = fetch_tools(config.MCP_GLOBAL_URL,    "global")
        try:
            workspace_tools = fetch_tools(config.MCP_WORKSPACE_URL, "workspace")
        except Exception as e:
            print(f"  WARN: workspace fetch failed ({e}); using global as fallback")
            workspace_tools = global_tools
        try:
            toolkit_tools = fetch_tools(config.MCP_TOOLKIT_URL,   "toolkit")
        except Exception as e:
            print(f"  WARN: toolkit fetch failed ({e}); using global as fallback")
            toolkit_tools = global_tools
        with open(fixtures_path, "w") as f:
            json.dump({"global": global_tools, "workspace": workspace_tools,
                       "toolkit": toolkit_tools}, f, indent=2)
        print(f"  Cached tool fixtures to {fixtures_path}")

    scenario_list = scenarios.build_scenarios(global_tools, workspace_tools, toolkit_tools)

    print()
    print(f"  Running {len(scenario_list)} scenarios...")
    print("-" * 64)

    r = runner.Runner(config.ANTHROPIC_API_KEY, config.MODEL)
    results = []
    for s in scenario_list:
        print(f"  [{s['brief_section']}] {s['name']} - {s['summary']}")
        res = r.run_scenario(s, runs=args.runs, full=args.full)
        if res.error:
            print(f"      ERROR: {res.error}")
        else:
            print(f"      input={res.input_tokens:,}  output={res.output_tokens:,}  "
                  f"total={res.total_tokens:,}  calls={res.tool_calls}")
        results.append(res)

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
    print("  Cost saving math: per-query saving x volume.")
    print(f"  Anchor pricing:  {config.PRICING['model_label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
