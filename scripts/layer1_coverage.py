#!/usr/bin/env python3
"""Regenerate docs/layer1-coverage.md from the inventory + layer-1 dictionary.

--check (used in CI) compares the regenerated document with the committed one:
the coverage table must never drift silently from the data and the dictionary.
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)

from layer1_classify import classify, classify_all, normalize, load_dictionary  # noqa: E402

CORPUS = 66427


def build():
    d = load_dictionary()
    inv = json.load(open(os.path.join(ROOT, "docs", "inventory-description.json"), encoding="utf-8"))
    rows = inv["formulas"]
    universe = sum(r["total"] for r in rows)
    repairs = [tuple(x) for x in d["normalization"].get("repairs", [])]
    agg, per, canon = {}, {}, {}
    conflicts = 0
    for r in rows:
        b = classify(r["text"], d)
        agg[b] = agg.get(b, 0) + r["total"]
        slot = per.setdefault(b, {"total": 0})
        slot["total"] += r["total"]
        for t, n in r["by_term"].items():
            slot[t] = slot.get(t, 0) + n
        if len(classify_all(r["text"], d)) > 1:
            conflicts += r["total"]
        key = normalize(r["text"], repairs)
        g = canon.setdefault(key, {"total": 0, "raw": set()})
        g["total"] += r["total"]
        g["raw"].add(r["text"])
    covered = sum(v for b, v in agg.items() if b != "unspecified")
    terms = sorted({t for r in rows for t in r["by_term"]}, key=lambda x: (len(x), x))
    order = sorted(agg.items(), key=lambda kv: -kv[1])
    L = [
        f"# Layer 1 dictionary v{d['version']} - coverage report",
        "",
        "Method: each distinct official `description` formula (docs/inventory-description.json, generated from the v0.4.0 mirror) was classified by `layer1_classify.py` with `layer1_dictionary.json`. Universe: divisions carrying a real description formula. Per-formula assignments are CI-diffed (docs/layer1-formula-buckets.json).",
        "",
        f"Universe: {universe} divisions = {universe/CORPUS*100:.1f}% of the {CORPUS:,}-division mirror. The rest has no qualifying description and is outside layer-1 scope - not 'misclassified'.",
        "",
        "| bucket | divisions | share of universe | share of corpus |",
        "|---|---|---|---|",
    ]
    for b, v in order:
        L.append(f"| {b} | {v} | {v/universe*100:.1f}% | {v/CORPUS*100:.1f}% |")
    L += [
        "",
        f"Bucket coverage: {covered} = {covered/universe*100:.1f}% of the described universe; {covered/CORPUS*100:.1f}% of the full corpus.",
        f"Formulas: {len(rows)} raw -> {len(canon)} canonical after normalization ({len(rows)-len(canon)} raw variants collapse into shared canonical forms).",
        f"Rule-order conflicts (matched by >1 bucket): {conflicts} divisions.",
        "",
        "Per term:",
        "",
        "| bucket | " + " | ".join(terms) + " | total |",
        "|---" * (len(terms) + 2) + "|",
    ]
    for b, v in sorted(per.items(), key=lambda kv: -kv[1]["total"]):
        L.append("| " + b + " | " + " | ".join(str(v.get(t, 0)) for t in terms) + f" | {v['total']} |")
    L += [
        "",
        "Notes: draft status - no layer-1 scores until the dictionary is frozen (CODEBOOK section 10); 1,301 of 1,494 formulas are singletons (min-bucket rule, section 8); validation sample split into tuning (200) and held-out test (100) sets.",
    ]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="compare the regenerated document with the committed file")
    args = ap.parse_args()
    doc = build()
    path = os.path.join(ROOT, "docs", "layer1-coverage.md")
    if args.check:
        committed = open(path, encoding="utf-8").read()
        if committed == doc:
            print("OK docs/layer1-coverage.md matches inventory + dictionary")
            raise SystemExit(0)
        print("DRIFT: docs/layer1-coverage.md does not match inventory + dictionary")
        raise SystemExit(1)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"coverage.md written ({len(doc)} bytes)")


if __name__ == "__main__":
    main()
