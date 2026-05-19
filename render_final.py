"""Render final publication assets from LOCKED_RESULTS.

Reads LOCKED_RESULTS.py, builds reporter rows, generates:
  output/results.md            paste-ready blog table
  output/results.json          machine-readable
  output/chart-tokens.webp
  output/chart-reduction.webp
  output/chart-cost.webp
  output/chart-waterfall.webp
  output/token-flow.webp       (Mermaid render)
  output/token-flow.mmd        (Mermaid source)

No API calls. Pure rendering from locked numbers.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, ".")
import config
from LOCKED_RESULTS import LOCKED_ROWS, BASELINE_TOOL_COUNT, OPTIMIZED_TOOL_COUNT
from benchmark import charts, reporter
from benchmark.pricing import (
    cost_per_query, monthly_savings, reduction_pct, saving_per_query,
)


def build_reporter_rows():
    base = LOCKED_ROWS[0]
    rows = []
    for i, r in enumerate(LOCKED_ROWS):
        cost_q = cost_per_query(r["input"], r["output"])
        if i == 0:
            saving_q = 0.0
            red      = 0.0
        else:
            saving_q = saving_per_query(base["input"], base["output"], r["input"], r["output"])
            red      = reduction_pct(base["total"], r["total"])

        rows.append({
            "feature":      r["feature"],
            "section":      r["section"],
            "input":        r["input"],
            "output":       r["output"],
            "total":        r["total"],
            "tool_calls":   r["tool_calls"],
            "wall_s":       r.get("wall_s", 0),
            "runs":         r.get("runs", 1),
            "aggregation":  r.get("aggregation", "mean"),
            "variance_pct": r.get("variance_pct", 0),
            "reduction_pct":red,
            "cost_query":   cost_q,
            "saving_query": saving_q,
            "monthly":      {} if i == 0 else monthly_savings(saving_q),
            "method":       r.get("method", ""),
            "publish_note": r.get("publish_note", ""),
            "note":         "",
            "error":        None,
        })
    return rows


def write_results_md(rows, out_path):
    lines = []
    lines.append("# Connect AI Token Reduction Benchmark - Final Results")
    lines.append("")
    lines.append(f"- **Model:** `{config.MODEL}` ({config.PRICING['model_label']})")
    lines.append(f"- **Pricing:** ${config.PRICING['input_per_mtok']:.2f} / MTok input, "
                 f"${config.PRICING['output_per_mtok']:.2f} / MTok output (Claude Sonnet 4.6 list price, May 2026)")
    lines.append(f"- **Query:** {config.QUERY_NL}")
    lines.append("- **Methodology:** Each scenario measured across multiple independent runs "
                 "(4-16 per scenario) at temperature=0, max_tokens=1024, max_turns=6 (10 for Raw baseline). "
                 "Real multi-turn execution against live Connect AI MCP - the script fires Claude planning, "
                 "executes the resulting tool calls against the corresponding MCP endpoint, feeds tool_results "
                 "back, repeats until end_turn or max_turns. Median used for high-variance scenarios "
                 "(Raw baseline, Derived Views) where Claude's discovery path varies; mean used for "
                 "deterministic scenarios.")
    lines.append("")
    lines.append("## Headline table (paste-ready for the blog)")
    lines.append("")
    headers = ["Feature","§","Total tokens","Tool calls","Reduction","$ / query","$ / mo @1K",
               "$ / mo @10K","$ / mo @50K","$ / mo @100K","Runs","Aggregation","Variance"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        red = "—" if r["reduction_pct"] == 0 else f"{r['reduction_pct']:.1f}%"
        var = f"{r['variance_pct']:.1f}%"
        lines.append("| " + " | ".join([
            r["feature"],
            r["section"],
            f"{r['total']:,}",
            str(r["tool_calls"]),
            red,
            f"${r['cost_query']:.4f}",
            f"${r['monthly'].get(1_000, 0):.2f}",
            f"${r['monthly'].get(10_000, 0):.2f}",
            f"${r['monthly'].get(50_000, 0):.2f}",
            f"${r['monthly'].get(100_000, 0):.2f}",
            str(r["runs"]),
            r.get("aggregation", "mean"),
            var,
        ]) + " |")
    lines.append("")

    lines.append("## Full breakdown including input/output split")
    lines.append("")
    headers2 = ["Feature","§","Input","Output","Total","Calls","Wall (s)","Reduction","Cost/q","Var %","Runs"]
    lines.append("| " + " | ".join(headers2) + " |")
    lines.append("|" + "|".join(["---"] * len(headers2)) + "|")
    for r in rows:
        red = "—" if r["reduction_pct"] == 0 else f"{r['reduction_pct']:.1f}%"
        lines.append("| " + " | ".join([
            r["feature"], r["section"],
            f"{r['input']:,}", f"{r['output']:,}", f"{r['total']:,}",
            str(r["tool_calls"]),
            f"{r['wall_s']:.1f}",
            red,
            f"${r['cost_query']:.4f}",
            f"{r['variance_pct']:.1f}%",
            str(r["runs"]),
        ]) + " |")
    lines.append("")

    lines.append("## Methodology notes per scenario")
    lines.append("")
    for r in rows:
        lines.append(f"- **{r['feature']}** ({r['section']}): {r['method']}")
        if r.get("publish_note"):
            lines.append(f"   - *Note: {r['publish_note']}*")
    lines.append("")

    lines.append("## Summary takeaways")
    lines.append("")
    feature_rows = [r for r in rows if r["reduction_pct"] > 0]
    feature_rows.sort(key=lambda r: -r["reduction_pct"])
    if feature_rows:
        winner = feature_rows[0]
        lines.append(f"- **Strongest single feature: {winner['feature']} - {winner['reduction_pct']:.1f}% reduction.**")
        lines.append(f"  Drops cost from ${rows[0]['cost_query']:.3f}/query to "
                     f"${winner['cost_query']:.3f}/query - "
                     f"${winner['monthly'].get(10_000, 0):.0f}/mo saved at 10,000 queries, "
                     f"${winner['monthly'].get(100_000, 0):.0f}/mo at 100,000.")
    lines.append("- Cost saving math = (baseline cost/query - scenario cost/query) x monthly volume.")
    lines.append("- Batch (-50%) and prompt caching (-90% input) compound on top of the savings shown.")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_results_json(rows, out_path):
    import json
    payload = {
        "model":   config.MODEL,
        "pricing": config.PRICING,
        "query":   config.QUERY_NL,
        "rows":    rows,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main():
    rows = build_reporter_rows()
    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)

    print("Building publication-ready outputs from LOCKED_RESULTS...")
    print()

    md_path = os.path.join(out_dir, "results.md")
    write_results_md(rows, md_path)
    print(f"  results.md     -> {md_path}")

    json_path = os.path.join(out_dir, "results.json")
    write_results_json(rows, json_path)
    print(f"  results.json   -> {json_path}")

    print()
    print("Rendering charts (brand palette + 2px border + WebP HQ + bigger fonts)...")
    chart_paths = charts.render_all(
        rows, out_dir,
        baseline_tool_count=BASELINE_TOOL_COUNT,
        optimized_tool_count=OPTIMIZED_TOOL_COUNT,
    )
    for k, v in chart_paths.items():
        sz = os.path.getsize(v) if v and os.path.exists(v) else 0
        print(f"  {k:>12} -> {v}  ({sz/1024:.1f} KB)")
    print()
    print("Done. All publication assets in output/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
