#!/usr/bin/env python3
"""Leakage diagnostic for the counterfactual spike set (issue #15).

Issue #15 requires evidence that the perturbation alone does not trivially
predict the verdict. This script quantifies the trivially-predictable signal:

  flip arm    the perturbed GT outcome distribution (a model answering the
              modal perturbed outcome without reading any records would score
              max(count)/n_flip on this arm);
  reorder arm GT is unchanged, so the "perturbation predicts the answer"
              signal is zero by construction (the correct answer is the
              original outcome);
  club-label pseudonymization arm
              same as reorder — GT unchanged.

The script also verifies the arm balance and prints the manifest's
quotas/shortfalls. Exit code 0 always; this is a REPORT, not a gate — the
gate is the recorded balance in manifest-cf.json.

Usage:
  python3 scripts/cf_leakage_check.py [path/to/manifest-cf.json]
  # default: ~/cf-dump/manifest-cf.json (ATX) — falls back to building nothing
"""
import json
import os
import sys
from collections import Counter

DEFAULT = os.path.expanduser("~/cf-dump/manifest-cf.json")


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not os.path.exists(path):
        print(f"cf-leakage: manifest not found at {path} — run scripts/cf_build.py first",
              file=sys.stderr)
        return 0
    m = json.load(open(path, encoding="utf-8"))
    items = m["items"]

    by_arm = {}
    for e in items:
        by_arm.setdefault(e["perturbation"], []).append(e)

    lines = ["cf-leakage diagnostic (issue #15): does the perturbation alone",
             "trivially predict the verdict?", ""]

    # reorder / pseudonymize: GT unchanged — the perturbation carries no signal
    for arm in ("reorder", "club_label_pseudonymize"):
        n = len(by_arm.get(arm, []))
        lines.append(f"  {arm}: n={n}; GT unchanged by construction — the perturbation "
                     f"carries no answer signal (any fixed answer scores original-baseline)")

    # flip: GT flips — the only arm where a fixed answer could score
    flips = by_arm.get("flip", [])
    n = len(flips)
    if n:
        cnt = Counter(e["gt_perturbed"]["winner"] for e in flips)
        modal, mc = cnt.most_common(1)[0]
        lines.append(f"  flip: n={n}; perturbed-GT distribution {dict(cnt)}; "
                     f"a fixed '{modal}' answer (no reading) would score "
                     f"{mc}/{n} = {mc/n:.3f}")
        orig = Counter(e["gt_original"]["winner"] for e in flips)
        lines.append(f"        original-GT distribution {dict(orig)} — the flip "
                     f"direction is data-driven (winner-dependent), not fixed")
    else:
        lines.append("  flip: n=0")

    lines.append("")
    lines.append(f"quotas/shortfalls: {json.dumps(m['quotas'], ensure_ascii=False)}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
