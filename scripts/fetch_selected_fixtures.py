#!/usr/bin/env python3
"""Fetch the selected v0.3 fixture set (issue #1) from the live Sejm API.

Reads fixtures/selection.json (the committed output of
scripts/select_fixtures.py), downloads each division detail from
api.sejm.gov.pl, writes the fixture files, and rebuilds
fixtures/manifest.json:

- the two v0.2 anchor entries are preserved (their FILES are never
  rewritten; the entries only gain `response_sha256` after a byte-equality
  check of the parsed response against the committed file),
- the new entries carry layer eligibility, selection provenance and the
  sha256 of the raw API response bytes.

Re-fetching and field-by-field comparison against the live API and the
mirror row is scripts/verify_provenance.py (operator tool — CI must not
call the API).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = "https://api.sejm.gov.pl/sejm/term{term}/votings/{sitting}/{voting}"
FIXTURES = os.path.join(ROOT, "fixtures")
ANCHORS = {(10, 1, 2), (10, 6, 14)}  # v0.2 anchors — files are never rewritten


def fetch_raw(url: str, attempts: int = 5) -> bytes:
    """GET with retries on transient failures (429/5xx/connection errors)."""
    delay = 2.0
    last = None
    for _ in range(attempts):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "sejmbench/0.3 (github.com/radoskoppl/sejmbench)"})
            with urllib.request.urlopen(req, timeout=120) as f:
                return f.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            last = exc
        except urllib.error.URLError as exc:  # timeouts, DNS, connection reset
            last = exc
        time.sleep(delay)
        delay = min(delay * 2, 30.0)
    raise RuntimeError(f"fetch failed after {attempts} attempts: {url}: {last}")


def fetch_one(entry: dict, write: bool = True) -> tuple:
    term, sitting, voting = entry["term"], entry["sitting"], entry["votingNumber"]
    url = BASE.format(term=term, sitting=sitting, voting=voting)
    raw = fetch_raw(url)
    d = json.loads(raw.decode("utf-8"))
    name = f"term{term}-s{sitting}-v{voting}-{entry['bucket']}.json"
    path = os.path.join(FIXTURES, name)
    if write:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
        file_sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    else:
        file_sha = None  # anchor mode: the committed file is never rewritten
    yes, no, ab, tv = d.get("yes", 0), d.get("no", 0), d.get("abstain", 0), d.get("totalVoted", 0)
    counters_usable = bool(tv) and yes + no + ab == tv
    desc = d.get("description")
    layers_1 = bool(desc and str(desc).strip() and str(desc).strip() != "-")
    if entry["bucket"] == "election" and not counters_usable:
        pass  # expected: the curated zero-counter case
    elif entry["bucket"] == "election" and counters_usable:
        print(f"WARN election-curated has usable counters: {name}", file=sys.stderr)
    record = {
        "file": f"fixtures/{name}",
        "sha256": file_sha,
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "term": d["term"],
        "sitting": d["sitting"],
        "votingNumber": d["votingNumber"],
        "title": d["title"],
        "date": d["date"],
        "kind": d.get("kind"),
        "description": d.get("description"),
        "counts": {k: d[k] for k in ("yes", "no", "abstain", "notParticipating", "totalVoted")},
        "source_url": url,
        "n_vote_records": len(d["votes"]),
        "selection": entry["selection"],
        "margin_bucket": entry["bucket"],
        "type_bucket": entry["type"],
        "layers": {"0.1": counters_usable, "0.2": counters_usable, "1": layers_1},
    }
    return record, d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selection", default=os.path.join(FIXTURES, "selection.json"))
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    with open(args.selection, encoding="utf-8") as fh:
        selection = json.load(fh)
    manifest_path = os.path.join(FIXTURES, "manifest.json")
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    anchors, fresh = [], []
    for entry in selection["selected"]:
        key = (entry["term"], entry["sitting"], entry["votingNumber"])
        (anchors if key in ANCHORS else fresh).append(entry)
    if anchors:
        print(f"selection contains anchor keys {anchors} - anchors are handled separately",
              file=sys.stderr)

    records, mismatches = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for entry, (record, d) in zip(fresh, ex.map(fetch_one, fresh)):
            records.append(record)

    # anchors: re-fetch for response_sha256; verify byte-equality of the parsed
    # response against the committed file; never rewrite the file
    for term, sitting, voting in sorted(ANCHORS):
        record, d = fetch_one({"term": term, "sitting": sitting, "votingNumber": voting,
                               "bucket": "anchor", "selection": "anchor", "type": "anchor"},
                              write=False)
        entry = next(e for e in manifest["fixtures"]
                     if (e["term"], e["sitting"], e["votingNumber"]) == (term, sitting, voting))
        with open(os.path.join(ROOT, entry["file"]), encoding="utf-8") as fh:
            committed = json.load(fh)
        if committed != d:
            mismatches.append(f"anchor drift: {entry['file']} differs from the live API")
        else:
            entry["response_sha256"] = record["response_sha256"]

    if mismatches:
        for m in mismatches:
            print(f"FAIL {m}", file=sys.stderr)
        return 1

    manifest["fetched_at_utc"] = manifest.get("fetched_at_utc")  # anchors keep their fetch stamp
    manifest["v03_selection"] = {
        "selection_file": "fixtures/selection.json",
        "seed": selection["seed"],
        "frame_votings_sha256": selection["frame"]["votings_sha256"],
    }
    all_entries = manifest["fixtures"] + records
    all_entries.sort(key=lambda e: e["file"])
    manifest["fixtures"] = all_entries
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    print(f"fetched {len(records)} new fixtures; manifest now has "
          f"{len(all_entries)} entries ({sum(1 for e in all_entries if e.get('selection') == 'curated')} curated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
