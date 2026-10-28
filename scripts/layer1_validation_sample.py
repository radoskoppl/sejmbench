#!/usr/bin/env python3
"""Seeded validation sample for the layer-1 dictionary (#2) - tuning + held-out test set.

The dictionary maps distinct official `description` formulas to buckets, so
the sample is drawn at the FORMULA level (one row per distinct formula, no
duplicates). Split:
  * tuning set: every formula with >= 3 divisions in the mirror (head) +
    seeded random fill of the tail to --tuning-n (default 200); hand-coded
    twice with a time gap.
  * held-out test set: --test-n (default 100) further seeded tail formulas,
    disjoint from the tuning set; scored only at dictionary freeze.
  * force-include: every bucket reaches --min-per-bucket formulas in the
    tuning set (rare buckets are not left to the random-fill lottery).

The maintainer hand-codes the tuning set twice; agreement between the two
codings and between code and hand coding is reported (CODEBOOK section 10;
maintainer coding is not independent validation).
"""

import argparse
import csv
import json
import os
import random
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", required=True, help="docs/inventory-description.json")
    ap.add_argument("--tuning-out", required=True, help="tuning CSV path (hand-coded)")
    ap.add_argument("--test-out", required=True, help="held-out test CSV path")
    ap.add_argument("--tuning-n", type=int, default=200)
    ap.add_argument("--test-n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20261027)
    ap.add_argument("--min-per-bucket", type=int, default=5,
                    help="force-include tail formulas so every bucket reaches this count in the tuning set")
    args = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from layer1_classify import classify, load_dictionary

    d = load_dictionary()
    inv = json.load(open(args.inventory, encoding="utf-8"))
    rows = [(f["text"], f["total"]) for f in inv["formulas"]]
    head = [(t, c) for t, c in rows if c >= 3]
    tail = [(t, c) for t, c in rows if c < 3]

    rng = random.Random(args.seed)
    rng.shuffle(tail)
    pools = {}
    for text, count in tail:
        pools.setdefault(classify(text, d), []).append((text, count))

    head_by = {}
    for text, _count in head:
        b = classify(text, d)
        head_by[b] = head_by.get(b, 0) + 1

    # force-include: every bucket reaches --min-per-bucket formulas in the
    # tuning set (rare buckets would otherwise be a lottery in the random fill)
    tuning = list(head)
    taken = set()
    for bucket in sorted(pools):
        need = max(0, args.min_per_bucket - head_by.get(bucket, 0))
        for text, count in pools[bucket][:need]:
            tuning.append((text, count))
            taken.add(text)

    remaining = [(t, c) for t, c in tail if t not in taken]
    fill = max(0, args.tuning_n - len(tuning))
    tuning.extend(remaining[:fill])
    test = remaining[fill:fill + args.test_n]

    def write(path, data):
        data = sorted(data, key=lambda tc: (-tc[1], tc[0]))
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["description", "divisions"])
            for text, count in data:
                w.writerow([text, count])

    write(args.tuning_out, tuning)
    write(args.test_out, test)
    by_bucket = {}
    for text, _count in tuning:
        b = classify(text, d)
        by_bucket[b] = by_bucket.get(b, 0) + 1
    print(f"head(count>=3)={len(head)} tail={len(tail)} tuning={len(tuning)} test={len(test)} seed={args.seed}")
    print("tuning per bucket:", dict(sorted(by_bucket.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
