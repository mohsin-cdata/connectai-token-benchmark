"""HQ chart + Mermaid renderer in CData brand palette.

Brand colors:
  Depth   #15151C  text, axes, border
  Agility #FFE500  accent, baseline reference, highlights
  Resolve #002660  primary bars
  Balance #B5B9BC  grid, secondary bars
  BG      #F1EEE9  figure / axes background
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

import config

DEPTH    = "#15151C"
AGILITY  = "#FFE500"
RESOLVE  = "#002660"
BALANCE  = "#B5B9BC"
BG_COLOR = "#F1EEE9"

BORDER_PX     = 2      # outer figure border
DPI           = 300
WEBP_QUALITY  = 95
LABEL_PAD_PCT = 0.10   # 10% headroom above the tallest bar so value labels never overflow


FONT_TITLE  = 15
FONT_AXIS   = 12
FONT_TICK   = 11
FONT_LABEL  = 11
FONT_LEGEND = 11


def _setup_brand_axes(ax) -> None:
    ax.set_facecolor(BG_COLOR)
    for spine in ax.spines.values():
        spine.set_color(DEPTH)
        spine.set_linewidth(1.2)
    ax.tick_params(axis="both", colors=DEPTH, labelsize=FONT_TICK)
    ax.yaxis.label.set_color(DEPTH)
    ax.xaxis.label.set_color(DEPTH)
    ax.title.set_color(DEPTH)
    ax.grid(axis="y", linestyle="--", alpha=0.5, color=BALANCE)


def _setup_figure(figsize: Tuple[float, float]):
    fig, ax = plt.subplots(figsize=figsize, dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    fig.patch.set_edgecolor(DEPTH)
    fig.patch.set_linewidth(BORDER_PX)
    _setup_brand_axes(ax)
    return fig, ax


def _save(fig, out_path: str) -> str:
    out_path = out_path if out_path.endswith(".webp") else out_path.rsplit(".", 1)[0] + ".webp"
    fig.savefig(
        out_path,
        format="webp",
        dpi=DPI,
        facecolor=BG_COLOR,
        edgecolor=DEPTH,
        bbox_inches="tight",
        pad_inches=0.30,
        pil_kwargs={"quality": WEBP_QUALITY, "method": 6},
    )
    plt.close(fig)
    return out_path


def _short(name: str) -> str:
    return name.split(" (")[0]


def _wrap(label: str, max_chars: int = 14) -> str:
    """Insert newline so x-axis labels don't squish."""
    if len(label) <= max_chars:
        return label
    parts = label.split(" ")
    out = ""
    line = ""
    for w in parts:
        if len(line) + 1 + len(w) > max_chars and line:
            out += line + "\n"
            line = w
        else:
            line = (line + " " + w).strip()
    out += line
    return out


def chart_tokens(rows: List[Dict[str, Any]], out_path: str) -> str:
    labels = [_wrap(_short(r["feature"])) for r in rows]
    inputs  = [r["input"]  for r in rows]
    outputs = [r["output"] for r in rows]
    x = np.arange(len(labels))
    w = 0.4

    fig, ax = _setup_figure((12.5, 6.0))
    bars_in  = ax.bar(x - w/2, inputs,  w, label="Input tokens",
                      color=RESOLVE, edgecolor=DEPTH, linewidth=0.6)
    bars_out = ax.bar(x + w/2, outputs, w, label="Output tokens",
                      color=AGILITY, edgecolor=DEPTH, linewidth=0.6)

    ymax = max(max(inputs, default=0), max(outputs, default=0))
    ax.set_ylim(0, ymax * (1.0 + LABEL_PAD_PCT))

    for i, val in enumerate(inputs):
        if val > 0:
            ax.text(i - w/2, val, f"{val:,}", ha="center", va="bottom",
                    fontsize=FONT_LABEL, color=DEPTH, fontweight="bold")
    for i, val in enumerate(outputs):
        if val > 0:
            ax.text(i + w/2, val, f"{val:,}", ha="center", va="bottom",
                    fontsize=FONT_LABEL, color=DEPTH, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=FONT_TICK, color=DEPTH)
    ax.set_ylabel("Tokens per query", color=DEPTH, fontsize=FONT_AXIS)
    ax.set_title("Tokens per query - input vs output  (lower is better)",
                 color=DEPTH, fontsize=FONT_TITLE, fontweight="bold", pad=16)
    ax.legend(facecolor=BG_COLOR, edgecolor=DEPTH, labelcolor=DEPTH,
              loc="upper right", fontsize=FONT_LEGEND)
    fig.tight_layout()
    return _save(fig, out_path)


def chart_reduction(rows: List[Dict[str, Any]], out_path: str) -> str:
    feature_rows = [r for r in rows[1:] if r["reduction_pct"] != 0]
    feature_rows.sort(key=lambda r: r["reduction_pct"])
    labels = [_short(r["feature"]) for r in feature_rows]
    values = [r["reduction_pct"] for r in feature_rows]

    fig, ax = _setup_figure((11.0, 0.55 * max(len(labels), 1) + 1.8))
    bars = ax.barh(labels, values, color=RESOLVE, edgecolor=DEPTH, linewidth=0.6)
    xmax = max(values, default=100)
    ax.set_xlim(0, xmax * (1.0 + 0.12))

    for bar, v in zip(bars, values):
        ax.text(v + xmax * 0.01, bar.get_y() + bar.get_height()/2,
                f"{v:.1f}%", va="center", fontsize=FONT_LABEL+1, color=DEPTH, fontweight="bold")

    ax.set_xlabel("Total token reduction vs Raw baseline (%)", color=DEPTH, fontsize=FONT_AXIS)
    ax.set_title("Token reduction by Connect AI feature",
                 color=DEPTH, fontsize=FONT_TITLE, fontweight="bold", pad=16)
    ax.tick_params(axis="y", labelsize=FONT_TICK+1)
    ax.grid(axis="x", linestyle="--", alpha=0.5, color=BALANCE)
    fig.tight_layout()
    return _save(fig, out_path)


def chart_cost_saved(rows: List[Dict[str, Any]], out_path: str) -> str:
    feature_rows = [r for r in rows[1:] if r["saving_query"] > 0]
    labels = [_wrap(_short(r["feature"])) for r in feature_rows]
    volumes = config.PROJECTION_VOLUMES
    x = np.arange(len(labels))
    w = 0.8 / max(len(volumes), 1)

    fig, ax = _setup_figure((12.5, 6.0))
    palette = [BALANCE, RESOLVE, DEPTH, AGILITY]
    for i, vol in enumerate(volumes):
        vals = [r["monthly"].get(vol, 0.0) for r in feature_rows]
        ax.bar(x + (i - (len(volumes)-1)/2) * w, vals, w,
               label=f"{vol:,} queries / mo",
               color=palette[i % len(palette)], edgecolor=DEPTH, linewidth=0.4)

    all_vals = [v for r in feature_rows for v in r["monthly"].values()]
    ymax = max(all_vals, default=0)
    ax.set_ylim(0, ymax * (1.0 + LABEL_PAD_PCT))

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=FONT_TICK, color=DEPTH)
    ax.set_ylabel("Monthly savings (USD)", color=DEPTH, fontsize=FONT_AXIS)
    ax.set_title(f"Estimated monthly $ saved per feature  ({config.PRICING['model_label']})",
                 color=DEPTH, fontsize=FONT_TITLE, fontweight="bold", pad=16)
    ax.legend(facecolor=BG_COLOR, edgecolor=DEPTH, labelcolor=DEPTH,
              loc="upper left", fontsize=FONT_LEGEND)
    fig.tight_layout()
    return _save(fig, out_path)


def chart_waterfall(rows: List[Dict[str, Any]], out_path: str) -> str:
    if not rows:
        return out_path
    baseline = rows[0]["total"]
    feature_rows = [r for r in rows[1:] if r["total"] > 0 and not r.get("error")]
    if not feature_rows:
        return out_path

    labels = ["Raw\nbaseline"] + [_wrap(_short(r["feature"])) for r in feature_rows]
    totals = [baseline] + [r["total"] for r in feature_rows]
    colors = [BALANCE] + [RESOLVE] * len(feature_rows)

    fig, ax = _setup_figure((12.5, 6.0))
    bars = ax.bar(labels, totals, color=colors, edgecolor=DEPTH, linewidth=0.8)

    ymax = max(totals)
    ax.set_ylim(0, ymax * (1.0 + LABEL_PAD_PCT))

    for bar, v in zip(bars, totals):
        ax.text(bar.get_x() + bar.get_width()/2, v, f"{v:,}",
                ha="center", va="bottom", fontsize=FONT_LABEL, color=DEPTH, fontweight="bold")

    ax.axhline(baseline, linestyle="--", color=AGILITY, linewidth=2.0,
               label=f"Raw baseline = {baseline:,}", alpha=0.95)
    ax.set_ylabel("Total tokens per query", color=DEPTH, fontsize=FONT_AXIS)
    ax.set_title("Total tokens per query - Raw baseline vs each Connect AI feature",
                 color=DEPTH, fontsize=FONT_TITLE, fontweight="bold", pad=16)
    ax.legend(facecolor=BG_COLOR, edgecolor=DEPTH, labelcolor=DEPTH,
              loc="upper right", fontsize=FONT_LEGEND)
    fig.tight_layout()
    return _save(fig, out_path)


# ---- Mermaid ---------------------------------------------------------------

MERMAID_TEMPLATE = """---
title: "How Connect AI cuts Claude token usage - {reduction_pct} fewer tokens, {calls_saved} fewer tool calls"
---
%%{{init: {{
  "theme": "base",
  "themeVariables": {{
    "background": "{bg}",
    "primaryColor": "{resolve}",
    "primaryTextColor": "{bg}",
    "primaryBorderColor": "{depth}",
    "lineColor": "{depth}",
    "secondaryColor": "{agility}",
    "tertiaryColor": "{balance}",
    "fontFamily": "Inter, Arial, sans-serif",
    "fontSize": "18px"
  }},
  "flowchart": {{
    "nodeSpacing": 50,
    "rankSpacing": 60,
    "padding": 16
  }}
}}}}%%
flowchart TB
    subgraph RAW["RAW BASELINE  -  {baseline_total} tokens  -  {baseline_calls} tool calls  -  ${baseline_cost}/query"]
        direction LR
        BU[User asks question]:::userBox
        BC[Claude]:::claudeBox
        BD["Discovery chain<br/>getCatalogs<br/>+ getInstructions x3<br/>+ getSchemas x3<br/>+ getTables x3<br/>+ getColumns x3"]:::costBox
        BQ["3 separate queryData calls<br/>ServiceNow + Salesforce + Snowflake"]:::costBox
        BA[Synthesise + answer]:::costBox
        BU --> BC
        BC -->|"loads {baseline_tools} universal tool defs"| BD
        BD --> BQ
        BQ --> BA
    end

    subgraph OPT["OPTIMIZED  -  {optimized_total} tokens  -  {optimized_calls} tool call  -  ${optimized_cost}/query"]
        direction LR
        OU[User asks question]:::userBox
        OC[Claude]:::claudeBox
        OQ["get_incidents Custom Tool<br/>Workspace + Custom Tool combo"]:::savedBox
        OA[Answer]:::savedBox
        OU --> OC
        OC -->|"loads 1 scoped tool def"| OQ
        OQ --> OA
    end

    RAW ~~~ OPT

    classDef userBox       fill:{resolve},stroke:{depth},stroke-width:2px,color:{bg},font-weight:bold;
    classDef claudeBox     fill:{resolve},stroke:{depth},stroke-width:2px,color:{bg},font-weight:bold;
    classDef costBox       fill:{balance},stroke:{depth},stroke-width:1.5px,color:{depth};
    classDef savedBox      fill:{agility},stroke:{depth},stroke-width:2px,color:{depth},font-weight:bold;
"""


def write_mermaid_source(rows: List[Dict[str, Any]], out_path: str,
                         baseline_tool_count: int, optimized_tool_count: int) -> str:
    baseline_total = rows[0]["total"] if rows else 0
    baseline_calls = rows[0]["tool_calls"] if rows else 0
    baseline_cost  = rows[0]["cost_query"] if rows else 0
    custom = next((r for r in rows if "Custom Tools" in r["feature"]), None)
    optimized_total = custom["total"] if custom else (rows[-1]["total"] if rows else 0)
    optimized_calls = custom["tool_calls"] if custom else 1
    optimized_cost  = custom["cost_query"] if custom else 0
    reduction = (baseline_total - optimized_total) / baseline_total * 100 if baseline_total else 0
    diagram = MERMAID_TEMPLATE.format(
        bg=BG_COLOR, depth=DEPTH, resolve=RESOLVE, agility=AGILITY, balance=BALANCE,
        baseline_total=f"{baseline_total:,}",
        optimized_total=f"{optimized_total:,}",
        baseline_tools=baseline_tool_count,
        optimized_tools=optimized_tool_count,
        baseline_calls=baseline_calls,
        optimized_calls=optimized_calls,
        baseline_cost=f"{baseline_cost:.4f}",
        optimized_cost=f"{optimized_cost:.4f}",
        reduction_pct=f"{reduction:.1f}%",
        calls_saved=baseline_calls - optimized_calls,
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(diagram)
    return out_path


def render_mermaid_image(mmd_path: str, out_webp_path: str,
                         width: int = 1600, height: int = 900,
                         css_file: str = "") -> str:
    """Render .mmd to .webp via mermaid-cli (npx -y @mermaid-js/mermaid-cli).

    Optional css_file injects a custom CSS file via mermaid-cli's --cssFile
    flag -- useful for @font-face declarations that point at bundled TTFs.

    Falls back to leaving only the .mmd source if mermaid-cli isn't installed.
    """
    if not shutil.which("npx") and not shutil.which("npx.cmd"):
        print("    skip: npx not on PATH; mermaid render not produced")
        return ""

    png_path = out_webp_path.replace(".webp", ".png")
    cfg_path = mmd_path + ".cfg.json"
    config_obj = {
        "theme": "base",
        "themeVariables": {
            "background":         BG_COLOR,
            "primaryColor":       RESOLVE,
            "primaryTextColor":   BG_COLOR,
            "primaryBorderColor": DEPTH,
            "lineColor":          DEPTH,
            "secondaryColor":     AGILITY,
            "tertiaryColor":      BALANCE,
            "fontFamily":         "Inter, Arial, sans-serif",
        },
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(config_obj, f, indent=2)

    cmd = [
        "npx.cmd" if os.name == "nt" else "npx", "-y", "@mermaid-js/mermaid-cli",
        "-i", mmd_path,
        "-o", png_path,
        "-b", BG_COLOR,
        "-w", str(width),
        "-H", str(height),
        "-c", cfg_path,
    ]
    if css_file and os.path.exists(css_file):
        cmd.extend(["-C", css_file])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception as e:
        print(f"    mermaid-cli failed: {e}")
        return ""
    if result.returncode != 0:
        print(f"    mermaid-cli stderr: {result.stderr[:400]}")
        return ""

    if os.path.exists(png_path):
        try:
            from PIL import Image
            img = Image.open(png_path).convert("RGB")
            img.save(out_webp_path, format="webp", quality=WEBP_QUALITY, method=6)
            return out_webp_path
        except Exception as e:
            print(f"    PNG->WebP convert failed: {e}; keeping PNG")
            return png_path
    return ""


def render_all(rows: List[Dict[str, Any]], out_dir: str,
               baseline_tool_count: int, optimized_tool_count: int) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = {
        "tokens":    chart_tokens(rows,        os.path.join(out_dir, "chart-tokens.webp")),
        "reduction": chart_reduction(rows,     os.path.join(out_dir, "chart-reduction.webp")),
        "cost":      chart_cost_saved(rows,    os.path.join(out_dir, "chart-cost.webp")),
        "waterfall": chart_waterfall(rows,     os.path.join(out_dir, "chart-waterfall.webp")),
    }
    mmd_path = write_mermaid_source(rows, os.path.join(out_dir, "token-flow.mmd"),
                                    baseline_tool_count, optimized_tool_count)
    paths["mermaid_src"] = mmd_path
    img_path = render_mermaid_image(mmd_path, os.path.join(out_dir, "token-flow.webp"))
    if img_path:
        paths["mermaid_img"] = img_path
    return paths
