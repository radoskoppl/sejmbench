#!/usr/bin/env python3
"""Leakage checks for layer-1/0.x fixtures (CODEBOOK sections 5, 9.2, 10).

Layer A (hard fail): the label-source field (`description`) of a fixture must
never appear in the reference prompt (CODEBOOK section 5) built for that
fixture, and the prompt must not contain the field name.

Layer B (informational, no fail while the input-spec is open): scan dictionary
needles against the candidate visible fields (`title`, `topic`) of each
fixture - the per-field/per-bucket rates feed the input-spec decision
(section 10).
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)

from layer1_classify import normalize, load_dictionary  # noqa: E402


def build_prompt(division):
    """Reference prompt (CODEBOOK section 5): club | name | vote lines."""
    lines = []
    for v in (division.get("votes") or []):
        name = " ".join(x for x in (v.get("firstName"), v.get("secondName"), v.get("lastName")) if x)
        lines.append(f"{v.get('club', '')} | {name} | {v.get('vote', '')}")
    return ("You are analyzing a roll-call division (głosowanie imienne) of the Sejm\n"
            "of the Republic of Poland. Each line below is one MP: club | name | vote,\n"
            "where vote is YES / NO / ABSTAIN / ABSENT.\n\n"
            + "\n".join(lines)
            + "\n\nAnswer ONLY with a JSON object.")


def main():
    d = load_dictionary()
    repairs = [tuple(x) for x in d["normalization"].get("repairs", [])]
    failures = 0
    leak_rates = {}
    with open(os.path.join(ROOT, "fixtures", "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    fixtures = [os.path.join(ROOT, e["file"]) for e in manifest["fixtures"]]
    for path in fixtures:
        div = json.load(open(path, encoding="utf-8"))
        prompt = build_prompt(div)
        desc = (div.get("description") or "").strip()
        if desc and desc in prompt:
            print(f"FAIL label-source leakage: description string present in prompt ({os.path.basename(path)})")
            failures += 1
        if "description" in prompt:
            print(f"FAIL label-source field name present in prompt ({os.path.basename(path)})")
            failures += 1
        for field in ("title", "topic"):
            val = normalize(div.get(field) or "", repairs, strip=False)
            for rule in d["rules"]:
                needle = normalize(rule["needle"], repairs, strip=False)
                hit = val.startswith(needle) if rule["match"] == "prefix" else needle in val
                if hit:
                    key = (field, rule["bucket"])
                    leak_rates[key] = leak_rates.get(key, 0) + 1
    print(f"fixtures scanned: {len(fixtures)}")
    print("needle hits in candidate visible fields (informational, feeds the input-spec decision):")
    for (field, bucket), n in sorted(leak_rates.items()):
        print(f"  {field:6s} {bucket:24s} {n}")
    if not leak_rates:
        print("  none")
    print("OK no label-source leakage" if not failures else "LEAKAGE DETECTED")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
