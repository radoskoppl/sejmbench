#!/usr/bin/env python3
"""Inventory of official `description` strings across the Sejm mirror (#2 step 1).

Reads a votings JSONL (one JSON object per division) and tallies distinct
`description` values overall and per term. The output JSON is the input to the
frozen string->bucket dictionary in CODEBOOK.md (issue #2). Ground truth for
layer 1 comes only from these official strings; no third-party labels.

Usage:
  python3 inventory_descriptions.py --input ~/sejm-dump/votings.jsonl \
      --out docs/inventory-description.json
"""

import argparse
import collections
import datetime
import gzip
import hashlib
import json
import os


def open_maybe_gz(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def sha256_file(path, chunk=8 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="votings.jsonl (or .gz) from the mirror dump")
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args()

    total = 0
    with_desc = 0
    per_term_total = collections.Counter()
    formulas = collections.defaultdict(collections.Counter)  # text -> Counter(term)

    with open_maybe_gz(args.input) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            term = str(rec.get("term", "?"))
            desc = rec.get("description")
            total += 1
            per_term_total[term] += 1
            if isinstance(desc, str):
                text = desc.strip()
                if text and text != "-":
                    with_desc += 1
                    formulas[text][term] += 1

    rows = [
        {
            "text": text,
            "total": sum(counts.values()),
            "by_term": {t: counts[t] for t in sorted(counts, key=lambda x: (len(x), x))},
        }
        for text, counts in sorted(formulas.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
    ]

    payload = {
        "meta": {
            "source_file": os.path.basename(args.input),
            "source_sha256": sha256_file(args.input),
            "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "total_divisions": total,
            "with_description": with_desc,
            "without_description": total - with_desc,
            "distinct_formulas": len(rows),
            "per_term_total": {t: per_term_total[t] for t in sorted(per_term_total, key=lambda x: (len(x), x))},
        },
        "formulas": rows,
    }

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    print(f"total={total} with_description={with_desc} distinct_formulas={len(rows)}")
    print("top 15:")
    for row in rows[:15]:
        print(f"  {row['total']:7}  {row['text'][:90]}")


if __name__ == "__main__":
    main()
