#!/usr/bin/env python3
"""Dump Sejm voting data (official API) into an HF-ready dataset.

Fetches every division (głosowanie) with its per-MP vote records from the
official Sejm API, stores immutable raw snapshots, and builds two JSONL
tables ready for Hugging Face:

  dump/votings.jsonl  one row per division (raw API fields + source_url)
  dump/votes.jsonl    one row per MP vote (term, sitting, votingNumber, vote)

Everything is resumable: raw snapshots are cached under dump/raw/ and skipped
on re-runs. manifest.json pins sha256 of the output files. Nothing derived
is added — raw API fields only (see CODEBOOK.md).

Usage:
  python3 scripts/dump_sejm_hf.py                          # discover terms 1..12, full dump
  python3 scripts/dump_sejm_hf.py --terms 9,10             # subset of terms
  python3 scripts/dump_sejm_hf.py --terms 10 --limit-sittings 2 --limit-votings 5   # smoke
  python3 scripts/dump_sejm_hf.py --push radoskoppl/sejm-votings   # needs:
      pip install datasets huggingface_hub  +  HF_TOKEN env (or --token)

License note: the source is official public data of the Chancellery of the
Sejm; the dataset rows carry source_url for one-click verification.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.sejm.gov.pl/sejm"
UA = "sejmbench-dump/0.1 (github.com/radoskoppl/sejmbench)"


def get_json(url: str, retries: int = 3):
    delay = 1.0
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(delay)
                delay *= 2
                last = e
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError(f"get_json: retries exhausted for {url}")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_terms(max_term: int = 12) -> list[int]:
    found = []
    for t in range(1, max_term + 1):
        try:
            get_json(f"{API}/term{t}/votings")
            found.append(t)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"  term{t}: HTTP {e.code} (skipping)")
        except Exception as e:  # noqa: BLE001
            print(f"  term{t}: {e} (skipping)")
    return found


VOTING_FIELDS = (
    "term", "sitting", "votingNumber", "date", "title", "topic", "description",
    "motion", "kind", "yes", "no", "abstain", "notParticipating", "present",
    "totalVoted", "majorityType", "majorityVotes", "votingOptions", "links",
)


def dump_terms(terms, out_dir, limit_sittings, limit_votings, sleep_s):
    raw_dir = os.path.join(out_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    votings_rows: list[dict] = []
    votes_rows: list[dict] = []
    stats = {"fetched": 0, "cached": 0, "missing": 0}
    per_term: dict[int, dict] = {}

    for term in terms:
        index = get_json(f"{API}/term{term}/votings")
        # index rows: {date, proceeding, votingsNum}; sitting number == proceeding
        sittings, seen = [], set()
        for row in index:
            p = row.get("proceeding")
            if p is None or p in seen:
                continue
            seen.add(p)
            sittings.append(row)
        if limit_sittings:
            sittings = sittings[:limit_sittings]

        tstats = {"sittings": 0, "votings": 0}
        for s in sittings:
            sitting = s["proceeding"]
            tdir = os.path.join(raw_dir, f"term{term}", f"sitting{sitting:03d}")
            os.makedirs(tdir, exist_ok=True)
            n = s.get("votingsNum", 0)
            if limit_votings:
                n = min(n, limit_votings)
            for vno in range(1, n + 1):
                fname = os.path.join(tdir, f"v{vno:03d}.json.gz")
                if os.path.exists(fname):
                    with gzip.open(fname, "rt", encoding="utf-8") as f:
                        detail = json.load(f)
                    stats["cached"] += 1
                else:
                    url = f"{API}/term{term}/votings/{sitting}/{vno}"
                    try:
                        detail = get_json(url)
                    except urllib.error.HTTPError as e:
                        if e.code == 404:
                            stats["missing"] += 1
                            print(f"  ! term{term} s{sitting} v{vno}: 404 (gap in API) — skipped")
                            continue
                        raise
                    with gzip.open(fname, "wt", encoding="utf-8") as f:
                        json.dump(detail, f, ensure_ascii=False)
                    stats["fetched"] += 1
                    time.sleep(sleep_s)

                source_url = f"https://api.sejm.gov.pl/sejm/term{term}/votings/{sitting}/{vno}"
                vrow = {k: detail.get(k) for k in VOTING_FIELDS}
                vrow["source_url"] = source_url
                votings_rows.append(vrow)

                votes = detail.get("votes")
                if isinstance(votes, list):
                    for rec in votes:
                        votes_rows.append({
                            "term": term,
                            "sitting": sitting,
                            "votingNumber": vno,
                            "MP": rec.get("MP"),
                            "club": rec.get("club"),
                            "firstName": rec.get("firstName"),
                            "lastName": rec.get("lastName"),
                            "secondName": rec.get("secondName"),
                            "vote": rec.get("vote"),
                        })
                else:
                    print(f"  ! term{term} s{sitting} v{vno}: votes is {type(votes).__name__} — vote rows skipped")
            tstats["sittings"] += 1
            tstats["votings"] += 1  # placeholder, corrected below
        # correct votings count: count raw files written for this term
        tstats["votings"] = sum(
            len(files) for root, _, files in os.walk(os.path.join(raw_dir, f"term{term}"))
        )
        per_term[term] = tstats
        print(f"term{term}: {tstats['sittings']} sittings, {tstats['votings']} divisions (raw files)")
    return votings_rows, votes_rows, stats, per_term


def write_jsonl(rows: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def build_manifest(out_dir: str, per_term: dict, stats: dict) -> dict:
    manifest = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "Official Sejm API (https://api.sejm.gov.pl) — Chancellery of the Sejm of the Republic of Poland",
        "api_base": API,
        "user_agent": UA,
        "terms": per_term,
        "fetch_stats": stats,
        "files": {},
    }
    for name in ("votings.jsonl", "votes.jsonl"):
        p = os.path.join(out_dir, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                rows = sum(1 for _ in f)
            manifest["files"][name] = {"sha256": sha256_file(p), "rows": rows}
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return manifest


def build_and_push(out_dir: str, repo_id: str, token: str | None, private: bool) -> None:
    try:
        from datasets import Dataset, DatasetDict  # type: ignore
    except ImportError as e:
        sys.exit(f"--push requires the datasets library: pip install datasets huggingface_hub ({e})")
    dd = DatasetDict({
        "votings": Dataset.from_json(os.path.join(out_dir, "votings.jsonl")),
        "votes": Dataset.from_json(os.path.join(out_dir, "votes.jsonl")),
    })
    dd.push_to_hub(repo_id, token=token, private=private)
    print(f"pushed DatasetDict with configs: votings, votes -> {repo_id}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump Sejm voting data (official API) into an HF-ready dataset.")
    ap.add_argument("--terms", default="", help="comma-separated term numbers (default: auto-discover 1..12)")
    ap.add_argument("--out", default="dump", help="output directory (default: dump/)")
    ap.add_argument("--limit-sittings", type=int, default=None, help="smoke: cap sittings per term")
    ap.add_argument("--limit-votings", type=int, default=None, help="smoke: cap divisions per sitting")
    ap.add_argument("--sleep", type=float, default=0.25, help="seconds between detail fetches (politeness)")
    ap.add_argument("--push", default="", metavar="REPO_ID", help="push DatasetDict to the Hub after building")
    ap.add_argument("--token", default=None, help="HF token (or set HF_TOKEN env)")
    ap.add_argument("--private", action="store_true", help="make the Hub dataset private")
    args = ap.parse_args()

    terms = [int(x) for x in args.terms.split(",") if x.strip()] if args.terms else discover_terms()
    print(f"terms: {terms}")
    os.makedirs(args.out, exist_ok=True)

    votings_rows, votes_rows, stats, per_term = dump_terms(
        terms, args.out, args.limit_sittings, args.limit_votings, args.sleep
    )
    write_jsonl(votings_rows, os.path.join(args.out, "votings.jsonl"))
    write_jsonl(votes_rows, os.path.join(args.out, "votes.jsonl"))
    manifest = build_manifest(args.out, per_term, stats)
    print(json.dumps(manifest["files"], ensure_ascii=False))
    print(f"fetch stats: {stats}")
    print(f"manifest: {os.path.join(args.out, 'manifest.json')}")

    if args.push:
        token = args.token or os.environ.get("HF_TOKEN")
        if not token:
            sys.exit("--push needs a token: export HF_TOKEN=... (huggingface.co/settings/tokens)")
        build_and_push(args.out, args.push, token, args.private)


if __name__ == "__main__":
    main()
