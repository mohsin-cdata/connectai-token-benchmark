"""Render the simple two-path token-flow diagram via matplotlib.

Why matplotlib instead of mermaid-cli for this one figure: puppeteer's
sandboxed Chromium does not reliably pick up custom or system-installed
fonts, even when fonts are base64-embedded into the CSS. Matplotlib reads
the TTFs directly via FontProperties(fname=...) so the output is
deterministic across machines.

Aspect ratio is intentionally tight (~1.55:1) so the diagram fills the KB
article column at readable size rather than scaling down to nothing.

Outputs:
  output/token-flow-simple.png
  output/token-flow-simple.webp
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from PIL import Image

# ---- Fonts (from the project's bundled TTFs) ----
_FONTS_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "connectai-token-benchmark", "fonts"))
_FP_REG  = os.path.join(_FONTS_DIR, "DMSans-Regular.ttf")
_FP_BOLD = os.path.join(_FONTS_DIR, "DMSans-Bold.ttf")
_FP_MED  = os.path.join(_FONTS_DIR, "DMSans-Medium.ttf")
for f in (_FP_REG, _FP_BOLD, _FP_MED):
    if os.path.exists(f):
        fm.fontManager.addfont(f)
DM_REG   = fm.FontProperties(fname=_FP_REG)  if os.path.exists(_FP_REG)  else None
DM_MED   = fm.FontProperties(fname=_FP_MED)  if os.path.exists(_FP_MED)  else None
DM_BOLD  = fm.FontProperties(fname=_FP_BOLD) if os.path.exists(_FP_BOLD) else None

# ---- Palette ----
BG    = "#F1EEE9"
NAVY  = "#002660"
INK   = "#15151C"
WHITE = "#FFFFFF"

# ---- Figure ----
FIG_W_IN = 10.0
FIG_H_IN = 6.5
DPI      = 200

# ---- Nodes in 100-unit coord space ----
# y_top / y_mid / y_bot
Y_TOP, Y_MID, Y_BOT = 78, 50, 22

NODES = [
    # id   label                            sub                     cx   cy     w    h   style
    ("U",  "Same user question",           None,                    10, Y_MID, 18, 14, "mono"),
    ("C",  "Claude",                       None,                    32, Y_MID, 14, 14, "mono"),
    ("D",  "Discovery chain",              "183K tokens · 22 calls", 62, Y_TOP, 26, 18, "tool"),
    ("A1", "Answer",                       None,                    91, Y_TOP, 14, 14, "mono"),
    ("T",  "get_incidents Custom Tool",    "4.4K tokens · 1 call",   62, Y_BOT, 30, 18, "tool"),
    ("A2", "Answer",                       None,                    91, Y_BOT, 14, 14, "mono"),
]

EDGES = [
    # (from, to, label, style)
    ("U",  "C",  None,                            "solid"),
    ("C",  "D",  "Raw — 11 universal tools",     "solid"),
    ("D",  "A1", None,                            "solid"),
    ("C",  "T",  "Connect AI — 1 Custom Tool",   "dashed"),
    ("T",  "A2", None,                            "dashed"),
]


def _draw_node(ax, node):
    nid, label, sub, cx, cy, w, h, style = node
    if style == "tool":
        face, edge_color, text_color = NAVY, INK, BG
        lw = 0.5
        font = DM_BOLD or DM_REG
    else:
        face, edge_color, text_color = WHITE, NAVY, INK
        lw = 1.6
        font = DM_MED or DM_REG
    x = cx - w / 2
    y = cy - h / 2
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.05,rounding_size=1.4",
        facecolor=face, edgecolor=edge_color, linewidth=lw, zorder=3,
    )
    ax.add_patch(box)
    if sub:
        ax.text(cx, cy + h * 0.16, label, ha="center", va="center",
                fontsize=13, color=text_color, fontproperties=font, zorder=4)
        ax.text(cx, cy - h * 0.22, sub, ha="center", va="center",
                fontsize=10.5, color=text_color, fontproperties=DM_REG, zorder=4)
    else:
        ax.text(cx, cy, label, ha="center", va="center",
                fontsize=12, color=text_color, fontproperties=font, zorder=4)
    return cx, cy, w, h


def _draw_edge(ax, nodes_by_id, from_id, to_id, label, style):
    fx, fy, fw, fh = nodes_by_id[from_id][2:]
    tx, ty, tw, th = nodes_by_id[to_id][2:]
    # right edge of from-node to left edge of to-node
    if tx > fx:
        x1, x2 = fx + fw / 2, tx - tw / 2
    else:
        x1, x2 = fx - fw / 2, tx + tw / 2
    y1, y2 = fy, ty
    linestyle = "--" if style == "dashed" else "-"
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>", mutation_scale=16,
        color=NAVY, lw=1.6, linestyle=linestyle, zorder=2,
        shrinkA=2, shrinkB=2,
    )
    ax.add_patch(arrow)
    if label:
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        # nudge the label slightly above the line for both branches so it
        # never overlaps the arrow head
        my += 2.2 if y2 > y1 else -2.2
        ax.text(mx, my, label, ha="center", va="center",
                fontsize=10, color=INK, fontproperties=DM_MED or DM_REG, zorder=5,
                bbox=dict(boxstyle="round,pad=0.3", facecolor=BG, edgecolor="none", alpha=0.95))


def render():
    os.makedirs("output", exist_ok=True)
    fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_position([0.01, 0.01, 0.98, 0.98])
    ax.set_xlim(0, 105)
    ax.set_ylim(8, 95)
    ax.axis("off")
    ax.set_aspect("auto")

    nodes_by_id = {}
    for n in NODES:
        cx, cy, w, h = _draw_node(ax, n)
        nodes_by_id[n[0]] = (n[1], n[2], cx, cy, w, h)
    for from_id, to_id, label, style in EDGES:
        _draw_edge(ax, nodes_by_id, from_id, to_id, label, style)

    png_path = "output/token-flow-simple.png"
    fig.savefig(png_path, dpi=DPI, facecolor=BG, edgecolor="none",
                bbox_inches=None, pad_inches=0)
    plt.close(fig)

    img = Image.open(png_path).convert("RGB")
    webp_path = "output/token-flow-simple.webp"
    img.save(webp_path, format="webp", quality=95, method=6)
    print(f"  {os.path.basename(png_path)}: {img.size[0]}x{img.size[1]} px")
    print(f"  {os.path.basename(webp_path)}: {img.size[0]}x{img.size[1]} px, "
          f"{os.path.getsize(webp_path)/1024:.0f} KB")


if __name__ == "__main__":
    render()
