"""Shared plot style, paths and the save() helper used by the notebooks (same style as the sibling repos)."""
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "outputs" / "figures"
TAB = ROOT / "outputs" / "tables"

SRC_WFP = "Source: WFP Bangladesh food prices via HDX (CC BY-IGO), retail, BDT nominal; author's calculations."
SRC_IDX = ("Source: WFP Bangladesh food prices via HDX (CC BY-IGO); FAOSTAT Consumer Price Indices (CC BY 4.0). "
           "Index weights are assumed quantities, see docs/DESIGN.md.")

BLUE, ORANGE, GREY, GREEN, RED = "#1f4e79", "#c55a11", "#7f7f7f", "#548235", "#a50021"
ITEM_LABEL = {"rice_coarse": "Rice (coarse)", "atta": "Wheat flour (atta)", "lentil_masur": "Lentils (masur)",
              "palm_oil": "Palm oil (L)", "soybean_oil": "Soybean oil (L)", "sugar": "Sugar",
              "egg": "Egg (piece)", "chicken_broiler": "Chicken, broiler", "onion": "Onion (imported)",
              "potato": "Potato", "chili_green": "Green chili"}


def set_style():
    plt.rcParams.update({
        "figure.dpi": 100, "savefig.dpi": 150, "font.size": 10,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3,
        "legend.frameon": False,
    })


def save(fig, name, note=SRC_WFP):
    fig.text(0.01, 0.005, note, fontsize=7.5, color="dimgray", ha="left", va="bottom", wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    path = FIG / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    return path
