#!/usr/bin/env python3
"""Issue #11 (v0.5 preflight): reconcile evaluation populations and freeze them.

Three-stage, deterministic, stdlib-only run against the ATX sejm-dump:

  pass 1  votings.jsonl   -> classify every mirror row:
                             zero_counter | inconsistent | out_of_terms | eligible
  pass 2  divisions_*.jsonl -> cross-check id sets, tally votes, flag
                             zero-active-votes rows (degenerate for 0.1/0.2)
  pass 3  seed_rule over the frozen model-evaluation population ->
                             layer 0.1/0.2 computation baselines
                             (majority-class, seeded random, constant-predictor MAE)

Writes:
  <out>/population-v0.5.json          reconciliation table + baselines + hashes
  <out>/ids-full-corpus.txt           frozen item-ID list (term:sitting:votingNumber)
  <out>/ids-term10.txt                term-10 subset
The sha256 of each ID list is the population hash the scorecard must reference.

Usage:
    python3 scripts/freeze_population.py --dump ~/sejm-dump --out docs/population
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import seed_rule  # noqa: E402

TERMS = list(range(3, 11))
RANDOM_SEED = 20261103


def key_of(r):
    return (int(r["term"]), int(r["sitting"]), int(r["votingNumber"]))


def classify(r):
    """Frozen eligibility (CODEBOOK §11 rules, as applied by select_fixtures)."""
    yes, no, ab, tv = (r.get("yes", 0), r.get("no", 0),
                       r.get("abstain", 0), r.get("totalVoted", 0))
    if tv == 0 and yes == 0 and no == 0 and ab == 0:
        return "zero_counter"
    if not (tv and yes + no + ab == tv):
        return "inconsistent"
    if int(r.get("term", 0)) not in TERMS:
        return "out_of_terms"
    return "eligible"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.path.expanduser("~/sejm-dump"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "population"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    votings_path = os.path.join(args.dump, "votings.jsonl")
    div_path = os.path.join(args.dump, "divisions_3_10.jsonl")

    # ---------------- pass 1: mirror classification ----------------
    frame_sha = hashlib.sha256()
    row_counts = {}
    by_term = {}
    key_class = {}            # key -> class (ALL rows must agree; else "mixed")
    n_rows = 0
    n_dup_rows = 0
    with open(votings_path, encoding="utf-8") as fh:
        for line in fh:
            frame_sha.update(line.encode("utf-8"))
            r = json.loads(line)
            n_rows += 1
            c = classify(r)
            row_counts[c] = row_counts.get(c, 0) + 1
            t = int(r.get("term", 0))
            bt = by_term.setdefault(t, {})
            bt[c] = bt.get(c, 0) + 1
            k = key_of(r)
            if k in key_class:
                n_dup_rows += 1
                if key_class[k] != c:
                    key_class[k] = "mixed"
            else:
                key_class[k] = c
    key_counts = {}
    for c in key_class.values():
        key_counts[c] = key_counts.get(c, 0) + 1
    print(f"mirror rows={n_rows} unique_keys={len(key_class)} dup_rows={n_dup_rows} "
          f"frame_sha256={frame_sha.hexdigest()}", file=sys.stderr)
    print(f"pass1 rows: {row_counts} keys: {key_counts}", file=sys.stderr)

    # ---------------- pass 2: divisions cross-check ----------------
    div_seen = set()
    div_zero_active = 0       # ANY division row with no active vote records
    div_not_in_mirror = []    # ids not present in mirror at all
    div_count = 0
    with open(div_path, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            k = key_of(d)
            div_count += 1
            div_seen.add(k)
            if k not in key_class:
                div_not_in_mirror.append(k)
            tallies = {"YES": 0, "NO": 0, "ABSTAIN": 0}
            for v in d["votes"]:
                if v["vote"] in tallies:
                    tallies[v["vote"]] += 1
            if tallies["YES"] + tallies["NO"] + tallies["ABSTAIN"] == 0:
                div_zero_active += 1
    eligible_keys = {k for k, c in key_class.items() if c == "eligible"}
    pop = sorted(k for k in eligible_keys if k in div_seen)
    term10 = [k for k in pop if k[0] == 10]
    print(f"pass2: divisions={div_count} not_in_mirror={len(div_not_in_mirror)} "
          f"zero_active(all)={div_zero_active} eligible_in_div={len(pop)}",
          file=sys.stderr)

    ids_full = os.path.join(args.out, "ids-full-corpus.txt")
    ids_t10 = os.path.join(args.out, "ids-term10.txt")
    with open(ids_full, "w", encoding="utf-8") as f:
        f.write("\n".join(f"{t}:{s}:{v}" for t, s, v in pop) + "\n")
    with open(ids_t10, "w", encoding="utf-8") as f:
        f.write("\n".join(f"{t}:{s}:{v}" for t, s, v in term10) + "\n")

    def sha256_file(p):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    pop_hash = sha256_file(ids_full)
    t10_hash = sha256_file(ids_t10)
    print(f"population: full={len(pop)} term10={len(term10)} "
          f"hash={pop_hash[:12]}/{t10_hash[:12]}", file=sys.stderr)

    # ---------------- pass 3: baselines on the frozen population ----------------
    # Stream divisions again, keep only population rows, run seed_rule.
    pop_set = set(pop)
    winners = []                       # "yes"/"no" per division (GT)
    track_yes_share, track_polar = [], []
    with open(div_path, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            if key_of(d) not in pop_set:
                continue
            m = seed_rule.compute_metric(d)
            winners.append(m["seed_rule"]["winner"])
            for tr in m["tracks"].values():
                track_yes_share.append(tr["yes_share"])
                track_polar.append(tr["polarization"])

    n = len(winners)
    assert n == len(pop), f"divisions pass found {n}, population {len(pop)}"

    # layer 0.1 winner task
    p_yes = winners.count("yes") / n
    majority_acc = max(p_yes, 1 - p_yes)
    # exact expectation for a seeded uniform 50/50 predictor:
    from statistics import mean
    rand_acc_exact = 0.5 * p_yes + 0.5 * (1 - p_yes)

    # layer 0.2 cohesion task: constant predictors (population means)
    mean_share, mean_polar = mean(track_yes_share), mean(track_polar)
    mae_share = mean([abs(s - mean_share) for s in track_yes_share])
    mae_polar = mean([abs(p - mean_polar) for p in track_polar])
    # zero-prediction variant (predict unanimous-in-favour: share=1, polar=0)
    mae_share_zero = mean([abs(s - 1.0) for s in track_yes_share])
    mae_polar_zero = mean([abs(p - 0.0) for p in track_polar])

    report = {
        "schema": "sejmbench.population/0.5",
        "generated_by": "scripts/freeze_population.py",
        "frame_sha256_votings_jsonl": frame_sha.hexdigest(),
        "random_seed": RANDOM_SEED,
        "definitions": {
            "zero_counter": "totalVoted == 0 and yes == no == abstain == 0 (layers 0.1/0.2 not eligible)",
            "inconsistent": "totalVoted != yes + no + abstain (headline tallies disagree)",
            "out_of_terms": "term outside 3..10 (no division records built)",
            "eligible": "consistent tallies and term in 3..10",
            "model_population": "unique mirror keys classified eligible, present in "
                                "divisions_3_10.jsonl with >= 1 active vote record",
        },
        "reconciliation": {
            "mirror_rows": n_rows,
            "mirror_unique_keys": len(key_class),
            "mirror_duplicate_rows": n_dup_rows,
            "unique_key_classes": key_counts,
            "divisions_rows": div_count,
            "divisions_zero_active": div_zero_active,
            "predictive_backtest_scored_note": "66,345 divisions - 241 zero-active "
                "- 60 warmup = 66,044 scored in the #8 predictive backtest (a different "
                "construct that INCLUDES inconsistent-tally rows); not a model-eval set",
            "prior_universe_note": "the 66,113 'universe' from CODEBOOK §11 counted eligible "
                "ROWS, not unique keys; at key level the count is "
                + str(key_counts.get("eligible", 0)),
        },
        "mirror_row_counts": row_counts,
        "divisions_not_in_mirror": len(div_not_in_mirror),
        "population_full": {"n": len(pop), "ids_file": "ids-full-corpus.txt",
                            "sha256": pop_hash},
        "population_term10": {"n": len(term10), "ids_file": "ids-term10.txt",
                              "sha256": t10_hash},
        "baselines_layer0_1": {
            "n": n,
            "p_yes": round(p_yes, 6),
            "majority_class_accuracy": round(majority_acc, 6),
            "random_uniform_accuracy": round(rand_acc_exact, 6),
        },
        "baselines_layer0_2": {
            "n_tracks": len(track_yes_share),
            "mean_yes_share": round(mean_share, 6),
            "mean_polarization": round(mean_polar, 6),
            "mae_constant_mean_share": round(mae_share, 6),
            "mae_constant_mean_polarization": round(mae_polar, 6),
            "mae_predict_share_one_polar_zero": {
                "share": round(mae_share_zero, 6), "polarization": round(mae_polar_zero, 6)},
        },
        "per_term": {str(t): by_term[t] for t in sorted(by_term)},
    }
    out_json = os.path.join(args.out, "population-v0.5.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: report[k] for k in
                      ("reconciliation", "population_full", "population_term10",
                       "baselines_layer0_1", "baselines_layer0_2")},
                     indent=1))
    print(f"wrote {out_json}", file=sys.stderr)


if __name__ == "__main__":
    main()
