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
    tie = [0, 0]
    for it in card["items"]:
        t = int(it["fixture"].split("-")[0][4:])
        c = 1 if it["status"] == "scored" and it["layer0_1"]["correct"] else 0
        per[t][0] += 1
        per[t][1] += c
        if it["layer0_1"].get("gt_tie"):
            tie[0] += 1
            tie[1] += c
    terms = sorted(per)
    n = [per[t][0] for t in terms]
    acc = [per[t][1] / per[t][0] * 100 for t in terms]
    total = sum(n)
    overall = sum(per[t][1] for t in terms) / total * 100
    tie_acc = tie[1] / tie[0] * 100 if tie[0] else 0.0

    fig, ax = plt.subplots(figsize=(11.5, 6.0))
    xs = range(len(terms))
    ax.bar(xs, acc, width=0.66, color="#3b6ea5", zorder=3)
    ax.axhline(MAJORITY * 100, color="#c0392b", ls="--", lw=1.8, zorder=5)
    ax.axhline(RANDOM * 100, color="#555f63", ls=":", lw=1.8, zorder=5)
    # baseline labels live in a legend below the axes — never over the data
    ax.legend(handles=[
        plt.Line2D([], [], ls="--", color="#c0392b", lw=1.6),
        plt.Line2D([], [], ls=":", color="#7f8c8d", lw=1.6),
    ], labels=["Always predict the most common result: 61.1%",
               "Random guessing: 49.8%"],
        loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2, frameon=False,
        fontsize=9)
    for x, a, cnt in zip(xs, acc, n):
        ax.text(x, a + 0.35, f"{a:.1f}", ha="center", fontsize=10, fontweight="bold")
        ax.text(x, 2.5, f"n={cnt:,}", ha="center", fontsize=7.5,
                color="white", fontweight="bold", zorder=4)
    ax.set_xlim(-0.55, len(terms) - 0.45)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([f"term {t}\n{YEARS[t]}" for t in terms], fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_ylabel("winner accuracy (%)")
    fig.suptitle(f"Basal correctly identifies the winning side in "
                 f"{overall:.2f}% of {total:,} Sejm divisions",
                 fontsize=13.5, y=0.99)
    ax.set_title("Accuracy by parliamentary term · 1997–2026",
                 fontsize=10.5, color="#555555", pad=12)
    fig.subplots_adjust(top=0.85)
    ax.grid(axis="y", color="#dddddd", lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.text(0.5, -0.052,
             f"n = eligible voting divisions per term · Tie cases: {tie_acc:.1f}% "
             f"accuracy (n={tie[0]}) · baselines computed across all {total:,} divisions",
             ha="center", fontsize=8.5, color="#333333")
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(OUT)


if __name__ == "__main__":
    main()
