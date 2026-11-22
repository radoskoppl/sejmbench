#!/usr/bin/env python3
"""CI gate (issue #1 scope 6): every club label in the fixture set must be
present in docs/club-identity.json for its term.

An unmapped club id — a (term, label) pair appearing in any fixture file that
the identity registry does not know — fails the build. The registry covers
every raw API label observed in the terms 3-10 corpus, so this gate fails on
both typos and genuinely new labels until they are curated.

Usage: python3 scripts/club_identity_check.py [--identity docs/club-identity.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(ROOT, "fixtures")
DEFAULT_IDENTITY = os.path.join(ROOT, "docs", "club-identity.json")


def fixture_clubs(fixtures_dir=FIXTURES):
    """{(term, club): [fixture files]} for every vote record in the set."""
    seen = {}
    for path in sorted(glob.glob(os.path.join(fixtures_dir, "*.json"))):
        name = os.path.basename(path)
        if name in ("manifest.json", "selection.json"):  # support files
            continue
        with open(path, encoding="utf-8") as fh:
            fx = json.load(fh)
        if "votes" not in fx or "term" not in fx:
            continue  # structure is verify_fixtures.py's job
        term = fx["term"]
        for vote in fx.get("votes", []):
            club = vote.get("club")
            if club:
                seen.setdefault((term, club), []).append(name)
    return seen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--identity", default=DEFAULT_IDENTITY)
    ap.add_argument("--fixtures", default=FIXTURES)
    args = ap.parse_args()

    with open(args.identity, encoding="utf-8") as fh:
        table = json.load(fh)
    known = set()
    for term_s, entry in table["terms"].items():
        for label in entry["labels"]:
            known.add((int(term_s), label))

    problems = []
    for (term, club), files in sorted(fixture_clubs(args.fixtures).items()):
        if (term, club) not in known:
            problems.append(f"unmapped club id: term {term} `{club}` in {', '.join(sorted(set(files)))}")

    if problems:
        for p in problems:
            print("FAIL", p, file=sys.stderr)
        return 1
    n_pairs = len(fixture_clubs())
    print(f"club-identity check OK: {n_pairs} (term, club) pairs covered by the registry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
