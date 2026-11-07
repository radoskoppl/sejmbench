#!/usr/bin/env python3
"""Rebuild every committed scorecard with the current scorer (schema 1.4,
issue #14 margin_buckets block), so rescore-check stays green."""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import scoring

manifest = scoring.load_manifest(ROOT)
for p in sorted(glob.glob(os.path.join(ROOT, "results", "*.scorecard.json"))):
    card = json.load(open(p, encoding="utf-8"))
    print(f"rescoring {os.path.basename(p)} (schema {card.get('scorecard_version')})...",
          flush=True)
    rebuilt = scoring.rescore(card, ROOT, manifest)
    # stamp the harness that actually produced the card (rescore carries the
    # committed value; after this pass every card records the current harness,
    # and future rescores carry it back unchanged — rescore-check stays green)
    rebuilt["harness_version"] = open(os.path.join(ROOT, "VERSION"),
                                      encoding="utf-8").read().strip()
    errs = scoring.validate_scorecard(rebuilt)
    if errs:
        raise SystemExit(f"{p}: rebuilt card invalid: {errs}")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rebuilt, f, ensure_ascii=False)
    os.replace(tmp, p)
    mb = rebuilt["layers"]["0.1"].get("margin_buckets", {})
    print(f"  -> schema {rebuilt['scorecard_version']}, macro={mb.get('margin_macro')}",
          flush=True)
print("REBUILD_DONE")
