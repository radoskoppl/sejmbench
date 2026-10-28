#!/usr/bin/env python3
"""Seeded validation sample for the layer-1 dictionary (#2).

The dictionary maps distinct official `description` formulas to buckets, so
the validation sample is drawn at the FORMULA level (one row per distinct
formula, no duplicates): every formula with >= 3 divisions in the mirror is
included, and the remaining slots are filled with a seeded random sample of
the long tail. The maintainer hand-codes each row twice, with a time gap;
agreement between the two codings and between code and hand coding is
reported (CODEBOOK section 10; maintainer coding is not independent
validation).
"""

import argparse
import csv
import json
import random


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True, help="docs/inventory-description.json")
    ap.add_argument("--out", required=True, help="output CSV path")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20261027)
    args = ap.parse_args()

    inv = json.load(open(args.inventory, encoding="utf-8"))
    rows = [(f["text"], f["total"]) for f in inv["formulas"]]
    head = [(t, c) for t, c in rows if c >= 3]
    tail = [(t, c) for t, c in rows if c < 3]

    rng = random.Random(args.seed)
    sample = list(head)
    if len(sample) < args.n:
        rng.shuffle(tail)
        sample.extend(tail[: args.n - len(sample)])

    sample.sort(key=lambda tc: (-tc[1], tc[0]))
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["description", "divisions"])
        for text, count in sample:
            w.writerow([text, count])

    print(f"head(count>=3)={len(head)} tail_pool={len(tail)} sampled_total={len(sample)} seed={args.seed}")


if __name__ == "__main__":
    main()
