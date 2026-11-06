#!/usr/bin/env python3
"""Temporal holdout split (issue #5): partition a frozen population by date.

The contamination policy (README, CODEBOOK section 9) makes a temporal holdout
the primary contamination control: divisions with an official sitting date
after a frozen cutoff are reported separately on every scorecard.

This script derives the post-cutoff ID list from artifacts that are already
committed (docs/population/gt-<set>.jsonl.gz carries each division's official
date in ``metric.fixture.date``), so the split is reproducible anywhere and
never needs the raw dump:

    python3 scripts/temporal_split.py --cutoff 2026-01-01 [--set full|term10]

Outputs (repo-relative):
    docs/population/ids-post-<cutoff>.txt           (set=full)
    docs/population/ids-post-<cutoff>-term10.txt    (set=term10)

The split auto-extends as new sittings are published: rerun after new dumps
and the post list grows by construction. A missing or unusable date is a hard
error - a silent fallback is how poisoned data happens (see issue #8).
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

IDS_FILES = {"full": "ids-full-corpus.txt", "term10": "ids-term10.txt"}
GT_FILES = {"full": "gt-full.jsonl.gz", "term10": "gt-term10.jsonl.gz"}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", required=True, help="frozen cutoff date, YYYY-MM-DD")
    ap.add_argument("--set", default="full", choices=sorted(IDS_FILES))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "docs", "population"))
    args = ap.parse_args()

    try:
        datetime.date.fromisoformat(args.cutoff)
    except ValueError:
        raise SystemExit(f"invalid cutoff date: {args.cutoff!r}")

    ids_path = os.path.join(args.out_dir, IDS_FILES[args.set])
    gt_path = os.path.join(args.out_dir, GT_FILES[args.set])

    population: list[tuple[int, int, int]] = []
    seen = set()
    with open(ids_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            t, s, v = line.split(":")
            k = (int(t), int(s), int(v))
            if k in seen:
                raise SystemExit(f"duplicate id in {IDS_FILES[args.set]}: {k}")
            seen.add(k)
            population.append(k)

    dates: dict[str, str | None] = {}
    with gzip.open(gt_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            dates[row["id"]] = row["metric"]["fixture"].get("date")

    missing = [k for k in population if f"term{k[0]}-s{k[1]}-v{k[2]}" not in dates]
    if missing:
        raise SystemExit(
            f"{len(missing)} population ids missing from {GT_FILES[args.set]} "
            f"(first: term{missing[0][0]}-s{missing[0][1]}-v{missing[0][2]}) - aborting, no silent fallback")
    pre: list[tuple[int, int, int]] = []
    post: list[tuple[int, int, int]] = []
    per_year: dict[str, int] = {}
    no_date: list[tuple[int, int, int]] = []
    for k in population:
        dv = dates[f"term{k[0]}-s{k[1]}-v{k[2]}"]
        if not dv:
            no_date.append(k)
            continue
        day = dv[:10]
        per_year[day[:4]] = per_year.get(day[:4], 0) + 1
        (post if day > args.cutoff else pre).append(k)
    if no_date:
        raise SystemExit(
            f"{len(no_date)} GT rows carry no official date "
            f"(first: term{no_date[0][0]}-s{no_date[0][1]}-v{no_date[0][2]}) - aborting, no silent fallback")

    post.sort()
    pre.sort()
    suffix = "" if args.set == "full" else f"-{args.set}"
    out_name = f"ids-post-{args.cutoff}{suffix}.txt"
    out_path = os.path.join(args.out_dir, out_name)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(f"{t}:{s}:{v}" for t, s, v in post) + "\n")

    per_term_post: dict[int, int] = {}
    for t, _, _ in post:
        per_term_post[t] = per_term_post.get(t, 0) + 1

    print(f"set={args.set} cutoff={args.cutoff}")
    print(f"population n={len(population)}  pre={len(pre)}  post={len(post)}")
    print(f"post by term: " + ", ".join(f"t{t}={n}" for t, n in sorted(per_term_post.items())))
    print("divisions per year: " + ", ".join(f"{y}={n}" for y, n in sorted(per_year.items())))
    print(f"wrote {out_name} sha256={sha256_file(out_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
