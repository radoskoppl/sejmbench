#!/usr/bin/env python3
"""Provenance verification (issue #1): fixtures vs live API and mirror row.

Operator tool — deliberately NOT part of CI (CI must not call the Sejm API).
Re-fetches every manifest fixture from api.sejm.gov.pl and compares:

1. live API response (parsed) vs the committed fixture file — content
   mismatch is a FAILURE;
2. live API response vs the mirror row in `votings.jsonl` (shared fields;
   mirror-only fields such as `votingOptions`/`links`/`source_url` are
   ignored) — a mismatch is a FAILURE;
3. the fixture file's sha256 against the manifest entry — mismatch is a
   FAILURE;
4. the raw response's sha256 against the manifest's `response_sha256` —
   byte-level instability with equal content is reported as a WARNING
   (the contract is content equality; key order must not fail the check).

Usage (the dump lives on the operator host):
    python3 scripts/verify_provenance.py --dump ~/sejm-dump
    python3 scripts/verify_provenance.py          # skip the mirror comparison
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from fetch_selected_fixtures import BASE, fetch_raw  # noqa: E402

SHARED_FIELDS = ("term", "sitting", "votingNumber", "title", "date", "kind",
                 "description", "yes", "no", "abstain", "totalVoted",
                 "notParticipating", "present")


def diff_fields(a: dict, b: dict) -> list:
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            out.append(f"{k}: live={a.get(k)!r} committed={b.get(k)!r}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=os.path.join(ROOT, "fixtures", "manifest.json"))
    ap.add_argument("--dump", help="sejm-dump directory with votings.jsonl (enables the mirror check)")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)

    mirror = {}
    if args.dump:
        with open(os.path.join(args.dump, "votings.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                mirror[(row["term"], row["sitting"], row["votingNumber"])] = row

    failures, warnings = [], []
    for entry in manifest["fixtures"]:
        name = entry["file"]
        path = os.path.join(ROOT, entry["file"])
        with open(path, "rb") as fh:
            blob = fh.read()
        if hashlib.sha256(blob).hexdigest() != entry["sha256"]:
            failures.append(f"{name}: file sha256 does not match the manifest")
        committed = json.loads(blob.decode("utf-8"))

        url = BASE.format(term=entry["term"], sitting=entry["sitting"], voting=entry["votingNumber"])
        raw = fetch_raw(url)
        live = json.loads(raw.decode("utf-8"))

        if hashlib.sha256(raw).hexdigest() != entry.get("response_sha256"):
            warnings.append(f"{name}: raw response bytes differ from the recorded "
                            f"response_sha256 (content comparison decides)")
        if live != committed:
            failures.append(f"{name}: live API differs from the committed fixture: "
                            f"{diff_fields(live, committed)[:5]}")

        if args.dump:
            row = mirror.get((entry["term"], entry["sitting"], entry["votingNumber"]))
            if row is None:
                failures.append(f"{name}: no mirror row for the division")
            else:
                for field in SHARED_FIELDS:
                    if row.get(field) != committed.get(field):
                        failures.append(f"{name}: mirror mismatch on {field}: "
                                        f"mirror={row.get(field)!r} fixture={committed.get(field)!r}")

    for w in warnings:
        print(f"WARN {w}")
    for f in failures:
        print(f"FAIL {f}")
    print(f"provenance: {len(manifest['fixtures'])} fixtures, {len(failures)} failures, "
          f"{len(warnings)} warnings, mirror check {'on' if args.dump else 'off'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
