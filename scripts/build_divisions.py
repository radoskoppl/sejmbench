#!/usr/bin/env python3
"""Rebuild divisions (one row per voting, per-MP votes embedded) from a dump.

Input: the dump written by dump_sejm_hf.py — votings.jsonl (per-division
metadata) and votes.jsonl (one row per MP vote, ordered by division).
Output: one JSON line per division with its vote records embedded — the
format consumed by the backtest scripts. No API access needed: the dump is
the source of truth.
"""
import argparse
import gzip
import json
import os


def open_out(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "wt", encoding="utf-8")
    return open(path, "w", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--terms", default="",
                    help="comma-separated term numbers (default: all)")
    ap.add_argument("--dump", default="dump",
                    help="dump directory with votings.jsonl and votes.jsonl")
    ap.add_argument("--out", default="divisions.jsonl",
                    help="output path; .gz suffix enables compression")
    args = ap.parse_args()

    terms = {int(x) for x in args.terms.split(",") if x.strip()}

    meta = {}
    with open(os.path.join(args.dump, "votings.jsonl"), encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if terms and d["term"] not in terms:
                continue
            meta[(d["term"], d["sitting"], d["votingNumber"])] = {
                "date": d.get("date"), "title": d.get("title"),
                "topic": d.get("topic"), "description": d.get("description"),
            }
    print(f"meta index: {len(meta)} divisions", flush=True)

    out = open_out(args.out)
    stats: dict[int, int] = {}
    cur = None
    buf: list = []

    def flush() -> None:
        nonlocal cur, buf
        if cur is None or not buf:
            return
        m = meta.get(cur, {})
        out.write(json.dumps({
            "term": cur[0], "sitting": cur[1], "votingNumber": cur[2],
            "date": m.get("date"), "title": m.get("title"),
            "topic": m.get("topic"), "description": m.get("description"),
            "votes": buf,
        }, ensure_ascii=False) + "\n")
        stats[cur[0]] = stats.get(cur[0], 0) + 1
        buf = []

    with open(os.path.join(args.dump, "votes.jsonl"), encoding="utf-8") as f:
        for line in f:
            if terms and not any(f'"term": {t},' in line for t in terms):
                continue
            d = json.loads(line)
            k = (d["term"], d["sitting"], d["votingNumber"])
            if cur is not None and k != cur:
                flush()
            cur = k
            buf.append({"club": d.get("club"), "vote": d.get("vote")})
    flush()
    out.close()
    print("divisions per term:", dict(sorted(stats.items())), flush=True)
    print(f"output: {args.out}", flush=True)


if __name__ == "__main__":
    main()
