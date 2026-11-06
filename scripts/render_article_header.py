#!/usr/bin/env python3
"""Render the article header image (5:2) for the SejmBench 9B article.

All numbers recomputed from results/basal-9b-full.scorecard.json.
Output: results/fig-article-header.png (5:2 aspect).
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
OUT = os.path.join(ROOT, "results", "fig-article-header.png")


def main():
    with open(CARD, encoding="utf-8") as fh:
        card = json.load(fh)
    per = collections.defaultdict(lambda: [0, 0])
    for it in card["items"]:
        t = int(it["fixture"].split("-")[0][4:])
        per[t][0] += 1
        per[t][1] += 1 if it["status"] == "scored" and it["layer0_1"]["correct"] else 0
    terms = sorted(per)
    acc = [per[t][1] / per[t][0] * 100 for t in terms]
    total = sum(per[t][0] for t in terms)
    overall = sum(per[t][1] for t in terms) / total * 100

    fig = plt.figure(figsize=(10, 4))  # 5:2 -> 2000x800 @ 200dpi
    # left text block
    fig.text(0.045, 0.66, "Basal wskazuje zwycięską stronę\nw %.2f%% głosowań imiennych Sejmu" % overall,
             fontsize=18.5, fontweight="bold", ha="left", va="center", linespacing=1.35)
    fig.text(0.045, 0.38, "SejmBench · %s głosowań · kadencje III–X (1997–2026)" % f"{total:,}",
             fontsize=12, color="#333333", ha="left", va="center")
    fig.text(0.045, 0.27, "poprzeczka: „typuj dominującą stronę” = 61.1%",
             fontsize=11, color="#c0392b", ha="left", va="center")
    fig.text(0.045, 0.10, "github.com/radoskoppl/sejmbench",
             fontsize=9.5, color="#555555", ha="left", va="center")
    # right decorative bars
    ax = fig.add_axes([0.70, 0.16, 0.27, 0.62])
    xs = range(len(terms))
    ax.bar(xs, acc, width=0.62, color="#3b6ea5", zorder=3)
    ax.axhline(61.1, color="#c0392b", ls="--", lw=1.4, zorder=5)
    ax.set_ylim(0, 105)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_title("trafność per kadencja (%)", fontsize=9, color="#555555", pad=6)
    for x, a in zip(xs, acc):
        ax.text(x, a + 2, f"{a:.1f}", ha="center", fontsize=6.5, color="#333333")
    ax.grid(axis="y", color="#e8e8e8", lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left", "bottom"):
        ax.spines[spine].set_visible(False)
    fig.savefig(OUT, dpi=200)
    print(OUT)


if __name__ == "__main__":
    main()
