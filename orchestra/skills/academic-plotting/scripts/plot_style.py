#!/usr/bin/env python3
"""Print or apply publication matplotlib rcParams."""
from __future__ import annotations

import argparse
import json

RCPARAMS = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "savefig.bbox": "tight",
    "figure.dpi": 300,
    "savefig.dpi": 300,
}

OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"]


def apply():
    import matplotlib.pyplot as plt
    plt.rcParams.update(RCPARAMS)
    return plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print-rcparams", action="store_true")
    ap.add_argument("--print-palette", action="store_true")
    args = ap.parse_args()
    if args.print_palette:
        print(json.dumps({"okabe_ito": OKABE_ITO}, indent=2))
    else:
        print(json.dumps(RCPARAMS, indent=2))


if __name__ == "__main__":
    main()
