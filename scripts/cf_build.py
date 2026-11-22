#!/usr/bin/env python3
"""Build the #15 counterfactual spike set (perturbed twins of term-10 divisions).

Perturbations (issue #15 design):
  flip        convert k = seed_margin//2 + 1 winning-side votes (of TRACK clubs)
              to the losing value, so the seed-rule winner flips; GT recomputed
              with seed_rule.compute_metric on the modified records.
  reorder     shuffle the vote records (seeded) - GT unchanged; control for
              answer stability (expect the same answer as the original run).
  pseudonymize  rename clubs to K1..Kn by descending track size (deterministic;
              ties alphabetical); GT unchanged.

Sampling: seeded (20261027), term-10 only (frozen population ids-term10.txt),
flip quota narrow(1-5)=60, close(6-50)=60, wide(>=51)=30, reorder=50,
pseudonymize=50. Pools are disjoint (flip first, then reorder, then pseudo).

Outputs in --out (default ~/cf-dump):
  divisions_3_10.jsonl   perturbed divisions (same schema; ids unchanged)
  ids-cf.txt             "term:s:v" lines for the runner
  manifest-cf.json       per-item provenance: perturbation, params, GT original
                         and perturbed (seed_rule), records sha256, source_url
  README-CF.md           SYNTHETIC DERIVED DATA note (issue #15 DATA_LICENSE)
"""
import hashlib
import json
import os
import random
import sys

REPO = os.path.expanduser("~/sejmbench")
sys.path.insert(0, REPO)
import seed_rule  # noqa: E402

SEED = 20261027
QUOTA = {"flip_narrow": 60, "flip_close": 60, "flip_wide": 30, "reorder": 50, "pseudo": 50}
DUMP = os.path.expanduser("~/sejm-dump/divisions_3_10.jsonl")
IDS = os.path.join(REPO, "docs", "population", "ids-term10.txt")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/cf-dump")


def bucket_of(seed_margin):
    if seed_margin <= 5:
        return "flip_narrow"
    if seed_margin <= 50:
        return "flip_close"
    return "flip_wide"


def main():
    os.makedirs(OUT, exist_ok=True)
    ids = set()
    with open(IDS, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                t, s, v = line.strip().split(":")
                ids.add(f"term{t}-s{s}-v{v}")

    divisions = {}
    with open(DUMP, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            item_id = f"term{d['term']}-s{d['sitting']}-v{d['votingNumber']}"
            if item_id in ids:
                divisions[item_id] = d
    print(f"loaded {len(divisions)} term-10 divisions", file=sys.stderr)

    rng = random.Random(SEED)
    item_ids = sorted(divisions)
    rng.shuffle(item_ids)

    # pass 1: classify by flip bucket, pick flips first
    pools = {k: [] for k in QUOTA}
    taken = set()
    # order items by bucket for flip selection; then fill reorder/pseudo from the rest
    for item_id in item_ids:
        d = divisions[item_id]
        m = seed_rule.compute_metric(d)
        sr = m["seed_rule"]
        if sr["tie"] or sr["winner"] not in ("yes", "no"):
            continue  # ties: no clean flip via k-conversion; keep out of scope (noted)
        if sr["method"] != "majority":
            continue
        seed_margin = abs(sr["margin"])
        b = bucket_of(seed_margin)
        pools[b].append(item_id)

    chosen = {}
    for b, quota in (("flip_narrow", QUOTA["flip_narrow"]),
                     ("flip_close", QUOTA["flip_close"]),
                     ("flip_wide", QUOTA["flip_wide"])):
        take = pools[b][:quota]
        if len(take) < quota:
            print(f"NOTE pool {b}: only {len(take)} of {quota} available", file=sys.stderr)
        for i in take:
            chosen[i] = ("flip", b)
            taken.add(i)
    rest = [i for i in item_ids if i not in taken]
    reorder_ids = rest[:QUOTA["reorder"]]
    for i in reorder_ids:
        chosen[i] = ("reorder", None)
    taken.update(reorder_ids)
    rest = [i for i in item_ids if i not in taken]
    pseudo_ids = rest[:QUOTA["pseudo"]]
    for i in pseudo_ids:
        chosen[i] = ("pseudo", None)
    taken.update(pseudo_ids)

    print(f"chosen: flip={sum(1 for v in chosen.values() if v[0]=='flip')} "
          f"reorder={len(reorder_ids)} pseudo={len(pseudo_ids)}", file=sys.stderr)

    manifest_entries = []
    out_rows = []
    for item_id in sorted(chosen):
        kind, bucket = chosen[item_id]
        d = divisions[item_id]
        records_sha = hashlib.sha256(
            json.dumps(d["votes"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        m0 = seed_rule.compute_metric(d)
        sr0 = m0["seed_rule"]
        gt0 = {"winner": sr0["winner"], "tie": sr0["tie"], "method": sr0["method"],
               "seed_margin": sr0["margin"]}
        entry = {"item_id": item_id, "perturbation": kind,
                 "source_url": (f"https://api.sejm.gov.pl/sejm/term{d['term']}/"
                                f"votings/{d['sitting']}/{d['votingNumber']}"),
                 "records_sha256_original": records_sha,
                 "gt_original": gt0}
        votes = [dict(v) for v in d["votes"]]

        if kind == "flip":
            # k winning-side votes of TRACK clubs -> losing value
            from collections import Counter
            cnt = Counter(v["club"] for v in votes)
            tracks = {c for c, n in cnt.items() if n >= seed_rule.MIN_TRACK_RECORDS}
            win_vote = "YES" if sr0["winner"] == "yes" else "NO"
            lose_vote = "NO" if win_vote == "YES" else "YES"
            win_count = sum(1 for v in votes if v["club"] in tracks and v["vote"] == win_vote)
            k = abs(sr0["margin"]) // 2 + 1
            if win_count < k:
                print(f"SKIP flip {item_id}: win_count {win_count} < k {k}", file=sys.stderr)
                continue
            flipped = 0
            for v in votes:
                if flipped >= k:
                    break
                if v["club"] in tracks and v["vote"] == win_vote:
                    v["vote"] = lose_vote
                    flipped += 1
            entry["params"] = {"k_flipped": flipped, "from": win_vote, "to": lose_vote}
            dp = dict(d)
            dp["votes"] = votes
            m1 = seed_rule.compute_metric(dp)
            sr1 = m1["seed_rule"]
            gt1 = {"winner": sr1["winner"], "tie": sr1["tie"], "method": sr1["method"],
                   "seed_margin": sr1["margin"]}
            assert gt1["winner"] != gt0["winner"], f"flip failed to flip: {item_id}"
            entry["gt_perturbed"] = gt1
            entry["bucket"] = bucket
            out_rows.append(dp)
        elif kind == "reorder":
            rng2 = random.Random(hash((SEED, item_id)) & 0xFFFFFFFF)
            rng2.shuffle(votes)
            entry["params"] = {"shuffle_seed": hash((SEED, item_id)) & 0xFFFFFFFF}
            dp = dict(d)
            dp["votes"] = votes
            m1 = seed_rule.compute_metric(dp)
            sr1 = m1["seed_rule"]
            gt1 = {"winner": sr1["winner"], "tie": sr1["tie"], "method": sr1["method"],
                   "seed_margin": sr1["margin"]}
            assert gt1 == gt0, f"reorder changed GT: {item_id}"
            entry["gt_perturbed"] = gt1
            out_rows.append(dp)
        else:  # pseudo
            from collections import Counter
            cnt = Counter(v["club"] for v in votes)
            order = sorted(cnt, key=lambda c: (-cnt[c], c))
            mapping = {c: f"K{i+1}" for i, c in enumerate(order)}
            for v in votes:
                v["club"] = mapping[v["club"]]
            entry["params"] = {"mapping": mapping}
            dp = dict(d)
            dp["votes"] = votes
            m1 = seed_rule.compute_metric(dp)
            sr1 = m1["seed_rule"]
            gt1 = {"winner": sr1["winner"], "tie": sr1["tie"], "method": sr1["method"],
                   "seed_margin": sr1["margin"]}
            assert gt1 == gt0, f"pseudo changed GT: {item_id}"
            entry["gt_perturbed"] = gt1
            out_rows.append(dp)

        manifest_entries.append(entry)

    with open(os.path.join(OUT, "divisions_3_10.jsonl"), "w", encoding="utf-8") as fh:
        for dp in out_rows:
            fh.write(json.dumps(dp, ensure_ascii=False, sort_keys=True) + "\n")
    with open(os.path.join(OUT, "ids-cf.txt"), "w", encoding="utf-8") as fh:
        for dp in out_rows:
            fh.write(f"{dp['term']}:{dp['sitting']}:{dp['votingNumber']}\n")
    manifest = {
        "kind": "sejmbench-counterfactual-spike",
        "issue": 15,
        "seed": SEED,
        "base_population": "ids-term10.txt (5,137; docs/population)",
        "synthetic_derived": True,
        "counts": {"flip_narrow": sum(1 for e in manifest_entries if e.get("bucket") == "flip_narrow"),
                   "flip_close": sum(1 for e in manifest_entries if e.get("bucket") == "flip_close"),
                   "flip_wide": sum(1 for e in manifest_entries if e.get("bucket") == "flip_wide"),
                   "reorder": sum(1 for e in manifest_entries if e["perturbation"] == "reorder"),
                   "pseudo": sum(1 for e in manifest_entries if e["perturbation"] == "pseudo")},
        "gt_source": "seed_rule.compute_metric (repo seed_rule.py) on perturbed records",
        "items": manifest_entries,
    }
    with open(os.path.join(OUT, "manifest-cf.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "README-CF.md"), "w", encoding="utf-8") as fh:
        fh.write("""# Counterfactual spike set (issue #15) — SYNTHETIC DERIVED DATA

These records are DERIVED from the official Sejm API mirror by deterministic
perturbation (seed 20261027). They are NOT official votes: modified records
must never enter the benchmark corpus, the fixture manifest, or any accuracy
scorecard. Tracked separately per issue #15 (DATA_LICENSE note). Each item's
provenance: original division (source_url + records sha256), perturbation
parameters, and GT recomputed with the frozen seed_rule.
""")
    print(f"WROTE {len(out_rows)} items to {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
