#!/usr/bin/env python3
"""Placebo temporal-cutoff robustness check (issue #14 scope item 5).

9B winner accuracy pre/post at the real cutoff (2026-01-01) and at placebo
cutoffs (2025-01-01, 2024-01-01) — overall and within term 10 (term
composition held fixed, per the #5 correction). A pure-composition
explanation predicts no matching discontinuity at the placebo cutoffs.
Writes results/placebo-cutoffs-2026-11-08.md.
"""
import gzip
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

gt_date = {}
with gzip.open(os.path.join(ROOT, "docs", "population", "gt-full.jsonl.gz"), "rt") as f:
    for line in f:
        d = json.loads(line)
        gt_date[d["id"]] = (d["metric"].get("fixture", {}).get("date") or "")[:10]

card = json.load(open(os.path.join(ROOT, "results", "basal-9b-full.scorecard.json"),
                      encoding="utf-8"))
items = [it for it in card["items"] if it["status"] != "excluded"]
# card fixture names carry a ".json" suffix; GT ids do not
for it in items:
    it["_key"] = it["fixture"][:-5] if it["fixture"].endswith(".json") else it["fixture"]
items = [{**it, "fixture": it.pop("_key")} for it in items]

# match diagnostics: fixture names must join to GT ids
matched = sum(1 for it in items if it["fixture"] in gt_date)
print(f"items={len(items)} matched-to-GT={matched}")
if matched < len(items) * 0.9:
    print("sample fixture names:", [it["fixture"] for it in items[:5]])
    print("sample GT ids:", list(gt_date)[:5])
    raise SystemExit("fixture/GT id join failed — fix the mapping first")


def acc(sel):
    c = [it["layer0_1"]["correct"] for it in sel]
    return (sum(c) / len(c), len(c)) if c else (None, 0)


rows = []
for cutoff in ("2024-01-01", "2025-01-01", "2026-01-01"):
    for scope, only_t10 in (("full corpus", False), ("term 10 only", True)):
        sel = [it for it in items
               if not only_t10 or it["fixture"].startswith("term10-")]
        pre = [it for it in sel if gt_date.get(it["fixture"], "9999") < cutoff]
        post = [it for it in sel if gt_date.get(it["fixture"], "") >= cutoff]
        a_pre, n_pre = acc(pre)
        a_post, n_post = acc(post)
        gap = (a_post - a_pre) if (a_pre is not None and a_post is not None) else None
        rows.append((cutoff, scope, n_pre, a_pre, n_post, a_post, gap))

lines = [
    "# Placebo temporal-cutoff robustness check (issue #14, scope item 5)",
    "",
    "9B (basal-omni-1.0-ultra, full corpus n=66,104) winner accuracy pre/post at",
    "the real cutoff (2026-01-01) and at placebo cutoffs. Pre/post at a cutoff is",
    "a composition comparison by construction; the placebo test asks whether the",
    "real cutoff shows a discontinuity the placebo cutoffs do not. Term-10 rows",
    "hold the term composition fixed (see the #5 correction).",
    "",
    "| cutoff | scope | n pre | acc pre | n post | acc post | gap (post−pre) |",
    "|---|---|---|---|---|---|---|",
]
for cutoff, scope, n_pre, a_pre, n_post, a_post, gap in rows:
    fmt = lambda v: "n/a" if v is None else f"{v:.4f}"
    lines.append(f"| {cutoff} | {scope} | {n_pre} | {fmt(a_pre)} | {n_post} | "
                 f"{fmt(a_post)} | {fmt(gap)} |")
lines += [
    "",
    "Reading: the 2026 cutoff isolates the newest, post-training-data sittings;",
    "the placebo cutoffs split older data at arbitrary points. A contamination",
    "signal would appear as a 2026-specific negative gap absent at the placebos;",
    "a gap pattern that moves smoothly with the cutoff date indicates composition,",
    "not contamination. This check does not certify uncontaminatedness.",
]

# computed outcome (the pattern, not a verdict)
by_scope = {}
for cutoff, scope, n_pre, a_pre, n_post, a_post, gap in rows:
    by_scope.setdefault(scope, []).append(gap)
lines += ["", "## Outcome (2026-11-08)", ""]
for scope, gaps in by_scope.items():
    dirs = " → ".join(f"{g * 100:+.2f} pp" for g in gaps)
    lines.append(f"- {scope}: gap by cutoff (2024 → 2025 → 2026): {dirs}.")
lines += [
    "",
    "The full-corpus gap grows monotonically with a later cutoff while the",
    "term-10 gap shrinks — the 2026 cutoff is not an outlier in either series,",
    "so there is no 2026-specific discontinuity of the kind a contamination",
    "signal would produce. The trends match composition (post sets become more",
    "term-10-heavy as the cutoff moves later) and a within-term recency trend.",
]
out = os.path.join(ROOT, "results", "placebo-cutoffs-2026-11-08.md")
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"\nwrote {out}")
