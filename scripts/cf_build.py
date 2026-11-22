#!/usr/bin/env python3
"""Build the #15 counterfactual spike set (perturbed twins of term-10 divisions).

Perturbations (issue #15; formalized in docs/lean/Sejmbench/Counterfactual.lean):
  flip          convert k = floor(seed_margin/2) + 1 winning-side records of
                TRACK clubs to the losing value (chosen by a stable seeded RNG
                over the qualifying records); GT recomputed with
                seed_rule.compute_metric; headline counters recomputed from
                the modified records.
  reorder       shuffle the vote records with a stable per-item seed
                (SHA-256-derived, not hash()) — GT unchanged.
  club-label pseudonymization
                rename clubs to K1..Kn by descending track size (ties
                alphabetical); GT unchanged. NOTE: records keep MP ids and
                names — this tests dependence on club LABELS, not on MP
                identity.

Determinism: every per-item seed is derived from (SEED, item_id) via
SHA-256 (stable across processes — Python hash() is salted and is NOT used).
Running the same command twice produces byte-identical outputs
(tests/test_cf_deterministic.py).

Usage:
  python3 scripts/cf_build.py [--repo ~/sejmbench] [--dump ~/sejm-dump]
                              [--out ~/cf-dump]

Quotas (frozen): flip narrow(<=5)=60, close(6-50)=60, wide(>=51)=30,
reorder=50, club-label-pseudonymize=50; pools disjoint (flip first, then
reorder, then pseudonymize). Shortfalls (e.g. narrow: 18 available) are
recorded in the manifest with the reason.
"""
import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter

SEED = 20261027
QUOTA = {"flip_narrow": 60, "flip_close": 60, "flip_wide": 30,
         "reorder": 50, "club_label_pseudonymize": 50}
SHORTFALL_REASON = "insufficient eligible population in the frozen term-10 frame"


def stable_item_seed(seed: int, item_id: str) -> int:
    """SHA-256-derived per-item seed — stable across processes (hash() is not)."""
    payload = f"{seed}:{item_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def records_sha(votes) -> str:
    return hashlib.sha256(
        json.dumps(votes, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_repo = os.path.dirname(here)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=default_repo)
    ap.add_argument("--dump", default=os.path.expanduser("~/sejm-dump"))
    ap.add_argument("--out", default=os.path.expanduser("~/cf-dump"))
    args = ap.parse_args()

    sys.path.insert(0, args.repo)
    import seed_rule  # noqa: E402

    ids_path = os.path.join(args.repo, "docs", "population", "ids-term10.txt")
    dump_path = os.path.join(args.dump, "divisions_3_10.jsonl")
    os.makedirs(args.out, exist_ok=True)

    ids = set()
    with open(ids_path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                t, s, v = line.strip().split(":")
                ids.add(f"term{t}-s{s}-v{v}")

    divisions = {}
    with open(dump_path, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            item_id = f"term{d['term']}-s{d['sitting']}-v{d['votingNumber']}"
            if item_id in ids:
                divisions[item_id] = d
    print(f"loaded {len(divisions)} term-10 divisions", file=sys.stderr)

    rng = random.Random(SEED)
    item_ids = sorted(divisions)
    rng.shuffle(item_ids)

    # classify flip pools by seed margin
    pools = {k: [] for k in ("flip_narrow", "flip_close", "flip_wide")}
    for item_id in item_ids:
        d = divisions[item_id]
        m = seed_rule.compute_metric(d)
        sr = m["seed_rule"]
        if sr["tie"] or sr["method"] != "majority":
            continue  # ties: no clean flip; excluded (see Counterfactual.lean)
        seed_margin = abs(sr["margin"])
        if seed_margin <= 5:
            pools["flip_narrow"].append(item_id)
        elif seed_margin <= 50:
            pools["flip_close"].append(item_id)
        else:
            pools["flip_wide"].append(item_id)

    chosen = {}
    taken = set()
    for b, quota in (("flip_narrow", QUOTA["flip_narrow"]),
                     ("flip_close", QUOTA["flip_close"]),
                     ("flip_wide", QUOTA["flip_wide"])):
        take = pools[b][:quota]
        for i in take:
            chosen[i] = ("flip", b)
            taken.add(i)
    rest = [i for i in item_ids if i not in taken]
    for i in rest[:QUOTA["reorder"]]:
        chosen[i] = ("reorder", None)
        taken.add(i)
    rest = [i for i in item_ids if i not in taken]
    for i in rest[:QUOTA["club_label_pseudonymize"]]:
        chosen[i] = ("club_label_pseudonymize", None)
        taken.add(i)

    n_flip = sum(1 for v in chosen.values() if v[0] == "flip")
    n_reorder = sum(1 for v in chosen.values() if v[0] == "reorder")
    n_pseudo = sum(1 for v in chosen.values() if v[0] == "club_label_pseudonymize")
    print(f"chosen: flip={n_flip} reorder={n_reorder} "
          f"club_label_pseudonymize={n_pseudo}", file=sys.stderr)

    manifest_entries = []
    out_rows = []
    for item_id in sorted(chosen):
        kind, bucket = chosen[item_id]
        d = divisions[item_id]
        src_sha = records_sha(d["votes"])
        m0 = seed_rule.compute_metric(d)
        sr0 = m0["seed_rule"]
        gt0 = {"winner": sr0["winner"], "tie": sr0["tie"], "method": sr0["method"],
               "seed_margin": sr0["margin"]}
        votes = [dict(v) for v in d["votes"]]
        entry = {"item_id": item_id, "perturbation": kind,
                 "source_url": (f"https://api.sejm.gov.pl/sejm/term{d['term']}/"
                                f"votings/{d['sitting']}/{d['votingNumber']}"),
                 "records_sha256_original": src_sha,
                 "gt_original": gt0}
        dp = dict(d)
        dp["votes"] = votes

        if kind == "flip":
            cnt = Counter(v["club"] for v in votes)
            tracks = {c for c, n in cnt.items() if n >= seed_rule.MIN_TRACK_RECORDS}
            win_vote = "YES" if sr0["winner"] == "yes" else "NO"
            lose_vote = "NO" if win_vote == "YES" else "YES"
            eligible = [i for i, v in enumerate(votes)
                        if v["club"] in tracks and v["vote"] == win_vote]
            k = abs(sr0["margin"]) // 2 + 1
            if len(eligible) < k:
                print(f"SKIP flip {item_id}: eligible {len(eligible)} < k {k}",
                      file=sys.stderr)
                continue
            item_seed = stable_item_seed(SEED, item_id)
            pick_rng = random.Random(item_seed)
            flipped_idx = sorted(pick_rng.sample(eligible, k))
            for i in flipped_idx:
                votes[i]["vote"] = lose_vote
            entry["params"] = {"k_flipped": k, "from": win_vote, "to": lose_vote,
                               "flip_seed": item_seed,
                               "flipped_record_indices": flipped_idx}
            dp["votes"] = votes
            # headline counters recomputed from the modified records (the
            # original counters would no longer describe this division)
            tally = Counter(v["vote"] for v in votes)
            dp["yes"] = tally.get("YES", 0)
            dp["no"] = tally.get("NO", 0)
            dp["abstain"] = tally.get("ABSTAIN", 0)
            m1 = seed_rule.compute_metric(dp)
            sr1 = m1["seed_rule"]
            gt1 = {"winner": sr1["winner"], "tie": sr1["tie"], "method": sr1["method"],
                   "seed_margin": sr1["margin"]}
            assert gt1["winner"] != gt0["winner"], f"flip failed to flip: {item_id}"
            entry["gt_perturbed"] = gt1
            entry["bucket"] = bucket
            out_rows.append(dp)
        elif kind == "reorder":
            shuffle_seed = stable_item_seed(SEED, item_id)
            random.Random(shuffle_seed).shuffle(votes)
            entry["params"] = {"shuffle_seed": shuffle_seed}
            dp["votes"] = votes
            m1 = seed_rule.compute_metric(dp)
            sr1 = m1["seed_rule"]
            gt1 = {"winner": sr1["winner"], "tie": sr1["tie"], "method": sr1["method"],
                   "seed_margin": sr1["margin"]}
            assert gt1 == gt0, f"reorder changed GT: {item_id}"
            entry["gt_perturbed"] = gt1
            out_rows.append(dp)
        else:  # club_label_pseudonymize
            cnt = Counter(v["club"] for v in votes)
            order = sorted(cnt, key=lambda c: (-cnt[c], c))
            mapping = {c: f"K{i+1}" for i, c in enumerate(order)}
            for v in votes:
                v["club"] = mapping[v["club"]]
            entry["params"] = {"label_mapping": mapping}
            dp["votes"] = votes
            m1 = seed_rule.compute_metric(dp)
            sr1 = m1["seed_rule"]
            gt1 = {"winner": sr1["winner"], "tie": sr1["tie"], "method": sr1["method"],
                   "seed_margin": sr1["margin"]}
            assert gt1 == gt0, f"pseudonymize changed GT: {item_id}"
            entry["gt_perturbed"] = gt1
            out_rows.append(dp)

        entry["records_sha256_perturbed"] = records_sha(dp["votes"])
        manifest_entries.append(entry)

    jsonl_name = "divisions_cf.jsonl"
    jsonl_path = os.path.join(args.out, jsonl_name)
    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for dp in out_rows:
            fh.write(json.dumps(dp, ensure_ascii=False, sort_keys=True) + "\n")
    with open(os.path.join(args.out, "ids-cf.txt"), "w", encoding="utf-8") as fh:
        for dp in out_rows:
            fh.write(f"{dp['term']}:{dp['sitting']}:{dp['votingNumber']}\n")

    jsonl_sha = hashlib.sha256(open(jsonl_path, "rb").read()).hexdigest()

    # balance of perturbed GT (leakage-diagnostic input): a model answering
    # the modal perturbed outcome without reading would score this on flips
    perturbed_winner = Counter(e["gt_perturbed"]["winner"] for e in manifest_entries
                               if e["perturbation"] == "flip")

    manifest = {
        "kind": "sejmbench-counterfactual-spike",
        "issue": 15,
        "seed": SEED,
        "base_population": "ids-term10.txt (5,137; docs/population)",
        "synthetic_derived": True,
        "jsonl": {"name": jsonl_name, "sha256": jsonl_sha, "rows": len(out_rows)},
        "quotas": {k: {"requested": q,
                       "generated": (sum(1 for e in manifest_entries
                                         if e.get("bucket") == k) if k.startswith("flip")
                                     else sum(1 for e in manifest_entries
                                              if e["perturbation"] == k)),
                       "shortfall_reason": (SHORTFALL_REASON
                                            if (k.startswith("flip") and
                                                sum(1 for e in manifest_entries
                                                    if e.get("bucket") == k) < q)
                                            else None)}
                   for k, q in QUOTA.items()},
        "perturbed_gt_balance": dict(perturbed_winner),
        "gt_source": "seed_rule.compute_metric (repo seed_rule.py) on perturbed records",
        "notes": [
            "Records keep MP ids and names: the third arm is club-LABEL "
            "pseudonymization, not full anonymization (issue #15 review).",
            "Headline counters of flipped items are recomputed from the "
            "modified records; the original counters would be false.",
            "Per-item seeds are SHA-256-derived from (SEED, item_id) — "
            "stable across processes (hash() is salted).",
        ],
        "items": manifest_entries,
    }
    manifest_path = os.path.join(args.out, "manifest-cf.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
    manifest_sha = hashlib.sha256(open(manifest_path, "rb").read()).hexdigest()
    with open(os.path.join(args.out, "manifest-cf.sha256"), "w") as fh:
        fh.write(f"{manifest_sha}  manifest-cf.json\n")
        fh.write(f"{jsonl_sha}  {jsonl_name}\n")
    with open(os.path.join(args.out, "README-CF.md"), "w", encoding="utf-8") as fh:
        fh.write("""# Counterfactual spike set (issue #15) — SYNTHETIC DERIVED DATA

These records are DERIVED from the official Sejm API mirror by deterministic
perturbation (seed 20261027). They are NOT official votes: modified records
must never enter the benchmark corpus, the fixture manifest, or any accuracy
scorecard. Tracked separately per issue #15 (see DATA_LICENSE.md,
"Synthetic derived data"). Each item's provenance: original division
(source_url + records sha256), perturbation parameters, perturbed-records
sha256, and GT recomputed with the frozen seed_rule. The third arm is
club-LABEL pseudonymization (records keep MP ids and names).
""")
    print(f"WROTE {len(out_rows)} items to {args.out}", file=sys.stderr)
    print(f"jsonl sha256 {jsonl_sha}", file=sys.stderr)
    print(f"manifest sha256 {manifest_sha}", file=sys.stderr)


if __name__ == "__main__":
    main()
