#!/usr/bin/env python3
"""Select the v0.3 stratified fixture set (issue #1) from the mirror dump.

Implements the frozen rule in CODEBOOK section 11: margin buckets (ordered),
type buckets from the layer-1 dictionary (`unknown` when no real formula),
allocation 2 anchors + 2 curated + 46 sampled, deterministic seeded sampling
(pass 1 type diversity, pass 2 term round-robin, seed 20261027).

Runs against a sejm-dump directory (default on ATX: ~/sejm-dump). Writes the
selection JSON to stdout (or --out). The output list is committed as
fixtures/selection.json; the frame file's sha256 is embedded as provenance.

Usage:
    python3 scripts/select_fixtures.py --dump ~/sejm-dump
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import layer1_classify  # noqa: E402

SEED = 20261027
TERMS = list(range(3, 11))

# Frozen allocation (CODEBOOK section 11): stratum -> sampled quota.
# Anchors (unanimous, comfortable) and curated cells (tie, election) are not
# sampled; the anchor slots are part of the stratum totals shown in the
# selection report, not produced here.
QUOTA = {"unanimous": 8, "edge": 10, "narrow": 10, "comfortable": 8, "landslide": 10}


def margin_bucket(yes: int, no: int) -> str:
    m = abs(yes - no)
    if yes == no:
        return "tie"  # includes 0:0
    if no == 0:
        return "unanimous"
    if m <= 5:
        return "edge"
    if m <= 20:
        return "narrow"
    if m <= 100:
        return "comfortable"
    return "landslide"


def type_bucket(description, dictionary) -> str:
    if description and str(description).strip() and str(description).strip() != "-":
        return layer1_classify.classify(description, dictionary)
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", required=True, help="sejm-dump directory containing votings.jsonl")
    ap.add_argument("--out", help="write the selection JSON to this path instead of stdout")
    args = ap.parse_args()

    votings_path = os.path.join(args.dump, "votings.jsonl")
    frame_sha = hashlib.sha256()
    n_rows = 0
    universe = 0
    zero_counter, inconsistent = [], []
    pools: dict[str, list] = {b: [] for b in QUOTA}
    pools["tie"] = []
    cell_counts: dict[tuple, int] = {}
    dictionary = layer1_classify.load_dictionary()

    with open(votings_path, encoding="utf-8") as fh:
        for line in fh:
            frame_sha.update(line.encode("utf-8"))
            r = json.loads(line)
            n_rows += 1
            yes, no, ab, tv = (r.get("yes", 0), r.get("no", 0),
                               r.get("abstain", 0), r.get("totalVoted", 0))
            if not (tv and yes + no + ab == tv):
                if tv == 0 and yes == no == ab == 0:
                    zero_counter.append(r)
                else:
                    inconsistent.append(r)
                continue
            if r.get("term") not in TERMS:
                continue
            universe += 1
            b = margin_bucket(yes, no)
            tb = type_bucket(r.get("description"), dictionary)
            cell_counts[(b, tb)] = cell_counts.get((b, tb), 0) + 1
            pools[b].append({
                "term": r["term"], "sitting": r["sitting"], "votingNumber": r["votingNumber"],
                "type": tb, "title": r.get("title", ""), "date": r.get("date"),
            })

    for pool in pools.values():
        pool.sort(key=lambda x: (x["term"], x["sitting"], x["votingNumber"]))
    zero_counter.sort(key=lambda r: (r["term"], r["sitting"], r["votingNumber"]))

    rng = random.Random(SEED)
    selected, notes = [], []

    # curated: one zero-counter election division (eligibility 0.1/0.2 = false)
    if zero_counter:
        e = zero_counter[rng.randrange(len(zero_counter))]
        selected.append({"term": e["term"], "sitting": e["sitting"], "votingNumber": e["votingNumber"],
                         "type": "election-zero-counter", "bucket": "election",
                         "selection": "curated", "title": e.get("title", ""), "date": e.get("date")})
    else:
        notes.append("election: empty cell - no zero-counter division in the frame")

    # curated: one eligible tie (yes == no, including 0:0)
    tie_pool = pools["tie"]
    if tie_pool:
        t = tie_pool[rng.randrange(len(tie_pool))]
        selected.append({**t, "bucket": "tie", "selection": "curated"})
    else:
        notes.append("tie: empty cell - no eligible yes==no division; slot reallocated to landslide")
        QUOTA["landslide"] = QUOTA["landslide"] + 1

    # sampled buckets: pass 1 type diversity, pass 2 term round-robin
    for bucket in ("unanimous", "edge", "narrow", "comfortable", "landslide"):
        quota = QUOTA[bucket]
        pool = pools[bucket]
        picked: set[int] = set()
        types = sorted({it["type"] for it in pool})
        pass1 = min(len(types), max(0, quota - 3))
        for ty in types[:pass1]:
            cands = [i for i, it in enumerate(pool) if it["type"] == ty and i not in picked]
            picked.add(cands[rng.randrange(len(cands))])
        rounds = 0
        while len(picked) < quota:
            term = TERMS[rounds % len(TERMS)]
            rounds += 1
            cands = [i for i, it in enumerate(pool) if it["term"] == term and i not in picked]
            if not cands:
                if all(not any(it["term"] == t2 for i, it in enumerate(pool) if i not in picked)
                       for t2 in TERMS):
                    break  # pool exhausted
                continue
            picked.add(cands[rng.randrange(len(cands))])
        for i in sorted(picked):
            selected.append({**pool[i], "bucket": bucket, "selection": "sampled"})

    selected.sort(key=lambda x: (x["term"], x["sitting"], x["votingNumber"]))
    out = {
        "seed": SEED,
        "codebook": "section 11 (strata frozen 2026-10-28, before sampling)",
        "frame": {
            "dump_dir": os.path.abspath(args.dump),
            "votings_rows": n_rows,
            "votings_sha256": frame_sha.hexdigest(),
            "universe_eligible": universe,
            "excluded_zero_counter": len(zero_counter),
            "excluded_inconsistent": len(inconsistent),
        },
        "cell_counts": {
            b: {
                "pool": sum(v for (bb, _), v in cell_counts.items() if bb == b),
                "by_type": {t: v for (bb, t), v in sorted(cell_counts.items()) if bb == b},
            } for b in ("tie", "unanimous", "edge", "narrow", "comfortable", "landslide")
        },
        "notes": notes,
        "selected": selected,
    }
    blob = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(blob)
        print(f"wrote {args.out} ({len(selected)} selected)")
    else:
        print(blob, end="")

    print(f"--- summary ---", file=sys.stderr)
    print(f"frame rows={n_rows} universe={universe} "
          f"zero_counter={len(zero_counter)} inconsistent={len(inconsistent)}", file=sys.stderr)
    for b in ("tie", "unanimous", "edge", "narrow", "comfortable", "landslide"):
        pool_n = sum(v for (bb, _), v in cell_counts.items() if bb == b)
        print(f"  {b:12s} pool={pool_n:6d} sampled={sum(1 for s in selected if s['bucket'] == b)}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
