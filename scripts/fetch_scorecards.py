#!/usr/bin/env python3
"""Fetch HF-hosted scorecards into results/ so `rescore-check` covers them.

Large model scorecards live in the HF dataset repo
patrykorwat/sejmbench-results (the git repo carries only sha256 references
in results/*.md). The repo is public: no token needed. Idempotent - files
already present are skipped; `rescore-check` then verifies each fetched
card end-to-end (the committed raw tar provides the per-item responses).
"""
import hashlib
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HF_REPO = "patrykorwat/sejmbench-results"
REMOTE_FILES = ["scorecards/basal-9b-full.scorecard.json"]


def main() -> int:
    changed = False
    for rel in REMOTE_FILES:
        dest = os.path.join(ROOT, "results", os.path.basename(rel))
        if os.path.exists(dest):
            print("already present: %s" % os.path.basename(rel))
            continue
        url = "https://huggingface.co/datasets/%s/resolve/main/%s" % (HF_REPO, rel)
        with urllib.request.urlopen(url, timeout=300) as r:
            data = r.read()
        with open(dest, "wb") as fh:
            fh.write(data)
        changed = True
        print("fetched %s: %d bytes sha256=%s" % (
            os.path.basename(rel), len(data), hashlib.sha256(data).hexdigest()))
    print("fetch_scorecards: %s" % ("updated" if changed else "up to date"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
