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

import gzip
import hashlib
import json
import os
import random

SCHEMA_VERSION = "1.4"             # docs/scorecard-schema.md (v1.4: margin_buckets block, issue #14)
BENCHMARK_VERSION = "0.3"          # CODEBOOK version — the contract
METRIC_VERSION = "0.3"             # CODEBOOK §2/§3 metric schema
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20261027          # CODEBOOK §8.1
RANDOM_BASELINE_SEED = 20261027
MIN_CELL_COUNT = 20                # CODEBOOK §8.3
SCORED_LAYERS = ("0.1", "0.2")     # layer 1 stays unscorable until §10 freezes

# Exact CODEBOOK §5 reference prompt (agent track, v0.3). The hash of these
# bytes is the prompt_hash recorded in submissions (AGENTS.md) and scorecards.
# v0.3: names NO_VOTE explicitly, separates the >=5-record track threshold from
# the >=5-active-votes cohesion threshold, states the YES == NO tie convention.
REFERENCE_PROMPT = """You are analyzing a roll-call division (głosowanie imienne) of the Sejm
of the Republic of Poland. Each line below is one MP: club | name | vote,
where vote is YES / NO / ABSTAIN / ABSENT — or NO_VOTE in term-3-era data.

{VOTE_RECORDS}

Answer ONLY with a JSON object:
{
  "winner": "yes" | "no",
  "tracks": [
    {"club": "<label>", "yes_share": <float>, "polarization": <float>}
  ]
}
Rules:
- A club counts toward the winner if it appears in at least 5 vote records.
- Active votes are YES / NO / ABSTAIN; ABSENT and NO_VOTE never decide an outcome.
- winner: "yes" if total active YES exceeds total active NO, "no" if active NO
  exceeds active YES; if they are equal (including 0:0), report "yes"
  (earlier-seed convention).
- Include in "tracks" exactly the clubs with at least 5 active votes.
- yes_share = YES / (YES + NO + ABSTAIN) for that club.
- polarization = 1 - |YES - NO| / (YES + NO + ABSTAIN).
"""


def reference_prompt_hash() -> str:
    return hashlib.sha256(REFERENCE_PROMPT.encode("utf-8")).hexdigest()


# Corpus-run variant (issue #12 / 9A): the compact divisions dump drops MP
# names, so each line is `club | vote`. Names carry no information for the
# task (tracks and winner are club-level), but the deviation must be explicit
# and versioned — this template has its own pinned hash.
REFERENCE_PROMPT_CORPUS = """You are analyzing a roll-call division (głosowanie imienne) of the Sejm
of the Republic of Poland. Each line below is one MP: club | vote,
where vote is YES / NO / ABSTAIN / ABSENT — or NO_VOTE in term-3-era data.

{VOTE_RECORDS}

Answer ONLY with a JSON object:
{
  "winner": "yes" | "no",
  "tracks": [
    {"club": "<label>", "yes_share": <float>, "polarization": <float>}
  ]
}
Rules:
- A club counts toward the winner if it appears in at least 5 vote records.
- Active votes are YES / NO / ABSTAIN; ABSENT and NO_VOTE never decide an outcome.
- winner: "yes" if total active YES exceeds total active NO, "no" if active NO
  exceeds active YES; if they are equal (including 0:0), report "yes"
  (earlier-seed convention).
- Include in "tracks" exactly the clubs with at least 5 active votes.
- yes_share = YES / (YES + NO + ABSTAIN) for that club.
- polarization = 1 - |YES - NO| / (YES + NO + ABSTAIN).
"""


def corpus_reference_prompt_hash() -> str:
    return hashlib.sha256(REFERENCE_PROMPT_CORPUS.encode("utf-8")).hexdigest()


# Accepted prompt versions: hash -> exact template. A scorecard must name one
# of these; silent prompt edits fail validation.
KNOWN_PROMPTS = {
    reference_prompt_hash(): REFERENCE_PROMPT,
    corpus_reference_prompt_hash(): REFERENCE_PROMPT_CORPUS,
}

# Issue #12: reproducible model identity. Required on model scorecards
# (baseline cards exempt); "unknown" is an allowed VALUE, the KEY is not.
MODEL_IDENTITY_REQUIRED = ("weights_sha256", "tokenizer", "quantization",
                           "runtime", "runtime_version", "context_length")


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
    # Partial abstention (issue #9A design): the item answers the winner task
    # but explicitly declines the numeric tracks task (e.g. typed-decision
    # models that cannot emit per-club estimates). The winner still scores;
    # layer 0.2 is reported as abstained (coverage), never penalized as an
    # instruction violation. Additive rule; absent marker = old behaviour.
    if parsed.get("tracks_abstained"):
        parsed["tracks_abstained"] = True
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
    # Corpus-backed sets carry a precomputed GT (`__gt__`, built by
    # scripts/build_corpus_gt.py); fixture sets compute the metric on the fly.
    metric = division.get("__gt__") or seed_rule.compute_metric(division)
    gt_winner = metric["seed_rule"]["winner"]
    gt_tie = metric["seed_rule"]["tie"]
    gt_tracks = metric["tracks"]

    pred_winner: str | None = None
    if status == "scored" and parsed is not None:
        pred_winner = parsed["winner"]
    correct = 1 if (pred_winner is not None and pred_winner == gt_winner) else 0

    layer02 = None
    if status == "scored" and pred_winner is not None:
        if parsed and parsed.get("tracks_abstained"):
            # explicit partial abstention: winner answered, tracks declined
            layer02 = {"n_tracks_gt": len(gt_tracks), "n_matched": 0,
                       "n_missing": len(gt_tracks), "n_extra": 0,
                       "missing_clubs": sorted(gt_tracks), "extra_clubs": [],
                       "n_invalid_entries": 0,
                       "mae_yes_share": None, "mae_polarization": None,
                       "tracks_abstained": True}
            return {
                "fixture": fixture_name,
                "status": status,
                "layer0_1": {"pred": pred_winner, "gt": gt_winner,
                             "gt_tie": gt_tie, "correct": correct},
                "layer0_2": layer02,
                **{k: item[k] for k in ("input_tokens", "context_overflow",
                                        "inference_attempts") if k in item},
                "abstain_marker": False,
            }
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
        # issue #12 operational fields, passed through from the raw response
        **{k: item[k] for k in ("input_tokens", "context_overflow",
                                "inference_attempts") if k in item},
        "abstain_marker": bool(parsed.get("abstain")) if isinstance(parsed, dict) else False,
    }


# --------------------------------------------------------------------------
# margin buckets (issue #14; CODEBOOK §13, frozen 2026-11-08, before model 2)
# --------------------------------------------------------------------------

MARGIN_BUCKETS = ("tie", "narrow", "close", "wide")


def margin_bucket(margin_all):
    """CODEBOOK §13 pre-registered buckets. m = |yes − no| over API headline
    counts (the GT `margin_all` field; same construct as CODEBOOK §11).

    tie: m == 0 · narrow: 1 ≤ m ≤ 5 · close: 6 ≤ m ≤ 50 · wide: m ≥ 51.
    These names overlap §11's stratification buckets with different ranges —
    §13 governs model reporting only, §11 fixture stratification only.
    """
    if margin_all is None:
        return None
    m = abs(int(margin_all))
    if m == 0:
        return "tie"
    if m <= 5:
        return "narrow"
    if m <= 50:
        return "close"
    return "wide"


def margin_bucket_stats(per_item: list, margins: dict) -> dict:
    """Per-bucket winner accuracy (layers 0.1) + margin-macro.

    Same denominator rule as the headline accuracy: excluded items leave the
    denominator; missing/abstained/failed items count as incorrect. Items
    whose GT carries no `margin_all` (partial/synthetic GT) are counted in
    the explicit `n_no_margin` field, not in any bucket. Macro = unweighted
    mean over the four buckets (buckets with n = 0 excluded); weights
    pre-registered in CODEBOOK §13.
    """
    vals = {b: [] for b in MARGIN_BUCKETS}
    n_scored = {b: 0 for b in MARGIN_BUCKETS}
    n_no_margin = 0
    for it in per_item:
        b = margin_bucket(margins.get(it["fixture"]))
        if b is None:
            if it["status"] != "excluded":
                n_no_margin += 1
            continue
        if it["status"] == "excluded":
            continue
        vals[b].append(it["layer0_1"]["correct"] or 0)
        if it["status"] == "scored":
            n_scored[b] += 1
    buckets, accs = {}, []
    for b in MARGIN_BUCKETS:
        v = vals[b]
        if v:
            acc, lo, hi = bootstrap_ci(v)
            buckets[b] = {"n": len(v), "n_scored": n_scored[b],
                          "accuracy": acc, "ci95": [lo, hi]}
            accs.append(acc)
        else:
            buckets[b] = {"n": 0, "n_scored": n_scored[b],
                          "accuracy": None, "ci95": [None, None]}
    return {"definition": "sejmbench.margin-buckets/1.0 (CODEBOOK §13)",
            "buckets": buckets,
            "n_no_margin": n_no_margin,
            "margin_macro": (sum(accs) / len(accs)) if accs else None}


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
    if data.get("prompt_hash") and data["prompt_hash"] not in KNOWN_PROMPTS:
        errs.append(f"prompt_hash is not a known versioned prompt: {data.get('prompt_hash')}")
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
        "n_excluded_ineligible": sum(1 for s in statuses if s == "excluded"),
    }


# --------------------------------------------------------------------------
# corpus sets + temporal holdout (issues #11/#5, schema 1.2/1.3)
# --------------------------------------------------------------------------

CORPUS_SETS = {"full": ("ids-full-corpus.txt", "gt-full.jsonl.gz"),
               "term10": ("ids-term10.txt", "gt-term10.jsonl.gz")}


def corpus_fixtures(repo_root: str, set_name: str):
    """Corpus set loader: GT stand-ins + the frozen population block (issue #11).

    Shared by the CLI (--set full|term10) and rescore so a committed corpus
    scorecard is rebuilt from exactly the same on-disk artifacts.
    """
    pop_dir = os.path.join(repo_root, "docs", "population")
    ids_file, gt_file = CORPUS_SETS[set_name]
    ids_path, gt_path = os.path.join(pop_dir, ids_file), os.path.join(pop_dir, gt_file)
    if not (os.path.exists(ids_path) and os.path.exists(gt_path)):
        raise SystemExit(f"corpus set '{set_name}' not built: run scripts/build_corpus_gt.py")
    ids = {("term%s-s%s-v%s.json") % tuple(line.strip().split(":"))
           for line in open(ids_path, encoding="utf-8") if line.strip()}
    fixtures, h = {}, hashlib.sha256()
    with gzip.open(gt_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            name = row["id"] + ".json"
            fixtures[name] = {"__gt__": row["metric"]}
            h.update(line.encode("utf-8"))
    if set(fixtures) != ids:
        raise SystemExit(f"{gt_file} does not match {ids_file} exactly — "
                         "population drift, refusing to score")
    population = {"set": set_name, "n": len(fixtures),
                  "ids_file": "docs/population/" + ids_file,
                  "ids_sha256": _sha256_file(ids_path),
                  "gt_sha256": h.hexdigest()}
    return fixtures, population


def gt_stream_sha256(path: str) -> str:
    """sha256 of the UNCOMPRESSED GT stream (the population gt_sha256)."""
    h = hashlib.sha256()
    with gzip.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fixture_key(name: str):
    """Map 'term10-s1-v10.json' to (10, 1, 10); None for non-corpus names."""
    base = name[:-5] if name.endswith(".json") else name
    try:
        t, s, v = base[len("term"):].split("-")
        return (int(t), int(s[1:]), int(v[1:]))
    except (ValueError, IndexError):
        return None


def load_post_ids(repo_root: str, cutoff: str, set_name: str) -> dict:
    """Load the committed post-cutoff ID list for a corpus set (issue #5).

    The split rule is frozen in CODEBOOK section 9; the lists are derived by
    scripts/temporal_split.py from the committed GT stream. Returns the
    cutoff, the repo-relative list path, its sha256 and the id set.
    """
    suffix = "" if set_name == "full" else "-" + set_name
    rel = "docs/population/ids-post-" + cutoff + suffix + ".txt"
    path = os.path.join(repo_root, rel)
    if not os.path.exists(path):
        raise SystemExit("temporal split list missing: " + rel +
                         " - run scripts/temporal_split.py --cutoff " + cutoff)
    post = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            t, s, v = line.split(":")
            post.add((int(t), int(s), int(v)))
    return {"cutoff": cutoff, "ids_post_file": rel,
            "ids_post_sha256": _sha256_file(path), "post_ids": post}


def _subset_l01(entries: list) -> dict:
    correct = [it["layer0_1"]["correct"] for it in entries]
    if not correct:
        return {"n": 0, "accuracy": None, "ci95": [None, None]}
    acc, lo, hi = bootstrap_ci(correct)
    return {"n": len(correct), "accuracy": acc, "ci95": [lo, hi]}


def _subset_l02(entries: list) -> dict:
    ys = [it["layer0_2"]["mae_yes_share"] for it in entries
          if it["layer0_2"] and it["layer0_2"]["mae_yes_share"] is not None]
    pol = [it["layer0_2"]["mae_polarization"] for it in entries
           if it["layer0_2"] and it["layer0_2"]["mae_polarization"] is not None]
    yst = bootstrap_ci(ys) if ys else (None, None, None)
    polst = bootstrap_ci(pol) if pol else (None, None, None)
    return {"n_scored": len(ys),
            "mae_yes_share": yst[0], "ci95_yes_share": [yst[1], yst[2]],
            "mae_polarization": polst[0], "ci95_polarization": [polst[1], polst[2]]}


def _temporal_block(per_item: list, temporal: dict) -> dict:
    """Partition scored items into pre/post-cutoff subsets (issue #5).

    Excluded items (zero-counter divisions) sit outside both subsets; every
    other item lands in exactly one. Subset statistics use the same
    bootstrap protocol as the headline layer blocks (seed 20261027).
    """
    post_ids = temporal["post_ids"]
    pre_items, post_items = [], []
    for it in per_item:
        if it.get("status") == "excluded":
            continue
        key = _fixture_key(it["fixture"])
        (post_items if key in post_ids else pre_items).append(it)
    return {"cutoff": temporal["cutoff"],
            "ids_post_file": temporal["ids_post_file"],
            "ids_post_sha256": temporal["ids_post_sha256"],
            "n_pre": len(pre_items), "n_post": len(post_items),
            "layers": {"0.1": {"pre": _subset_l01(pre_items), "post": _subset_l01(post_items)},
                       "0.2": {"pre": _subset_l02(pre_items), "post": _subset_l02(post_items)}}}


def _validate_temporal_split(card: dict, ts: dict) -> list:
    """Schema checks for the temporal_split block (issue #5)."""
    errs = []
    if card.get("set") == "public":
        errs.append("temporal_split is defined on corpus sets only")
        return errs
    for k in ("cutoff", "ids_post_file", "ids_post_sha256", "n_pre", "n_post", "layers"):
        if k not in ts:
            errs.append("temporal_split missing key: " + k)
    cut = ts.get("cutoff")
    if not (isinstance(cut, str) and len(cut) == 10 and cut[4] == "-" and cut[7] == "-"
            and all(c.isdigit() for i, c in enumerate(cut) if i not in (4, 7))):
        errs.append("temporal_split.cutoff must be an ISO date (YYYY-MM-DD)")
    v = ts.get("ids_post_sha256", "")
    if not (isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)):
        errs.append("temporal_split.ids_post_sha256 must be a sha256 hex digest")
    n_pre, n_post = ts.get("n_pre"), ts.get("n_post")
    if not (isinstance(n_pre, int) and isinstance(n_post, int) and n_pre >= 0 and n_post >= 0):
        errs.append("temporal_split.n_pre/n_post must be non-negative integers")
    else:
        non_excluded = sum(1 for it in card.get("items", []) if it.get("status") != "excluded")
        if n_pre + n_post != non_excluded:
            errs.append("temporal_split n_pre+n_post=%d != non-excluded items %d"
                        % (n_pre + n_post, non_excluded))
    if not card.get("contamination", {}).get("temporal_holdout_applied"):
        errs.append("temporal_split present but contamination.temporal_holdout_applied is not true")
    layers = ts.get("layers")
    if not isinstance(layers, dict) or "0.1" not in layers:
        errs.append("temporal_split.layers must carry the 0.1 subset stats")
    return errs


def _submission_paths_from_tar(card: dict, repo_root: str) -> tuple:
    """Per-item files absent: rescore from the committed raw tar instead.

    The tar (results/<dir>.raw.tar.gz) carries the run's own bytes; every
    file sha256 is verified against the card submission manifest, so a
    rescore never runs on substitute data. Missing tar or any mismatch is a
    hard error.
    """
    import tarfile
    import tempfile
    entries = card.get("submission", {}).get("files", [])
    if not entries:
        raise SystemExit("cannot rescore: empty submission file list")
    dirs = sorted({os.path.dirname(f["path"]) for f in entries})
    if len(dirs) != 1:
        raise SystemExit("cannot rescore: submission files span %d dirs; expected "
                         "a single results/<dir> layout" % len(dirs))
    tar_rel = dirs[0] + ".raw.tar.gz"
    tar_path = os.path.join(repo_root, tar_rel)
    if not os.path.exists(tar_path):
        raise SystemExit("cannot rescore: per-item files missing and " + tar_rel + " not found")
    tmp = tempfile.mkdtemp(prefix="sejmbench-rescore-")
    try:
        with tarfile.open(tar_path, "r:gz") as tf:
            members = tf.getmembers()
            # rewrite member names so the extracted layout mirrors the
            # repo-relative paths the card references (the tar was created
            # from inside results/)
            for m in members:
                parts = m.name.split("/", 1)
                if len(parts) == 2 and not m.name.startswith("results/"):
                    m.name = "results/" + m.name
            try:
                tf.extractall(tmp, members=members, filter="data")
            except TypeError:  # python < 3.11.4: no filter parameter
                tf.extractall(tmp, members=members)
    except tarfile.TarError as exc:
        raise SystemExit("cannot rescore: " + tar_rel + " unreadable: " + str(exc))
    out = []
    for f in entries:
        p = os.path.join(tmp, f["path"])
        if not os.path.exists(p):
            raise SystemExit("cannot rescore: " + f["path"] + " not present in " + tar_rel)
        if _sha256_file(p) != f.get("sha256"):
            raise SystemExit("cannot rescore: sha256 mismatch for " + f["path"] +
                             " vs " + tar_rel)
        out.append(p)
    return out, tmp


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
        entry_meta = meta["fixture_entries"][name]
        if entry_meta.get("layers", {}).get("0.1", True) is False:
            # zero-counter division: layer 0.1/0.2 not eligible (CODEBOOK §11);
            # an exclusion is not an incorrect answer — it leaves the denominators
            statuses[name] = "excluded"
            per_item.append({
                "fixture": name, "status": "excluded",
                "exclusion_reason": "layers 0.1/0.2 not eligible (zero-counter division)",
                "layer0_1": {"pred": None, "gt": None, "gt_tie": None, "correct": None},
                "layer0_2": None,
            })
            continue
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
        p = data["_path"]
        if p.startswith("<"):
            # in-harness generated answers (baselines): the marker itself is the
            # value - never CWD-dependent via relpath
            entry["submission_file"] = p
        else:
            entry["submission_file"] = os.path.relpath(p, meta.get("repo_root") or ".")
        entry["submission_sha256"] = (_sha256_file(p)
                                      if os.path.exists(p) and not
                                      p.startswith("<") else None)
        statuses[name] = entry["status"]
        per_item.append(entry)

    import seed_rule
    margins = {}
    for name in names:
        margins[name] = (fixtures[name].get("__gt__")
                         or seed_rule.compute_metric(fixtures[name])).get("margin_all")
    mb = margin_bucket_stats(per_item, margins)

    counts = _counts_by_status(statuses.values())
    n_total = len(names)
    n_eligible = n_total - counts["n_excluded_ineligible"]
    n_ties = sum(1 for it in per_item if it["layer0_1"].get("gt_tie") is True)
    exact_set = sum(1 for it in per_item if it["layer0_2"] and it["layer0_2"]["n_missing"] == 0
                    and it["layer0_2"]["n_extra"] == 0 and it["layer0_2"]["n_invalid_entries"] == 0)
    correct = [it["layer0_1"]["correct"] for it in per_item if it["status"] != "excluded"]
    acc, acc_lo, acc_hi = bootstrap_ci(correct)

    mae_ys_vals = [it["layer0_2"]["mae_yes_share"] for it in per_item
                   if it["layer0_2"] and it["layer0_2"]["mae_yes_share"] is not None]
    mae_pol_vals = [it["layer0_2"]["mae_polarization"] for it in per_item
                    if it["layer0_2"] and it["layer0_2"]["mae_polarization"] is not None]
    ys_stat = bootstrap_ci(mae_ys_vals) if mae_ys_vals else (None, None, None)
    pol_stat = bootstrap_ci(mae_pol_vals) if mae_pol_vals else (None, None, None)
    n_scored = counts["n_scored"]
    n_tracks_answered = sum(1 for it in per_item if it["layer0_2"]
                            and not it["layer0_2"].get("tracks_abstained"))
    n_tracks_abstained = sum(1 for it in per_item if it["layer0_2"]
                             and it["layer0_2"].get("tracks_abstained"))

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
        "prompt": ({"hash": corpus_reference_prompt_hash(), "template": REFERENCE_PROMPT_CORPUS}
                   if meta.get("prompt_variant") == "corpus"
                   else {"hash": reference_prompt_hash(), "template": REFERENCE_PROMPT}),
        "evaluation_date": meta["evaluation_date"],
        "contamination": meta["contamination"],
        "token_usage": meta.get("token_usage"),
        "cost_estimate": meta.get("cost_estimate"),
        "layers": {
            "0.1": {
                "n_total": n_total,
                "n_eligible": n_eligible,
                **counts,
                "n_ties": n_ties,
                "accuracy": acc, "ci95": [acc_lo, acc_hi],
                "margin_buckets": mb,
                "bootstrap": {"replicates": BOOTSTRAP_REPLICATES, "seed": BOOTSTRAP_SEED},
            },
            "0.2": {
                "n_total": n_total,
                "n_eligible": n_eligible,
                "n_scored": n_scored,
                "n_tracks_answered": n_tracks_answered,
                "n_tracks_abstained": n_tracks_abstained,
                "tracks_answer_coverage": (n_tracks_answered / n_eligible) if n_eligible else None,
                "answer_coverage": (n_scored / n_eligible) if n_eligible else None,
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
    if meta.get("population"):
        # corpus sets bind the scorecard to the frozen population (schema 1.2)
        card["population"] = meta["population"]
    if meta.get("operational"):
        card["operational"] = meta["operational"]
    if meta.get("temporal", {}).get("post_ids"):
        # temporal holdout subsets (issue #5, schema 1.3); the caller flips
        # contamination.temporal_holdout_applied when the split is applied
        card["temporal_split"] = _temporal_block(per_item, meta["temporal"])
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
    if card.get("prompt", {}).get("hash") not in KNOWN_PROMPTS:
        errs.append("prompt hash is not a known versioned prompt")
    elif card["prompt"].get("template") != KNOWN_PROMPTS[card["prompt"]["hash"]]:
        errs.append("prompt template does not match its pinned hash (silent edit)")
    if card.get("submission", {}).get("kind") == "model":
        ident = card.get("model", {}).get("identity")
        if not isinstance(ident, dict):
            errs.append("model scorecard must carry model.identity "
                        "(weights_sha256, tokenizer, quantization, runtime, "
                        "runtime_version, context_length) per issue #12")
        else:
            for k in MODEL_IDENTITY_REQUIRED:
                if k not in ident:
                    errs.append(f"model.identity missing key: {k}")
        if not card.get("operational", {}).get("retry_policy"):
            errs.append("model scorecard must declare operational.retry_policy "
                        "(fixed before the run; retries must never re-roll "
                        "for a better answer)")
    if expected_set_hash is not None and card.get("set_hash") != expected_set_hash:
        errs.append("set_hash does not match the canonical hash of the manifest on disk")
    if card.get("set") != "public":
        pop = card.get("population")
        if not isinstance(pop, dict):
            errs.append("corpus-set scorecard must carry a 'population' block "
                        "(n / ids_sha256 / gt_sha256) per schema 1.2")
        else:
            if not isinstance(pop.get("n"), int) or pop["n"] <= 0:
                errs.append("population.n must be a positive integer")
            for k in ("ids_sha256", "gt_sha256"):
                v = pop.get(k, "")
                if not (isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)):
                    errs.append(f"population.{k} must be a sha256 hex digest")
    if card.get("submission", {}).get("kind") == "model" and card.get("set") != "public":
        if "temporal_split" not in card:
            errs.append("corpus model scorecard must carry temporal_split "
                        "(CODEBOOK §9 rule 6 — enforce with --temporal-cutoff)")
    ts = card.get("temporal_split")
    if ts is not None:
        errs.extend(_validate_temporal_split(card, ts))
    if expected_fixtures is not None:
        got = sorted(({"file": f["file"], "sha256": f["sha256"]} for f in card.get("fixtures", [])),
                     key=lambda x: x["file"])
        want = sorted(({"file": e["file"], "sha256": e["sha256"]} for e in expected_fixtures),
                      key=lambda x: x["file"])
        if got != want:
            errs.append("fixtures list does not match the manifest (files or sha256)")
    l01 = card.get("layers", {}).get("0.1", {})
    counted = sum(l01.get(k, 0) for k in
                  ("n_scored", "n_abstained", "n_parse_failures", "n_refusals",
                   "n_missing_files", "n_excluded_ineligible"))
    if l01 and counted != l01.get("n_total"):
        errs.append(f"layer 0.1 counts sum to {counted}, n_total={l01.get('n_total')}")
    mb = l01.get("margin_buckets")
    if mb is not None:
        if set(mb.get("buckets", {})) != set(MARGIN_BUCKETS):
            errs.append(f"margin_buckets must carry exactly {list(MARGIN_BUCKETS)}")
        elif (sum(b["n"] for b in mb["buckets"].values())
              + mb.get("n_no_margin", 0)) != l01.get("n_eligible"):
            errs.append("margin_buckets n values (+ n_no_margin) do not sum "
                        "to layer 0.1 n_eligible")
    for it in card.get("items", []):
        if "status" not in it or "layer0_1" not in it:
            errs.append(f"item missing status/layer0_1: {it.get('fixture')}")
    return errs


# --------------------------------------------------------------------------
# baselines (same harness, deterministic; no model calls)
# --------------------------------------------------------------------------

def baseline_items(which: str, fixtures: dict, manifest: dict):
    """Non-LLM baseline answers in the AGENTS.md item shape.

    - majority-class: predicts the modal winner class OF THE SET BEING SCORED
      (computed from each item's GT; tie -> "yes" per the earlier-seed
      convention). On the full corpus the modal winner is "no" (p_yes = 0.389),
      so hard-coding "yes" would score below random.
      tracks: yes_share 1.0, polarization 0.0 (unanimous yes).
    - random: seeded RNG (RANDOM_BASELINE_SEED) over fixture order
      (sorted names); winner fair coin, shares uniform [0,1).
    carry_last / kNN over titles need division history and are NOT
    computable on an isolated fixture set — they enter the leaderboard
    only from the corpus-backed runs (separate, harness 0.4.2 re-run).
    """
    rng = random.Random(RANDOM_BASELINE_SEED)
    if which == "majority-class":
        import seed_rule
        winners = []
        for name in sorted(fixtures):
            d = fixtures[name]
            m = d.get("__gt__") or seed_rule.compute_metric(d)
            winners.append(m["seed_rule"]["winner"])
        n_yes = winners.count("yes")
        pred_winner = "yes" if n_yes >= len(winners) - n_yes else "no"
    else:
        pred_winner = None
    items = {}
    for name in sorted(fixtures):
        if which == "majority-class":
            raw = {"winner": pred_winner,
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
    if "__gt__" in division:
        return list(division["__gt__"]["tracks"].keys())
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
    "Rebuild a scorecard from its referenced artifacts (CI reproduction, corpus-aware)."
    names = [os.path.basename(f["file"]) for f in card["fixtures"]]
    meta = dict(card)
    # prompt_variant is meta-only (never serialized into the card): recover it
    # from the pinned prompt hash so the rebuilt prompt block matches
    if card.get("prompt", {}).get("hash") == corpus_reference_prompt_hash():
        meta["prompt_variant"] = "corpus"
    if card.get("set") == "public":
        fixtures = {n: load_fixture(repo_root, n, manifest) for n in names}
        meta["set_hash"] = canonical_set_hash(manifest, names)
        meta["fixture_entries"] = {os.path.basename(e["file"]): e for e in manifest["fixtures"]}
    else:
        fixtures, population = corpus_fixtures(repo_root, card["set"])
        meta["fixture_entries"] = {name: {"file": name, "sha256": population["gt_sha256"],
                                          "layers": {"0.1": True, "0.2": True}}
                                   for name in fixtures}
        meta["population"] = population
    if card.get("temporal_split"):
        ts = card["temporal_split"]
        drift_file = ts.get("ids_post_file")
        loaded = load_post_ids(repo_root, ts["cutoff"], card["set"])
        if loaded["ids_post_sha256"] != ts.get("ids_post_sha256"):
            raise SystemExit(f"temporal split drift: {drift_file} sha256 does not match the list on disk")
        meta["temporal"] = loaded
    if card.get("submission", {}).get("kind") == "baseline":
        which = card["model"]["id"].split(":", 1)[1]
        items = baseline_items(which, fixtures,
                               manifest if card.get("set") == "public" else {"fixtures": []})
        problems = []
        meta["repo_root"] = repo_root
    else:
        paths = [os.path.join(repo_root, f["path"]) for f in card["submission"]["files"]]
        item_root = repo_root
        if not all(os.path.exists(p) for p in paths):
            paths, item_root = _submission_paths_from_tar(card, repo_root)
        items, problems = load_submission_files(paths)
        # rescore-from-tar: the extracted layout mirrors the repo layout, so
        # per-item submission_file paths and sha256s reproduce exactly
        meta["repo_root"] = item_root
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
            "n": l01.get("n_eligible", l01["n_total"]),
            "accuracy": l01["accuracy"],
            "accuracy_ci95": l01["ci95"],
            "acc_close": ((l01.get("margin_buckets", {}).get("buckets", {}).get("close") or {})
                          .get("accuracy")),
            "acc_close_ci95": ((l01.get("margin_buckets", {}).get("buckets", {}).get("close") or {})
                               .get("ci95")),
            "margin_macro": l01.get("margin_buckets", {}).get("margin_macro"),
            "mae_yes_share": l02["mae_yes_share"],
            "ci95_yes_share": l02["ci95_yes_share"],
            "mae_polarization": l02["mae_polarization"],
            "ci95_polarization": l02["ci95_polarization"],
            "declared_cutoff": card["contamination"]["declared_cutoff"],
            "evaluation_date": card["evaluation_date"],
            "baseline": card["submission"].get("kind") == "baseline",
        })
    return rows
