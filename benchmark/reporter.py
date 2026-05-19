"""Render benchmark results as terminal table + JSON / CSV / Markdown exports."""
from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from typing import Any, Dict, List

from tabulate import tabulate

import config
from benchmark.pricing import (
    cost_per_query, monthly_savings, reduction_pct, saving_per_query,
)
from benchmark.runner import ScenarioResult


def _build_rows(results: List[ScenarioResult]) -> List[Dict[str, Any]]:
    if not results:
        return []
    baseline = results[0]
    rows: List[Dict[str, Any]] = []
    for r in results:
        if r.error:
            rows.append({
                "feature":     r.name,
                "section":     r.brief_section,
                "input":       0,
                "output":      0,
                "total":       0,
                "tool_calls":  0,
                "reduction_pct": 0.0,
                "cost_query":  0.0,
                "saving_query":0.0,
                "monthly":     {v: 0.0 for v in config.PROJECTION_VOLUMES},
                "note":        r.note or "",
                "error":       r.error,
            })
            continue

        if r.static_only:
            base_in  = r.baseline_input_tokens or 0
            opt_in   = r.input_tokens
            saving_q = saving_per_query(base_in, 0, opt_in, 0)
            rows.append({
                "feature":      r.name,
                "section":      r.brief_section,
                "input":        opt_in,
                "output":       0,
                "total":        opt_in,
                "tool_calls":   0,
                "reduction_pct": reduction_pct(base_in, opt_in),
                "cost_query":   cost_per_query(opt_in, 0),
                "saving_query": saving_q,
                "monthly":      monthly_savings(saving_q),
                "note":         r.note or f"Static count: full {base_in}-tok schema vs scoped {opt_in}-tok",
                "error":        None,
            })
            continue

        saving_q = saving_per_query(
            baseline.input_tokens, baseline.output_tokens,
            r.input_tokens, r.output_tokens,
        )
        rows.append({
            "feature":      r.name,
            "section":      r.brief_section,
            "input":        r.input_tokens,
            "output":       r.output_tokens,
            "total":        r.total_tokens,
            "tool_calls":   r.tool_calls,
            "reduction_pct": reduction_pct(baseline.total_tokens, r.total_tokens) if r is not baseline else 0.0,
            "cost_query":   cost_per_query(r.input_tokens, r.output_tokens),
            "saving_query": 0.0 if r is baseline else saving_q,
            "monthly":      {v: 0.0 for v in config.PROJECTION_VOLUMES} if r is baseline
                            else monthly_savings(saving_q),
            "note":         r.note or "",
            "error":        None,
        })
    return rows


def print_terminal(rows: List[Dict[str, Any]]) -> None:
    headers = ["Feature","§","Input","Output","Total","Calls","Reduction %",
               "$ / query","$ / mo @10K","$ / mo @100K"]
    table = []
    for r in rows:
        table.append([
            r["feature"],
            r["section"],
            f"{r['input']:>7,}",
            f"{r['output']:>7,}",
            f"{r['total']:>7,}",
            r["tool_calls"],
            f"{r['reduction_pct']:>6.1f}%",
            f"${r['cost_query']:.5f}",
            f"${r['monthly'].get(10_000, 0):.2f}",
            f"${r['monthly'].get(100_000, 0):.2f}",
        ])
    print(tabulate(table, headers=headers, tablefmt="github"))


def export_json(rows: List[Dict[str, Any]], raw: List[ScenarioResult], path: str) -> None:
    payload = {
        "model":   config.MODEL,
        "pricing": config.PRICING,
        "rows":    rows,
        "raw":     [asdict(r) for r in raw],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def export_csv(rows: List[Dict[str, Any]], path: str) -> None:
    if not rows:
        return
    fieldnames = ["feature","section","input","output","total","tool_calls","reduction_pct",
                  "cost_query","saving_query"] + [f"monthly_{v}" for v in config.PROJECTION_VOLUMES] + ["note"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row = {k: r.get(k) for k in ["feature","section","input","output","total","tool_calls",
                                         "reduction_pct","cost_query","saving_query","note"]}
            for v in config.PROJECTION_VOLUMES:
                row[f"monthly_{v}"] = r["monthly"].get(v, 0.0)
            w.writerow(row)


def export_markdown(rows: List[Dict[str, Any]], path: str) -> None:
    lines: List[str] = []
    lines.append("# Connect AI Token Reduction Benchmark Results")
    lines.append("")
    lines.append(f"- **Model:** `{config.MODEL}` ({config.PRICING['model_label']})")
    lines.append(f"- **Pricing:** ${config.PRICING['input_per_mtok']:.2f} / MTok input, "
                 f"${config.PRICING['output_per_mtok']:.2f} / MTok output")
    lines.append("- **Query:** " + config.QUERY_NL)
    lines.append("")
    lines.append("## Results")
    lines.append("")
    headers = ["Feature","§","Input","Output","Total","Calls","Reduction","$ / query saved",
               "$ / mo @1K","$ / mo @10K","$ / mo @50K","$ / mo @100K"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        lines.append("| " + " | ".join([
            r["feature"],
            r["section"],
            f"{r['input']:,}",
            f"{r['output']:,}",
            f"{r['total']:,}",
            str(r["tool_calls"]),
            f"{r['reduction_pct']:.1f}%",
            f"${r['saving_query']:.5f}",
            f"${r['monthly'].get(1_000, 0):.2f}",
            f"${r['monthly'].get(10_000, 0):.2f}",
            f"${r['monthly'].get(50_000, 0):.2f}",
            f"${r['monthly'].get(100_000, 0):.2f}",
        ]) + " |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for r in rows:
        if r.get("note"):
            lines.append(f"- **{r['feature']}** ({r['section']}): {r['note']}")
        if r.get("error"):
            lines.append(f"- **{r['feature']}** ERROR: {r['error']}")
    lines.append("")
    lines.append("Cost saving compares each row's `$ / query` against the Baseline row, then "
                 "multiplies by monthly volume. Batch (-50%) and prompt caching (-90% input) "
                 "compound on top.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def export_ledger(results: List[ScenarioResult], path: str) -> None:
    """Per-run JSONL ledger - one line per individual run across all scenarios.

    Append-only audit trail. Each line has: scenario, section, run_index,
    timestamp, token counts, tool_calls, stop_reason, wall_s. Recipients can
    grep / pipe / pandas-read this to inspect individual runs or to estimate
    variance themselves.
    """
    with open(path, "w", encoding="utf-8") as f:
        for r in results:
            if r.error or not r.inferences:
                continue
            for i, inf in enumerate(r.inferences, start=1):
                record = {
                    "scenario":   r.name,
                    "section":    r.brief_section,
                    "run_index":  i,
                    **inf,
                }
                f.write(json.dumps(record, default=str) + "\n")


def write_all(results: List[ScenarioResult], out_dir: str) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    rows = _build_rows(results)
    print_terminal(rows)
    paths = {
        "json":   os.path.join(out_dir, "results.json"),
        "csv":    os.path.join(out_dir, "results.csv"),
        "md":     os.path.join(out_dir, "results.md"),
        "ledger": os.path.join(out_dir, "run_ledger.jsonl"),
    }
    export_json(rows, results, paths["json"])
    export_csv(rows, paths["csv"])
    export_markdown(rows, paths["md"])
    export_ledger(results, paths["ledger"])
    return paths
