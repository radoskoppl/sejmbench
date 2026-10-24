"""Fetch real divisions from the Sejm API and save them as fixtures.

Usage:
    python scripts/fetch_fixtures.py            # the two pinned divisions
    python scripts/fetch_fixtures.py --list     # new: pick your own

Pinned divisions (see fixtures/manifest.json for sha256 pins):
  term10 sitting 1  voting 2  - 458:0  (landslide)
  term10 sitting 6  voting 14 - 224:196 (tight, third reading, pharmacy law)
"""

import argparse
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone

BASE = "https://api.sejm.gov.pl/sejm/term{term}/votings/{sitting}/{voting}"
FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")

PINNED = [
    (10, 1, 2, "landslide"),
    (10, 6, 14, "tight"),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sejmbench/0.2 (github.com/radoskoppl/sejmbench)"})
    with urllib.request.urlopen(req, timeout=60) as f:
        return json.load(f)


def save(term, sitting, voting, label):
    d = get(BASE.format(term=term, sitting=sitting, voting=voting))
    name = f"term{term}-s{sitting}-v{voting}-{label}.json"
    path = os.path.join(FIXTURES, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return {
        "file": f"fixtures/{name}",
        "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
        "term": d["term"],
        "sitting": d["sitting"],
        "votingNumber": d["votingNumber"],
        "title": d["title"],
        "date": d["date"],
        "kind": d.get("kind"),
        "counts": {k: d[k] for k in ("yes", "no", "abstain", "notParticipating", "totalVoted")},
        "source_url": f"https://api.sejm.gov.pl/sejm/term{term}/votings/{sitting}/{voting}",
        "n_vote_records": len(d["votes"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="list pinned divisions and exit")
    args = ap.parse_args()
    if args.list:
        for t, s, v, label in PINNED:
            print(f"term{t} sitting {s} voting {v} ({label})")
        return
    os.makedirs(FIXTURES, exist_ok=True)
    manifest = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Sejm API v1 (https://api.sejm.gov.pl) - official public API of the Chancellery of the Sejm",
        "fixtures": [save(t, s, v, label) for t, s, v, label in PINNED],
    }
    with open(os.path.join(FIXTURES, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
