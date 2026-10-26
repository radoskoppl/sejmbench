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


def get_json(url: str, retries: int = 6):
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
    "totalVoted", "majorityType", "majorityVotes", "votingOptions", "links", "sittingDay",
)


def dump_terms(terms, out_dir, limit_sittings, limit_votings, sleep_s):
    raw_dir = os.path.join(out_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    # stream rows straight to disk: a full corrected dump is ~20M vote rows
    # and must not accumulate in memory (ATX has 14 GB)
    fv = open(os.path.join(out_dir, "votings.jsonl"), "w", encoding="utf-8")
    fs = open(os.path.join(out_dir, "votes.jsonl"), "w", encoding="utf-8")
    n_v = n_s = 0
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
            # BUGFIX 2026-10-25: votingNumber is unique across the WHOLE
            # (multi-day) sitting, but index row's votingsNum counts only its
            # first day — range(1, n+1) silently truncated multi-day sittings
            # (term10: 808 of 5201 votings). Query the sitting list endpoint
            # for the true votingNumber set.
            vnos = []
            lst = []
            try:
                lst = get_json(f"{API}/term{term}/votings/{sitting}") or []
            except urllib.error.HTTPError as e:
                if e.code == 404 and not s.get("votingsNum", 0):
                    lst = []  # empty sitting, nothing to fetch
                else:
                    raise RuntimeError(
                        f"sitting list fetch failed: term{term} s{sitting}: {e}"
                    ) from e
            except Exception as e:
                raise RuntimeError(
                    f"sitting list fetch failed: term{term} s{sitting}: {e}"
                ) from e
            if not lst and s.get("votingsNum", 0):
                raise RuntimeError(
                    f"empty sitting list: term{term} s{sitting} "
                    f"(votingsNum={s['votingsNum']})"
                )
            vnos = [x["votingNumber"] for x in lst]
            time.sleep(0.05)  # ~1540 list calls per pass — be gentle
            if limit_votings:
                vnos = vnos[:limit_votings]
            for vno in vnos:
                fname = os.path.join(tdir, f"v{vno:03d}.json.gz")
                url = f"{API}/term{term}/votings/{sitting}/{vno}"
                detail = None
                if os.path.exists(fname):
                    try:
                        with gzip.open(fname, "rt", encoding="utf-8") as f:
                            detail = json.load(f)
                        stats["cached"] += 1
                    except Exception:
                        # corrupt/empty cache entry (e.g. killed mid-write) — re-fetch
                        os.remove(fname)
                        detail = None
                if detail is None:
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
                fv.write(json.dumps(vrow, ensure_ascii=False) + "\n")
                n_v += 1

                votes = detail.get("votes")
                if isinstance(votes, list):
                    for rec in votes:
                        fs.write(json.dumps({
                            "term": term,
                            "sitting": sitting,
                            "votingNumber": vno,
                            "MP": rec.get("MP"),
                            "club": rec.get("club"),
                            "firstName": rec.get("firstName"),
                            "lastName": rec.get("lastName"),
                            "secondName": rec.get("secondName"),
                            "vote": rec.get("vote"),
                        }, ensure_ascii=False) + "\n")
                        n_s += 1
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
    fv.close()
    fs.close()
    return n_v, n_s, stats, per_term


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


def write_dataset_card(out_dir: str, per_term: dict) -> str:
    coverage = ", ".join(f"term{t}: {v['votings']} divisions" for t, v in sorted(per_term.items()))
    card = f"""---
language:
- pl
license: other
license_name: polish-public-sector-open-statutory-reuse
license_link: https://eli.gov.pl/api/acts/DU/2023/1524/text.html
task_categories:
- text-classification
tags:
- sejm
- poland
- parliament
- roll-call
- votes
pretty_name: Sejm roll-call votes (official API mirror)
source_datasets:
- original
size_categories:
- 1M<n<10M
configs:
- config_name: votings
  data_files:
  - split: train
    path: votings/*.parquet
- config_name: votes
  data_files:
  - split: train
    path: votes/*.parquet
- config_name: sittings
  data_files:
  - split: train
    path: sittings/*.parquet
- config_name: druki
  data_files:
  - split: train
    path: druki/*.parquet
- config_name: druk_texts
  data_files:
  - split: train
    path: druk_texts/*.parquet
---

# Sejm roll-call votes — official API mirror (sejmbench)

Every named vote of the Sejm of the Republic of Poland as served by the
official Sejm API, with one row per MP vote. Five configs:

- `votings` — one row per division (raw API fields + source_url)
- `votes` — one row per MP vote (term, sitting, votingNumber, MP, club, name, vote)
- `sittings` — one row per sitting day
- `druki` — one row per parliamentary print
- `druk_texts` — extracted text of print attachments

Coverage: {coverage}.

## Provenance

- Source: official Sejm API (https://api.sejm.gov.pl) — Chancellery of the Sejm.
- Fetched: {time.strftime('%Y-%m-%d', time.gmtime())}; immutable gzip raw snapshots + sha256
  manifest; nothing derived is added (outcome/majority classification is left to the
  consumer — see CODEBOOK.md in the source repo).

## Process and scoring

https://github.com/radoskoppl/sejmbench (CODEBOOK.md, seed rule, testable hypotheses).
"""
    path = os.path.join(out_dir, "dataset_card.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(card)
    return path


def build_and_push(out_dir: str, repo_id: str, token: str | None, private: bool) -> None:
    try:
        from datasets import (  # type: ignore
            Dataset, DatasetDict, Features, Value,
        )
        from huggingface_hub import HfApi  # type: ignore
    except ImportError as e:
        sys.exit(f"--push requires: pip install datasets huggingface_hub ({e})")
    # Explicit features: JSONL schema inference crashes when a struct column
    # has optional keys that appear only in later chunks — votingOptions
    # structs with/without `description` both occur across terms. Missing
    # keys become None under the declared feature.
    _t, _i = Value("string"), Value("int64")
    dd = DatasetDict({
        "votings": Dataset.from_json(
            os.path.join(out_dir, "votings.jsonl"),
            features=Features({
                "term": _i, "sitting": _i, "votingNumber": _i, "date": _t,
                "sittingDay": _i, "title": _t, "topic": _t, "description": _t,
                "motion": _t, "kind": _t, "yes": _i, "no": _i, "abstain": _i,
                "notParticipating": _i, "present": _i, "totalVoted": _i,
                "majorityType": _t, "majorityVotes": _i,
                "votingOptions": [{
                    "option": _t, "optionIndex": _i, "votes": _i,
                    "description": _t,
                }],
                "links": [{"href": _t, "rel": _t}],
                "source_url": _t,
            }),
        ),
        "votes": Dataset.from_json(
            os.path.join(out_dir, "votes.jsonl"),
            features=Features({
                "term": _i, "sitting": _i, "votingNumber": _i, "MP": _i,
                "club": _t, "firstName": _t, "lastName": _t, "secondName": _t,
                "vote": _t,
            }),
        ),
    })
    api = HfApi(token=token)
    for _cfg, _ds in dd.items():
        # stale shards from earlier pushes (different shard counts) must go,
        # or config globs would index overlapping data
        try:
            api.delete_files(repo_id, repo_type="dataset", delete_patterns=f"{_cfg}/*")
        except Exception as e:
            print(f"  (stale-shard delete for {_cfg}: {e})", flush=True)
        _ds.push_to_hub(repo_id, config_name=_cfg, token=token, private=private)
    print(f"pushed DatasetDict with configs: votings, votes -> {repo_id}")
    card_path = os.path.join(out_dir, "dataset_card.md")
    if os.path.exists(card_path):
        HfApi(token=token).upload_file(
            path_or_fileobj=card_path,
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset",
            commit_message="Add provenance dataset card",
        )
        print(f"dataset card uploaded as README.md -> {repo_id}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump Sejm voting data (official API) into an HF-ready dataset.")
    ap.add_argument("--terms", default="", help="comma-separated term numbers (default: auto-discover 1..12)")
    ap.add_argument("--out", default="dump", help="output directory (default: dump/)")
    ap.add_argument("--limit-sittings", type=int, default=None, help="smoke: cap sittings per term")
    ap.add_argument("--limit-votings", type=int, default=None, help="smoke: cap divisions per sitting")
    ap.add_argument("--sleep", type=float, default=0.25, help="seconds between detail fetches (politeness)")
    ap.add_argument("--push", default="", metavar="REPO_ID", help="push DatasetDict to the Hub after building")
    ap.add_argument("--push-only", action="store_true",
                    help="skip fetching; build+push from the existing JSONL/manifest")
    ap.add_argument("--token", default=None, help="HF token (or set HF_TOKEN env)")
    ap.add_argument("--private", action="store_true", help="make the Hub dataset private")
    args = ap.parse_args()

    terms = [int(x) for x in args.terms.split(",") if x.strip()] if args.terms else discover_terms()
    print(f"terms: {terms}")
    os.makedirs(args.out, exist_ok=True)

    if args.push_only:
        # build+push from the existing JSONL/manifest — no API walk
        mpath = os.path.join(args.out, "manifest.json")
        per_term = {}
        if os.path.exists(mpath):
            with open(mpath, encoding="utf-8") as f:
                per_term = json.load(f).get("terms", {})
        stats = {"fetched": 0, "cached": 0, "missing": 0}
        print("push-only: using existing JSONL + manifest", flush=True)
    else:
        n_v, n_s, stats, per_term = dump_terms(
            terms, args.out, args.limit_sittings, args.limit_votings, args.sleep
        )
        print(f"rows written: votings={n_v} votes={n_s}")
        manifest = build_manifest(args.out, per_term, stats)
        print(json.dumps(manifest["files"], ensure_ascii=False))
        print(f"fetch stats: {stats}")
        print(f"manifest: {os.path.join(args.out, 'manifest.json')}")
        card_path = write_dataset_card(args.out, per_term)
        print(f"dataset card: {card_path}")

    if args.push:
        token = args.token or os.environ.get("HF_TOKEN")
        if not token:
            sys.exit("--push needs a token: export HF_TOKEN=... (huggingface.co/settings/tokens)")
        build_and_push(args.out, args.push, token, args.private)


if __name__ == "__main__":
    main()
