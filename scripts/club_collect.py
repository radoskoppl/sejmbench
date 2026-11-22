#!/usr/bin/env python3
"""Collector for the SejmBench club-identity mapping (#1).

Streams a votes.jsonl dump (one row per MP vote:
{term, sitting, votingNumber, MP, club, firstName, lastName, secondName, vote})
and emits, per (term, club):
  - mp_ids        : sorted unique MP ids (MP id is unique within a term)
  - sittings      : [min, max] sitting number the label appeared at
  - n_divisions   : distinct (sitting, votingNumber) the label appears in
  - per_sitting   : {sitting: sorted unique MP ids}   (time-resolved overlap)
plus, per (term, sitting): the span of official dates from sittings.jsonl.

Provenance: sha256 + line count of the input dump is embedded in the output.

Usage (ATX): python3 club_collect.py ~/sejm-dump/votes.jsonl \
                 ~/sejm-dump/votings.jsonl docs/club-identity-membership.json.gz
"""
import gzip
import hashlib
import json
import sys
from collections import defaultdict

def main(votes_path, votings_path, out_path):
    # (term, sitting) -> sorted list of official voting timestamps; votings.jsonl
    # is the date source (one row per division, carries `date`).
    dates = defaultdict(list)
    with open(votings_path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            dates[(r["term"], r["sitting"])].append(r.get("date"))
    dates = {k: sorted(x for x in v if x) for k, v in dates.items()}

    membership = defaultdict(set)    # (term, club) -> MP ids
    label_sittings = defaultdict(set)  # (term, club) -> sittings
    divkeys = defaultdict(set)       # (term, club) -> {(sitting, votingNumber)}
    ts_membership = defaultdict(set) # (term, club, sitting) -> MP ids
    n_rows = 0
    n_no_club = 0
    h = hashlib.sha256()

    with open(votes_path, "rb") as f:
        for line in f:
            h.update(line)
            n_rows += 1
            if n_rows % 5_000_000 == 0:
                print(f"... {n_rows} rows", flush=True)
            r = json.loads(line)
            c = r.get("club")
            if not c:
                n_no_club += 1
                continue
            t = r["term"]; s = r["sitting"]; v = r["votingNumber"]
            key = (t, c)
            membership[key].add(r["MP"])
            label_sittings[key].add(s)
            divkeys[key].add((s, v))
            ts_membership[(t, c, s)].add(r["MP"])

    out = {
        "provenance": {
            "input": "votes.jsonl",
            "input_sha256": h.hexdigest(),
            "rows": n_rows,
            "rows_no_club": n_no_club,
            "date_source": "votings.jsonl",
        },
        "sitting_dates": {
            f"{t}:{s}": v for (t, s), v in sorted(dates.items())
        },
        "clubs": {},
    }
    for (t, c) in sorted(membership):
        ss = sorted(label_sittings[(t, c)])
        sd = sorted(dates.get((t, ss[0]), [None])[0:1] + dates.get((t, ss[-1]), [None])[-1:])
        out["clubs"][f"{t}|{c}"] = {
            "mp_ids": sorted(membership[(t, c)]),
            "sittings": [ss[0], ss[-1]],
            "n_divisions": len(divkeys[(t, c)]),
            "divisions": sorted(divkeys[(t, c)]),
            "first_date": next((d for s2 in ss for d in dates.get((t, s2), [])), None),
            "last_date": next(
                (d for s2 in reversed(ss) for d in reversed(dates.get((t, s2), []))), None
            ),
            "per_sitting": {
                str(s): sorted(ts_membership[(t, c, s)]) for s in ss
            },
        }

    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True)
    print(f"DONE rows={n_rows} no_club={n_no_club} labels={len(membership)} -> {out_path}", flush=True)

if __name__ == "__main__":
    main(*sys.argv[1:4])
