#!/usr/bin/env python3
"""Build the precomputed ground truth for corpus-backed evaluation sets (issue #11).

Streams the divisions dump once, keeps only the frozen population ids, runs
seed_rule per division and writes gzipped JSONL:
    {"id": "term{T}-s{S}-v{V}", "metric": <seed_rule output>}

The uncompressed-stream sha256 is the `gt_sha256` bound into scorecards
(schema 1.2 `population` block). Rows are sorted by id so the hash is
reproducible regardless of dump order.

Usage (run on ATX where the dump lives):
    python3 scripts/build_corpus_gt.py --dump ~/sejm-dump
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import seed_rule  # noqa: E402

SETS = {
    "full": ("ids-full-corpus.txt", "gt-full.jsonl.gz"),
    "term10": ("ids-term10.txt", "gt-term10.jsonl.gz"),
}


def key_of(r):
    return (int(r["term"]), int(r["sitting"]), int(r["votingNumber"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.path.expanduser("~/sejm-dump"))
    args = ap.parse_args()

    pop_dir = os.path.join(ROOT, "docs", "population")
    div_path = os.path.join(args.dump, "divisions_3_10.jsonl")

    set_ids = {}
    for name, (ids_file, _) in SETS.items():
        ids = set()
        with open(os.path.join(pop_dir, ids_file), encoding="utf-8") as fh:
            for line in fh:
                t, s, v = line.strip().split(":")
                ids.add((int(t), int(s), int(v)))
        set_ids[name] = ids
    all_keys = set().union(*set_ids.values())

    rows: dict[str, dict] = {}
    with open(div_path, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            k = key_of(d)
            if k not in all_keys:
                continue
            m = seed_rule.compute_metric(d)
            item_id = f"term{k[0]}-s{k[1]}-v{k[2]}"
            if item_id in rows:
                raise SystemExit(f"duplicate division id in dump: {item_id}")
            rows[item_id] = m

    by_set: dict[str, list] = {name: [] for name in SETS}
    id_to_sets = {}
    for name, keys in set_ids.items():
        for t, s, v in keys:
            id_to_sets.setdefault(f"term{t}-s{s}-v{v}", set()).add(name)
    for item_id, m in rows.items():
        for name in id_to_sets[item_id]:
            by_set[name].append((item_id, m))

    summary = {}
    for name, (_, out_file) in SETS.items():
        entries = sorted(by_set[name])
        buf = io.BytesIO()
        h = hashlib.sha256()
        for item_id, m in entries:
            row = json.dumps({"id": item_id, "metric": m}, sort_keys=True,
                             ensure_ascii=False) + "\n"
            b = row.encode("utf-8")
            h.update(b)
            buf.write(b)
        with open(os.path.join(pop_dir, out_file), "wb") as fh:
            with gzip.GzipFile(fileobj=fh, mode="wb", filename="", mtime=0) as gz:
                gz.write(buf.getvalue())
        summary[name] = {"n": len(entries), "gt_sha256": h.hexdigest(),
                         "out": out_file}
        print(f"{name}: n={len(entries)} gt_sha256={h.hexdigest()}", file=sys.stderr)

    expected = {}
    for name, (ids_file, _) in SETS.items():
        ids_path = os.path.join(pop_dir, ids_file)
        n_ids = sum(1 for _ in open(ids_path, encoding="utf-8"))
        expected[name] = n_ids
        if summary[name]["n"] != n_ids:
            raise SystemExit(f"{name}: GT has {summary[name]['n']} rows, "
                             f"population list has {n_ids} — refusing to write")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
