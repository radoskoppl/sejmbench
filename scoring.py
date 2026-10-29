"""SejmBench harness scorer (issue #4) — deterministic offline scoring.

Separates model execution from scoring: `score` consumes saved submissions
(AGENTS.md format), never calls a model, never touches the network. Every
published number must be reproducible from saved artifacts, so all rules
here are fixed and deterministic:

Parse rules (item status):
  * `refusal`       — raw_output is null/empty/whitespace.
  * `parse_failure` — no JSON object extractable, or the JSON object lacks
                      the `winner` key, or `winner` is not a string.
  * `abstain`       — JSON parses, `winner` is a string outside {yes, no},
                      or an explicit {"abstain": true} marker is present
                      (the model declined the binary).
  * `scored`        — `winner` in {yes, no} (case-insensitive, normalized
                      to lowercase). Tracks are scored for these items only.

Layer 0.1 (winner): exact match against the seed rule (CODEBOOK §3, with
the tie-break convention). Abstain, parse failure, refusal and a missing
submission file all count as incorrect for headline accuracy (§9.4) and are
reported separately.

Layer 0.2 (tracks): per-item mean absolute deviation of yes_share and
polarization over the fixture's ground-truth tracks (seed_rule §2). MAE is
computed over items with a valid parsed answer (§8.6: status `scored`);
answer coverage is reported alongside. Track matching is by exact club
label. A ground-truth track missing from the answer counts as maximum
deviation (1.0 on both measures) — the reference prompt requires "exactly
the clubs with at least 5 active votes", so omitting a track is an
instruction violation, not a neutral gap. Extra model-side tracks are
recorded but not penalized (structural fidelity is reported separately as
n_exact_track_set / exact_track_set_rate). Non-numeric or out-of-[0,1]
values count as missing for that track. A `tracks` field that is not a
list does not invalidate the item — the winner is still scored and every
ground-truth track counts as missing. Duplicate club labels void that
club: it counts as missing and each duplicate entry is invalid.

Statistics (CODEBOOK §8): bootstrap 95% CIs (10,000 replicates, seed
20261027, percentile method, deterministic RNG); paired bootstrap for
comparisons over the shared fixture set; differences inside the CI are
not ranked. The same seed restarts per statistic, so every CI is
reproducible bit-for-bit.

Scorecard schema is documented and versioned in docs/scorecard-schema.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import random

SCHEMA_VERSION = "1.1"             # docs/scorecard-schema.md (review round 2026-10-28)
BENCHMARK_VERSION = "0.3"          # CODEBOOK version — the contract
METRIC_VERSION = "0.3"             # CODEBOOK §2/§3 metric schema
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20261027          # CODEBOOK §8.1
RANDOM_BASELINE_SEED = 20261027
MIN_CELL_COUNT = 20                # CODEBOOK §8.3
SCORED_LAYERS = ("0.1", "0.2")     # layer 1 stays unscorable until §10 freezes

# Exact CODEBOOK §5 reference prompt (agent track, v0.2). The hash of these
# bytes is the prompt_hash recorded in submissions (AGENTS.md) and scorecards.
REFERENCE_PROMPT = """You are analyzing a roll-call division (głosowanie imienne) of the Sejm
of the Republic of Poland. Each line below is one MP: club | name | vote,
where vote is YES / NO / ABSTAIN / ABSENT.

{VOTE_RECORDS}

Answer ONLY with a JSON object:
{
  "winner": "yes" | "no",
  "tracks": [
    {"club": "<label>", "yes_share": <float>, "polarization": <float>}
  ]
}
Rules:
- Include exactly the clubs with at least 5 active votes (YES/NO/ABSTAIN).
- yes_share = YES / (YES + NO + ABSTAIN) for that club.
- polarization = 1 - |YES - NO| / (YES + NO + ABSTAIN).
"""


def reference_prompt_hash() -> str:
    return hashlib.sha256(REFERENCE_PROMPT.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# fixtures / provenance
# --------------------------------------------------------------------------

def load_manifest(repo_root: str) -> dict:
    with open(os.path.join(repo_root, "fixtures", "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


def canonical_set_hash(manifest: dict, files=None) -> str:
    """sha256 over the sorted `file:sha256` lines of the fixture manifest."""
    entries = manifest["fixtures"]
    if files is not None:
        wanted = {os.path.basename(f) for f in files}
        entries = [e for e in entries if os.path.basename(e["file"]) in wanted]
    canon = "".join(f"{e['file']}:{e['sha256']}\n" for e in sorted(entries, key=lambda e: e["file"]))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def load_fixture(repo_root: str, name: str, manifest: dict) -> dict:
    """Load one fixture by manifest entry (name with or without fixtures/)."""
    entry = next(
        (e for e in manifest["fixtures"] if os.path.basename(e["file"]) == os.path.basename(name)),
        None,
    )
    if entry is None:
        raise ValueError(f"fixture not in manifest: {name}")
    path = os.path.join(repo_root, entry["file"])
    with open(path, "rb") as fh:
        blob = fh.read()
    if hashlib.sha256(blob).hexdigest() != entry["sha256"]:
        raise ValueError(f"fixture sha256 mismatch: {entry['file']}")
    return json.loads(blob.decode("utf-8"))


# --------------------------------------------------------------------------
# parse rules
# --------------------------------------------------------------------------

def _extract_json_object(text: str):
    """First balanced {...} object in the string, string-aware, or None."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except ValueError:
                        break
        start = text.find("{", start + 1)
    return None


def parse_answer(raw_output):
    """Apply the fixed parse rules. Returns (status, parsed_dict_or_None)."""
    if raw_output is None:
        return "refusal", None
    if isinstance(raw_output, dict):
        parsed = raw_output
    elif isinstance(raw_output, str):
        s = raw_output.strip()
        if not s:
            return "refusal", None
        try:
            candidate = json.loads(s)
        except ValueError:
            candidate = _extract_json_object(s)
        if not isinstance(candidate, dict):
            return "parse_failure", None
        parsed = candidate
    else:
        return "parse_failure", None

    if parsed.get("abstain") is True:
        return "abstain", parsed
    winner = parsed.get("winner")
    if winner is None or not isinstance(winner, str):
        return "parse_failure", parsed
    if winner.strip().lower() not in ("yes", "no"):
        return "abstain", parsed
    parsed["winner"] = winner.strip().lower()
    return "scored", parsed


def _usable_tracks(parsed) -> tuple[dict, int]:
    """{club: (yes_share, polarization)} from usable entries; (map, n_invalid)."""
    tracks = parsed.get("tracks")
    if not isinstance(tracks, list):
        # present but not a list: the structure is unusable, every ground-truth
        # track will count as missing (max deviation); one invalid entry recorded
        return {}, 1
    out, invalid, seen = {}, 0, set()
    for t in tracks:
        if not isinstance(t, dict) or not isinstance(t.get("club"), str):
            invalid += 1
            continue
        ys, pol = t.get("yes_share"), t.get("polarization")
        if not (isinstance(ys, (int, float)) and not isinstance(ys, bool) and 0.0 <= ys <= 1.0):
            invalid += 1
            continue
        if not (isinstance(pol, (int, float)) and not isinstance(pol, bool) and 0.0 <= pol <= 1.0):
            invalid += 1
            continue
        club = t["club"]
        if club in seen:  # duplicate label voids the club: it counts as
            invalid += 1  # missing (max deviation) via the normal path
            out.pop(club, None)
            continue
        seen.add(club)
        out[club] = (float(ys), float(pol))
    return out, invalid


# --------------------------------------------------------------------------
# item scoring
# --------------------------------------------------------------------------

def score_item(item: dict, division: dict, fixture_name: str) -> dict:
    """Score one submission item (one fixture) against the seed rule."""
    import seed_rule

    status, parsed = parse_answer(item.get("raw_output"))
    metric = seed_rule.compute_metric(division)
    gt_winner = metric["seed_rule"]["winner"]
    gt_tie = metric["seed_rule"]["tie"]
    gt_tracks = metric["tracks"]

    pred_winner: str | None = None
    if status == "scored" and parsed is not None:
        pred_winner = parsed["winner"]
    correct = 1 if (pred_winner is not None and pred_winner == gt_winner) else 0

    layer02 = None
    if status == "scored" and pred_winner is not None:
        pred, invalid = _usable_tracks(parsed)
        devs_ys, devs_pol, matched = [], [], 0
        missing = sorted(c for c in gt_tracks if c not in pred)
        for club, gt in sorted(gt_tracks.items()):
            if club in pred:
                ys, pol = pred[club]
                devs_ys.append(abs(ys - gt["yes_share"]))
                devs_pol.append(abs(pol - gt["polarization"]))
                matched += 1
            else:  # instruction violation: max deviation, deterministic
                devs_ys.append(1.0)
                devs_pol.append(1.0)
        extra = sorted(c for c in pred if c not in gt_tracks)
        mae_ys = sum(devs_ys) / len(devs_ys) if devs_ys else None
        mae_pol = sum(devs_pol) / len(devs_pol) if devs_pol else None
        layer02 = {
            "n_tracks_gt": len(gt_tracks),
            "n_matched": matched,
            "n_missing": len(missing),
            "n_extra": len(extra),
            "missing_clubs": missing,
            "extra_clubs": extra,
            "n_invalid_entries": invalid,
            "mae_yes_share": mae_ys,
            "mae_polarization": mae_pol,
        }

    return {
        "fixture": fixture_name,
        "status": status,
        "layer0_1": {"pred": pred_winner, "gt": gt_winner, "gt_tie": gt_tie,
                     "correct": correct},
        "layer0_2": layer02,
        "abstain_marker": bool(parsed.get("abstain")) if isinstance(parsed, dict) else False,
    }


# --------------------------------------------------------------------------
# statistics (deterministic)
# --------------------------------------------------------------------------

def bootstrap_ci(values, replicates: int = BOOTSTRAP_REPLICATES, seed: int = BOOTSTRAP_SEED):
    """Percentile bootstrap 95% CI of the mean. Deterministic (§8.1)."""
    values = list(values)
    n = len(values)
    if n == 0:
        return None, None, None
    rng = random.Random(seed)
    means = []
    for _ in range(replicates):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(0.025 * replicates)]
    hi = means[min(replicates - 1, int(0.975 * replicates))]
    return sum(values) / n, lo, hi


def paired_bootstrap(diffs, replicates: int = BOOTSTRAP_REPLICATES, seed: int = BOOTSTRAP_SEED):
    """Paired bootstrap CI of the mean of per-item differences (§8.2)."""
    return bootstrap_ci(diffs, replicates, seed)


def _fmt_ci(stat, lo=None, hi=None):
    """Format 'stat [lo, hi]'; point estimate only when the CI is missing."""
    if stat is None:
        return "n/a"
    if lo is None or hi is None:
        return f"{stat:.4f}"
    return f"{stat:.4f} [{lo:.4f}, {hi:.4f}]"


# --------------------------------------------------------------------------
# submission loading
# --------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_submission_files(paths) -> tuple[dict, list]:
    """Load AGENTS.md submission files keyed by their `fixture` basename."""
    items, problems = {}, []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except ValueError as exc:
                problems.append(f"{p}: invalid JSON ({exc})")
                continue
        name = data.get("fixture")
        if not name:
            problems.append(f"{p}: missing 'fixture' field")
            continue
        key = os.path.basename(name)
        if key in items:
            problems.append(f"{p}: duplicate submission for fixture {key}")
            continue
        data["_path"] = p
        items[key] = data
    return items, problems


def validate_submission_item(data: dict) -> list:
    """AGENTS.md contract checks (results-only format)."""
    errs = []
    if str(data.get("temperature")) not in ("0", "0.0"):
        errs.append(f"temperature must be 0, got {data.get('temperature')!r}")
    for field in ("model", "date", "prompt_hash", "declared_cutoff"):
        if not data.get(field):
            errs.append(f"missing required field: {field}")
    if data.get("prompt_hash") and data["prompt_hash"] != reference_prompt_hash():
        errs.append(f"prompt_hash mismatch: {data.get('prompt_hash')} != {reference_prompt_hash()}")
    if "raw_output" not in data:
        errs.append("missing raw_output")
    return errs


# --------------------------------------------------------------------------
# scorecard assembly
# --------------------------------------------------------------------------

def _counts_by_status(statuses):
    return {
        "n_scored": sum(1 for s in statuses if s == "scored"),
        "n_abstained": sum(1 for s in statuses if s == "abstain"),
        "n_parse_failures": sum(1 for s in statuses if s == "parse_failure"),
        "n_refusals": sum(1 for s in statuses if s == "refusal"),
        "n_missing_files": sum(1 for s in statuses if s == "missing"),
    }


def build_scorecard(fixtures: dict, items: dict, problems: list, meta: dict) -> dict:
    """Assemble the scorecard for one submission over a fixture set.

    `fixtures`: {basename: division dict} for the set; `items`: submission
    files keyed by fixture basename; `meta`: identity/contamination fields.
    """
    names = sorted(fixtures)
    unknown = sorted(set(items) - set(names))
    if unknown:  # records outside the set are contract violations, not gaps
        problems.extend(f"unknown fixture (not in the set): {u}" for u in unknown)
    per_item, statuses = [], {}
    for name in names:
        data = items.get(name)
        if data is None:
            statuses[name] = "missing"
            per_item.append({
                "fixture": name, "status": "missing",
                "exclusion_reason": "no submission file for fixture",
                "layer0_1": {"pred": None, "gt": None, "gt_tie": None, "correct": 0},
                "layer0_2": None,
            })
            continue
        errs = validate_submission_item(data)
        if errs:
            problems.extend(f"{name}: {e}" for e in errs)
        entry = score_item(data, fixtures[name], name)
        entry["submission_file"] = os.path.relpath(data["_path"], meta.get("repo_root") or ".")
        entry["submission_sha256"] = (_sha256_file(data["_path"])
                                      if os.path.exists(data["_path"]) and not
                                      data["_path"].startswith("<") else None)
        statuses[name] = entry["status"]
        per_item.append(entry)

    counts = _counts_by_status(statuses.values())
    n_total = len(names)
    n_ties = sum(1 for it in per_item if it["layer0_1"].get("gt_tie") is True)
    exact_set = sum(1 for it in per_item if it["layer0_2"] and it["layer0_2"]["n_missing"] == 0
                    and it["layer0_2"]["n_extra"] == 0 and it["layer0_2"]["n_invalid_entries"] == 0)
    correct = [it["layer0_1"]["correct"] for it in per_item]
    acc, acc_lo, acc_hi = bootstrap_ci(correct)

    mae_ys_vals = [it["layer0_2"]["mae_yes_share"] for it in per_item
                   if it["layer0_2"] and it["layer0_2"]["mae_yes_share"] is not None]
    mae_pol_vals = [it["layer0_2"]["mae_polarization"] for it in per_item
                    if it["layer0_2"] and it["layer0_2"]["mae_polarization"] is not None]
    ys_stat = bootstrap_ci(mae_ys_vals) if mae_ys_vals else (None, None, None)
    pol_stat = bootstrap_ci(mae_pol_vals) if mae_pol_vals else (None, None, None)
    n_scored = counts["n_scored"]

    card = {
        "schema": f"sejmbench.scorecard/{SCHEMA_VERSION}",
        "scorecard_version": SCHEMA_VERSION,
        "benchmark_version": meta.get("benchmark_version", "0.3"),
        "metric_version": meta.get("metric_version", "0.3"),
        "harness_version": meta.get("harness_version"),
        "set": meta["set"],
        "set_hash": meta["set_hash"],
        "fixtures": [{"file": meta["fixture_entries"][n]["file"],
                      "sha256": meta["fixture_entries"][n]["sha256"]} for n in names],
        "model": meta["model"],
        "submission": meta["submission"],
        "prompt": {"hash": reference_prompt_hash(), "template": REFERENCE_PROMPT},
        "evaluation_date": meta["evaluation_date"],
        "contamination": meta["contamination"],
        "token_usage": meta.get("token_usage"),
        "cost_estimate": meta.get("cost_estimate"),
        "layers": {
            "0.1": {
                "n_total": n_total, **counts,
                "n_ties": n_ties,
                "accuracy": acc, "ci95": [acc_lo, acc_hi],
                "bootstrap": {"replicates": BOOTSTRAP_REPLICATES, "seed": BOOTSTRAP_SEED},
            },
            "0.2": {
                "n_total": n_total,
                "n_scored": n_scored,
                "answer_coverage": (n_scored / n_total) if n_total else None,
                "n_exact_track_set": exact_set,
                "exact_track_set_rate": (exact_set / n_scored) if n_scored else None,
                "mae_yes_share": ys_stat[0], "ci95_yes_share": [ys_stat[1], ys_stat[2]],
                "mae_polarization": pol_stat[0], "ci95_polarization": [pol_stat[1], pol_stat[2]],
                "bootstrap": {"replicates": BOOTSTRAP_REPLICATES, "seed": BOOTSTRAP_SEED},
            },
        },
        "items": per_item,
        "problems": problems,
        "generated_by": f"sejmbench scorer (scorecard schema {SCHEMA_VERSION})",
    }
    return card


SCORECARD_REQUIRED_KEYS = (
    "schema", "scorecard_version", "benchmark_version", "metric_version",
    "harness_version", "set", "set_hash", "fixtures", "model", "prompt",
    "evaluation_date", "contamination", "layers", "items",
)


def validate_scorecard(card: dict, expected_set_hash: str | None = None,
                       expected_fixtures: list | None = None) -> list:
    """Schema validation (CI gate). Returns a list of problems (empty = valid).

    `expected_set_hash` / `expected_fixtures` bind the scorecard to the
    manifest actually on disk; the CI gates always pass both.
    """
    errs = []
    for key in SCORECARD_REQUIRED_KEYS:
        if key not in card:
            errs.append(f"missing key: {key}")
    if card.get("schema") != f"sejmbench.scorecard/{SCHEMA_VERSION}":
        errs.append(f"unknown schema: {card.get('schema')!r}")
    if card.get("scorecard_version") != SCHEMA_VERSION:
        errs.append(f"scorecard_version {card.get('scorecard_version')!r} != {SCHEMA_VERSION!r}")
    if card.get("benchmark_version") != BENCHMARK_VERSION:
        errs.append(f"benchmark_version {card.get('benchmark_version')!r} != current "
                    f"contract {BENCHMARK_VERSION!r}")
    if card.get("metric_version") != METRIC_VERSION:
        errs.append(f"metric_version {card.get('metric_version')!r} != current "
                    f"contract {METRIC_VERSION!r}")
    if card.get("prompt", {}).get("hash") != reference_prompt_hash():
        errs.append("prompt hash mismatch")
    if expected_set_hash is not None and card.get("set_hash") != expected_set_hash:
        errs.append("set_hash does not match the canonical hash of the manifest on disk")
    if expected_fixtures is not None:
        got = sorted(({"file": f["file"], "sha256": f["sha256"]} for f in card.get("fixtures", [])),
                     key=lambda x: x["file"])
        want = sorted(({"file": e["file"], "sha256": e["sha256"]} for e in expected_fixtures),
                      key=lambda x: x["file"])
        if got != want:
            errs.append("fixtures list does not match the manifest (files or sha256)")
    l01 = card.get("layers", {}).get("0.1", {})
    counted = sum(l01.get(k, 0) for k in
                  ("n_scored", "n_abstained", "n_parse_failures", "n_refusals", "n_missing_files"))
    if l01 and counted != l01.get("n_total"):
        errs.append(f"layer 0.1 counts sum to {counted}, n_total={l01.get('n_total')}")
    for it in card.get("items", []):
        if "status" not in it or "layer0_1" not in it:
            errs.append(f"item missing status/layer0_1: {it.get('fixture')}")
    return errs


# --------------------------------------------------------------------------
# baselines (same harness, deterministic; no model calls)
# --------------------------------------------------------------------------

def baseline_items(which: str, fixtures: dict, manifest: dict):
    """Non-LLM baseline answers in the AGENTS.md item shape.

    - majority-class: always "yes" (the modal winner class in the Sejm);
      tracks: yes_share 1.0, polarization 0.0 (unanimous yes).
    - random: seeded RNG (RANDOM_BASELINE_SEED) over fixture order
      (sorted names); winner fair coin, shares uniform [0,1).
    carry_last / kNN over titles need division history and are NOT
    computable on an isolated fixture set — they enter the leaderboard
    only from the corpus-backed runs (separate, harness 0.4.2 re-run).
    """
    rng = random.Random(RANDOM_BASELINE_SEED)
    items = {}
    for name in sorted(fixtures):
        if which == "majority-class":
            raw = {"winner": "yes",
                   "tracks": [{"club": c, "yes_share": 1.0, "polarization": 0.0}
                              for c in sorted(_gt_clubs(fixtures[name]))]}
        elif which == "random":
            raw = {"winner": rng.choice(["yes", "no"]),
                   "tracks": [{"club": c, "yes_share": round(rng.random(), 4),
                               "polarization": round(rng.random(), 4)}
                              for c in sorted(_gt_clubs(fixtures[name]))]}
        else:
            raise ValueError(f"unknown baseline: {which}")
        items[name] = {
            "model": f"baseline:{which}", "date": "n/a (deterministic baseline)",
            "temperature": 0, "raw_output": raw, "fixture": name,
            "prompt_hash": reference_prompt_hash(), "declared_cutoff": "n/a (non-model baseline)",
            "_path": f"<generated:{which}>",
        }
    return items


def _gt_clubs(division) -> list:
    import seed_rule
    return list(seed_rule.compute_metric(division)["tracks"].keys())


def baseline_meta(which: str, set_name: str, manifest: dict, harness_version: str) -> dict:
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "metric_version": METRIC_VERSION,
        "harness_version": harness_version,
        "set": set_name,
        "set_hash": canonical_set_hash(manifest),
        "fixture_entries": {os.path.basename(e["file"]): e for e in manifest["fixtures"]},
        "model": {
            "id": f"baseline:{which}",
            "provider": "none (deterministic harness baseline)",
            "revision": "n/a",
            "identity_mutable_alias": False,
            "call_date": "n/a",
            "decoding": {"temperature": 0},
        },
        "submission": {"kind": "baseline",
                       "files": [],
                       "note": "predictions generated in-harness (deterministic), stored in items"},
        "evaluation_date": "2026-10-28",
        "contamination": {"declared_cutoff": "n/a (non-model baseline)",
                          "temporal_holdout_applied": False},
        "token_usage": {"input_tokens": 0, "output_tokens": 0},
        "cost_estimate": {"value": 0.0, "currency": "USD", "note": "no model calls"},
    }


# --------------------------------------------------------------------------
# rescore / leaderboard
# --------------------------------------------------------------------------

def shared_fixtures(a: dict, b: dict) -> tuple[list, list]:
    """Names present in both scorecards with IDENTICAL fixture sha256.

    Same name with a different hash means different data — such items are
    excluded from pairing and reported back to the caller.
    """
    sha_a = {os.path.basename(f["file"]): f["sha256"] for f in a["fixtures"]}
    sha_b = {os.path.basename(f["file"]): f["sha256"] for f in b["fixtures"]}
    overlap = set(sha_a) & set(sha_b)
    shared = sorted(n for n in overlap if sha_a[n] == sha_b[n])
    mismatched = sorted(n for n in overlap if sha_a[n] != sha_b[n])
    return shared, mismatched


def rescore(card: dict, repo_root: str, manifest: dict) -> dict:
    """Rebuild a scorecard from its referenced artifacts (CI reproduction)."""
    names = [os.path.basename(f["file"]) for f in card["fixtures"]]
    fixtures = {n: load_fixture(repo_root, n, manifest) for n in names}
    meta = dict(card)
    meta["set_hash"] = canonical_set_hash(manifest, names)
    meta["fixture_entries"] = {os.path.basename(e["file"]): e for e in manifest["fixtures"]}

    if card.get("submission", {}).get("kind") == "baseline":
        which = card["model"]["id"].split(":", 1)[1]
        items = baseline_items(which, fixtures, manifest)
        problems = []
    else:
        paths = [os.path.join(repo_root, f["path"]) for f in card["submission"]["files"]]
        items, problems = load_submission_files(paths)
    meta["repo_root"] = repo_root
    return build_scorecard(fixtures, items, problems, meta)


def _diff_paths(a, b, prefix=""):
    """Leaf paths where two JSON structures differ (for rescore reports)."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out.extend(_diff_paths(a.get(k), b.get(k), f"{prefix}.{k}"))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{prefix}: list length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(_diff_paths(x, y, f"{prefix}[{i}]"))
    elif a != b:
        out.append(f"{prefix}: committed={a!r} rescored={b!r}")
    return out


def rescore_matches(card: dict, rebuilt: dict) -> list:
    """Full-canonical comparison of a committed scorecard against its rescore.

    Every field is compared, not just numbers: provenance text, hashes,
    model identity and the prompt template must all survive the rescore.
    The `problems` list is compared by length only — its messages may embed
    paths that differ legitimately between the original run and the rescore;
    `rescore-check` separately rejects any committed problems.
    """
    a = {k: v for k, v in card.items() if k != "problems"}
    b = {k: v for k, v in rebuilt.items() if k != "problems"}
    mismatches = []
    if len(card.get("problems", [])) != len(rebuilt.get("problems", [])):
        mismatches.append(f"problems: committed n={len(card.get('problems', []))} "
                          f"rescored n={len(rebuilt.get('problems', []))}")
    if json.dumps(a, sort_keys=True, ensure_ascii=False) != json.dumps(b, sort_keys=True, ensure_ascii=False):
        diffs = _diff_paths(a, b)
        mismatches.extend(diffs[:10] if diffs else ["structures differ"])
    return mismatches


def leaderboard_rows(scorecards: list) -> list:
    rows = []
    for card in sorted(scorecards, key=lambda c: (c["model"]["id"], c["set"])):
        l01, l02 = card["layers"]["0.1"], card["layers"]["0.2"]
        rows.append({
            "model": card["model"]["id"],
            "provider": card["model"].get("provider"),
            "set": card["set"],
            "n": l01["n_total"],
            "accuracy": l01["accuracy"],
            "accuracy_ci95": l01["ci95"],
            "mae_yes_share": l02["mae_yes_share"],
            "ci95_yes_share": l02["ci95_yes_share"],
            "mae_polarization": l02["mae_polarization"],
            "ci95_polarization": l02["ci95_polarization"],
            "declared_cutoff": card["contamination"]["declared_cutoff"],
            "evaluation_date": card["evaluation_date"],
            "baseline": card["submission"].get("kind") == "baseline",
        })
    return rows
