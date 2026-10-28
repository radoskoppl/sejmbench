#!/usr/bin/env python3
"""Snapshot of bucket assignment for every distinct official description formula.

Generates docs/layer1-formula-buckets.json from docs/inventory-description.json
with the current layer-1 dictionary. Run with --check (used in CI) to compare
the regenerated snapshot against the committed file: any rule or dictionary
change that re-classifies a formula surfaces as a diff.

Plan (CODEBOOK section 10, "Frozen dictionary plan"): at freeze this table
becomes the exhaustive frozen dictionary; rules remain the proposer for new
formulas.
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)

from layer1_classify import classify, load_dictionary  # noqa: E402


def build():
    d = load_dictionary()
    inv = json.load(open(os.path.join(ROOT, "docs", "inventory-description.json"), encoding="utf-8"))
    return {
        "dictionary_version": d["version"],
        "formulas": [
            {"text": r["text"], "total": r["total"], "bucket": classify(r["text"], d)}
            for r in inv["formulas"]
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="compare the regenerated snapshot with the committed file")
    args = ap.parse_args()

    payload = build()
    path = os.path.join(ROOT, "docs", "layer1-formula-buckets.json")
    if args.check:
        committed = json.load(open(path, encoding="utf-8"))
        if committed == payload:
            print(f"OK layer1-formula-buckets.json matches dictionary {payload['dictionary_version']}")
            raise SystemExit(0)
        print("DRIFT: layer1-formula-buckets.json does not match the current dictionary")
        raise SystemExit(1)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    buckets = {}
    for f in payload["formulas"]:
        buckets[f["bucket"]] = buckets.get(f["bucket"], 0) + f["total"]
    print(f"snapshot written: {len(payload['formulas'])} formulas, dictionary {payload['dictionary_version']}")
    for k in sorted(buckets, key=lambda x: -buckets[x]):
        print(f"  {buckets[k]:6}  {k}")


if __name__ == "__main__":
    main()
