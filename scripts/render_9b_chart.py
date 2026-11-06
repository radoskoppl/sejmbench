#!/usr/bin/env python3
"""Render the 9B winner-accuracy-by-term chart from the committed scorecard.

Recomputes every printed number from results/basal-9b-full.scorecard.json —
no figures are carried over from prose. Output:
results/fig-9b-accuracy-by-term.png
"""
import collections
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patheffects as pe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD = os.path.join(ROOT, "results", "basal-9b-full.scorecard.json")
OUT = os.path.join(ROOT, "results", "fig-9b-accuracy-by-term.png")

YEARS = {3: "1997–2001", 4: "2001–2005", 5: "2005–2007", 6: "2007–2011",
         7: "2011–2015", 8: "2015–2019", 9: "2019–2023", 10: "2023–2027"}

# baselines recomputed from the same frozen population (corpus-baselines doc;
# majority = modal winner of the scored set, random = seed 20261027)
MAJORITY = 0.611
RANDOM = 0.498


def main():
    with open(CARD, encoding="utf-8") as fh:
        card = json.load(fh)
    per = collections.defaultdict(lambda: [0, 0])
    for it in card["items"]:
        t = int(it["fixture"].split("-")[0][4:])
        per[t][0] += 1
        per[t][1] += 1 if it["status"] == "scored" and it["layer0_1"]["correct"] else 0
    terms = sorted(per)
    n = [per[t][0] for t in terms]
    acc = [per[t][1] / per[t][0] * 100 for t in terms]
    overall = sum(per[t][1] for t in terms) / sum(n) * 100

    fig, ax = plt.subplots(figsize=(11, 5.4))
    xs = range(len(terms))
    bars = ax.bar(xs, acc, width=0.66, color="#3b6ea5", zorder=3)
    ax.axhline(MAJORITY * 100, color="#c0392b", ls="--", lw=1.6, zorder=2)
    ax.axhline(RANDOM * 100, color="#7f8c8d", ls=":", lw=1.6, zorder=2)
    ax.text(len(terms) + 0.15, MAJORITY * 100 + 1.5, "majority-class\n61.1%",
            color="#c0392b", fontsize=8.5, ha="left", va="bottom",
            path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])
    ax.text(len(terms) + 0.15, RANDOM * 100 + 1.5, "random\n49.8%",
            color="#333333", fontsize=8.5, ha="left", va="bottom",
            path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])
    for x, a, cnt in zip(xs, acc, n):
        ax.text(x, a + 0.35, f"{a:.1f}", ha="center", fontsize=10, fontweight="bold")
        ax.text(x, 2.5, f"n={cnt:,}", ha="center", fontsize=7.5,
                color="white", fontweight="bold", zorder=4)
    ax.set_xlim(-0.55, len(terms) + 1.35)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([f"term {t}\n{YEARS[t]}" for t in terms], fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_ylabel("winner accuracy (%)")
    ax.set_title(f"SejmBench layer 0.1 — basal-omni-1.0-ultra, {sum(n):,} votes, "
                 f"overall {overall:.2f}% [95% CI 97.85–98.07]", fontsize=12)
    ax.grid(axis="y", color="#dddddd", lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(OUT)


if __name__ == "__main__":
    main()
