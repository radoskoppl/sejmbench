#!/usr/bin/env python3
"""SejmBench harness CLI (issue #4).

Subcommands
  score         deterministic offline scoring of saved submissions (no network)
  baselines     regenerate the non-LLM baseline scorecards (always deterministic)
  compare       paired bootstrap comparison of two scorecards (CODEBOOK §8.2)
  rescore-check CI gate: rebuild committed scorecards from raw artifacts and
                compare every committed field exactly (numbers and provenance)
  leaderboard   regenerate results/leaderboard.jsonl + the README table from
                accepted scorecards (--check fails on drift)

Only layer 0.1/0.2 are scorable; layer 1 refuses until CODEBOOK §10 freezes.
Provider-specific execution lives in documented adapters (not here); a bare
model id does not imply runnability.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

import scoring  # noqa: E402


def _repo_version() -> str:
    with open(os.path.join(_ROOT, "VERSION"), encoding="utf-8") as fh:
        return fh.read().strip()


def _write_json(path: str, card: dict) -> None:
    os.makedirs(os.path.dirname(os.path.join(_ROOT, path)) or ".", exist_ok=True)
    full = os.path.join(_ROOT, path)
    with open(full, "w", encoding="utf-8") as fh:
        json.dump(card, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {path}")


def _load_scorecard(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _fixtures_for_set(repo_root: str, manifest: dict, set_name: str) -> dict:
    if set_name != "public":
        raise SystemExit(f"unknown set: {set_name} (only 'public' exists)")
    return {
        os.path.basename(e["file"]): scoring.load_fixture(repo_root, e["file"], manifest)
        for e in manifest["fixtures"]
    }


def _check_layers(layers: str) -> None:
    requested = {s.strip() for s in layers.split(",") if s.strip()}
    if "1" in requested:
        raise SystemExit(
            "layer 1 dictionary is DRAFT (CODEBOOK §10): no layer-1 scores may be "
            "submitted or published until the dictionary freezes."
        )
    unknown = requested - set(scoring.SCORED_LAYERS)
    if unknown:
        raise SystemExit(f"unknown layers: {sorted(unknown)}")
    if requested != set(scoring.SCORED_LAYERS):
        raise SystemExit(
            "--layers must be exactly '0.1,0.2': this harness computes both layers "
            f"into one scorecard; requested: {sorted(requested)}")


# ---------------------------------------------------------------- score ----

def cmd_score(args) -> int:
    _check_layers(args.layers)
    manifest = scoring.load_manifest(_ROOT)
    fixtures = _fixtures_for_set(_ROOT, manifest, args.set)

    paths = []
    for p in args.submission:
        if os.path.isdir(p):
            paths.extend(sorted(
                os.path.join(p, f) for f in os.listdir(p) if f.endswith(".json")))
        else:
            paths.append(p)
    if not paths:
        raise SystemExit("no submission files found")

    items, problems = scoring.load_submission_files(paths)
    if not items:
        raise SystemExit(f"no usable submission items; problems: {problems}")

    # model identity: AGENTS.md fields, consistent across files
    ids = {d.get("model") for d in items.values()}
    dates = {d.get("date") for d in items.values()}
    temps = {str(d.get("temperature")) for d in items.values()}
    cuts = {d.get("declared_cutoff", "unknown") for d in items.values()}
    if len(ids) != 1 or None in ids:
        raise SystemExit(f"inconsistent or missing 'model' across submission files: {ids}")
    if len(temps) != 1:
        raise SystemExit(f"inconsistent 'temperature' across files: {temps}")
    eval_date = args.eval_date or (dates.pop() if len(dates) == 1 else None)
    if not eval_date:
        raise SystemExit("inconsistent 'date' across files; pass --eval-date explicitly")
    declared_cutoff = args.declared_cutoff or (cuts.pop() if len(cuts) == 1 else "unknown")

    revision_provided = args.revision is not None
    decoding = {"temperature": 0}
    if args.top_p is not None:
        decoding["top_p"] = args.top_p
    if args.max_tokens is not None:
        decoding["max_tokens"] = args.max_tokens

    meta = {
        "benchmark_version": scoring.BENCHMARK_VERSION,
        "metric_version": scoring.METRIC_VERSION,
        "harness_version": _repo_version(),
        "repo_root": _ROOT,
        "set": args.set,
        "set_hash": scoring.canonical_set_hash(manifest),
        "fixture_entries": {os.path.basename(e["file"]): e for e in manifest["fixtures"]},
        "model": {
            "id": args.model_id or next(iter(ids)),
            "provider": args.provider or "unspecified",
            "revision": args.revision,
            "identity_mutable_alias": not revision_provided,
            "call_date": eval_date,
            "decoding": decoding,
        },
        "submission": {
            "kind": "model",
            "files": [{"fixture": os.path.basename(k),
                       "path": os.path.relpath(v["_path"], _ROOT),
                       "sha256": scoring._sha256_file(v["_path"])}
                      for k, v in sorted(items.items())],
        },
        "evaluation_date": eval_date,
        "contamination": {"declared_cutoff": declared_cutoff,
                          "temporal_holdout_applied": False},
        "token_usage": ({"input_tokens": args.token_usage_in,
                         "output_tokens": args.token_usage_out}
                        if args.token_usage_in is not None or args.token_usage_out is not None
                        else None),
        "cost_estimate": ({"value": args.cost_usd, "currency": "USD"}
                          if args.cost_usd is not None else None),
    }
    card = scoring.build_scorecard(fixtures, items, problems, meta)

    errs = scoring.validate_scorecard(card)
    if errs:
        raise SystemExit("scorecard failed schema validation:\n  " + "\n  ".join(errs))
    if args.out:
        _write_json(args.out, card)
    l01, l02 = card["layers"]["0.1"], card["layers"]["0.2"]
    print(f"layer 0.1: accuracy {scoring._fmt_ci(l01['accuracy'], l01['ci95'][0], l01['ci95'][1])}"
          f" n={l01['n_total']}")
    print(f"layer 0.2: yes_share MAE {scoring._fmt_ci(l02['mae_yes_share'], l02['ci95_yes_share'][0], l02['ci95_yes_share'][1])}"
          f" | polarization MAE {scoring._fmt_ci(l02['mae_polarization'], l02['ci95_polarization'][0], l02['ci95_polarization'][1])}"
          f" (coverage {l02['answer_coverage']:.2f})")
    if card["problems"]:
        print(f"PROBLEMS (CI will fail on these):", file=sys.stderr)
        for p in card["problems"]:
            print(f"  - {p}", file=sys.stderr)
        return 1
    return 0


# ------------------------------------------------------------ baselines ----

def cmd_baselines(args) -> int:
    manifest = scoring.load_manifest(_ROOT)
    fixtures = _fixtures_for_set(_ROOT, manifest, args.set)
    for which in ("majority-class", "random"):
        items = scoring.baseline_items(which, fixtures, manifest)
        meta = scoring.baseline_meta(which, args.set, manifest, _repo_version())
        card = scoring.build_scorecard(fixtures, items, [], meta)
        errs = scoring.validate_scorecard(card)
        if errs:
            raise SystemExit(f"baseline {which} failed validation: {errs}")
        _write_json(f"results/baseline-{which}-{args.set}.scorecard.json", card)
    return 0


# --------------------------------------------------------------- compare ----

def cmd_compare(args) -> int:
    a, b = _load_scorecard(args.scorecard_a), _load_scorecard(args.scorecard_b)
    for name, card in (("A", a), ("B", b)):
        errs = scoring.validate_scorecard(card)
        if errs:
            raise SystemExit(f"scorecard {name} invalid: {errs}")
    if a.get("metric_version") != b.get("metric_version"):
        raise SystemExit("scorecards with different metric versions are not comparable (CODEBOOK rule)")

    def by_fixture(card):
        return {os.path.basename(it["fixture"]): it for it in card["items"]}

    ia, ib = by_fixture(a), by_fixture(b)
    shared, sha_mismatched = scoring.shared_fixtures(a, b)
    shared = [f for f in shared if f in ia and f in ib]
    if not shared:
        raise SystemExit("no shared fixtures (same name AND same fixture sha256) "
                         "between the two scorecards")

    winner_diffs = [ia[f]["layer0_1"]["correct"] - ib[f]["layer0_1"]["correct"] for f in shared]
    ys_diffs = [ia[f]["layer0_2"]["mae_yes_share"] - ib[f]["layer0_2"]["mae_yes_share"]
                for f in shared if ia[f]["layer0_2"] and ib[f]["layer0_2"]]
    pol_diffs = [ia[f]["layer0_2"]["mae_polarization"] - ib[f]["layer0_2"]["mae_polarization"]
                 for f in shared if ia[f]["layer0_2"] and ib[f]["layer0_2"]]

    def block(diffs):
        if diffs:
            mean, lo, hi = scoring.paired_bootstrap(diffs)
        else:
            mean = lo = hi = None
        n = len(diffs)
        excludes_zero = mean is not None and lo is not None and hi is not None and (lo > 0 or hi < 0)
        ranked = excludes_zero and n >= scoring.MIN_CELL_COUNT
        provisional = excludes_zero and n < scoring.MIN_CELL_COUNT
        if provisional:
            note = (f"CI excludes zero but n={n} < minimum cell count {scoring.MIN_CELL_COUNT} "
                    f"(§8.3) — provisional, not a ranking")
        elif not excludes_zero:
            note = "differences inside the 95% CI — not ranked (§8.2)"
        else:
            note = ""
        return {"n_shared": n, "mean_diff": mean, "ci95": [lo, hi],
                "ranked": ranked, "provisional": provisional, "note": note}

    cov_a = a["layers"]["0.2"].get("answer_coverage")
    cov_b = b["layers"]["0.2"].get("answer_coverage")
    out = {
        "schema": "sejmbench.compare/1.0",
        "comparison_seed": scoring.BOOTSTRAP_SEED,
        "shared_fixtures": shared,
        "excluded_fixture_hash_mismatches": sha_mismatched,
        "a": os.path.basename(args.scorecard_a),
        "b": os.path.basename(args.scorecard_b),
        "answer_coverage": {
            "a": cov_a, "b": cov_b,
            "diff": None if (cov_a is None or cov_b is None) else cov_a - cov_b,
            "note": "MAE denominators include only items with a valid parsed answer (§8.6); "
                    "a coverage gap can flatter the model that answers only the easy items",
        },
        "layer0_1": block(winner_diffs),
        "layer0_2": {"mae_yes_share": block(ys_diffs),
                     "mae_polarization": block(pol_diffs)},
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


# --------------------------------------------------------- rescore-check ----

def cmd_rescore_check(args) -> int:
    manifest = scoring.load_manifest(_ROOT)
    expected_hash = scoring.canonical_set_hash(manifest)
    paths = []
    for p in args.scorecards:
        paths.extend(sorted(glob.glob(p)) or [p])
    failed = False
    for p in paths:
        card = _load_scorecard(p)
        errs = scoring.validate_scorecard(card, expected_set_hash=expected_hash,
                                          expected_fixtures=manifest["fixtures"])
        if errs:
            print(f"FAIL {p}: schema invalid: {errs}")
            failed = True
            continue
        if card.get("problems"):
            print(f"FAIL {p}: scorecard carries problems (not acceptable): {card['problems']}")
            failed = True
            continue
        rebuilt = scoring.rescore(card, _ROOT, scoring.load_manifest(_ROOT))
        mismatches = scoring.rescore_matches(card, rebuilt)
        if mismatches:
            print(f"FAIL {p}: {len(mismatches)} mismatches, e.g. {mismatches[:3]}")
            failed = True
        else:
            print(f"OK   {p}: rescore reproduces every committed number")
    return 1 if failed else 0


# ------------------------------------------------------------ leaderboard ----

LEADERBOARD_START = "<!-- LEADERBOARD:START -->"
LEADERBOARD_END = "<!-- LEADERBOARD:END -->"


def _render_table(rows) -> str:
    header = ("| model | set | n | accuracy (95% CI) | yes_share MAE (95% CI) "
              "| polarization MAE (95% CI) | scorecard |")
    sep = "|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for r in rows:
        acc = (scoring._fmt_ci(r["accuracy"], r["accuracy_ci95"][0], r["accuracy_ci95"][1])
               if r["accuracy"] is not None else "n/a")
        ys = (scoring._fmt_ci(r["mae_yes_share"], r["ci95_yes_share"][0], r["ci95_yes_share"][1])
              if r["mae_yes_share"] is not None else "n/a")
        pol = (scoring._fmt_ci(r["mae_polarization"], r["ci95_polarization"][0], r["ci95_polarization"][1])
               if r["mae_polarization"] is not None else "n/a")
        star = "\\*" if r["baseline"] else ""
        lines.append(f"| {r['model']}{star} | {r['set']} | {r['n']} | {acc} | {ys} | {pol} | "
                     f"[{r['scorecard']}]({r['scorecard']}) |")
    return "\n".join(lines)


def cmd_leaderboard(args) -> int:
    manifest = scoring.load_manifest(_ROOT)
    paths = sorted(glob.glob(os.path.join(_ROOT, "results", "*.scorecard.json")))
    cards, rows = [], []
    for p in paths:
        card = _load_scorecard(p)
        errs = scoring.validate_scorecard(card, expected_set_hash=scoring.canonical_set_hash(manifest),
                                          expected_fixtures=manifest["fixtures"])
        if errs:
            raise SystemExit(f"scorecard {p} invalid — leaderboard only reads accepted scorecards: {errs}")
        if card.get("problems"):
            raise SystemExit(f"scorecard {p} carries problems — fix the submission first")
        cards.append(card)
        row = scoring.leaderboard_rows([card])[0]
        row["scorecard"] = os.path.relpath(p, _ROOT)
        rows.append(row)

    jsonl_path = os.path.join(_ROOT, "results", "leaderboard.jsonl")
    new_jsonl = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)
    old_jsonl = open(jsonl_path, encoding="utf-8").read() if os.path.exists(jsonl_path) else ""

    readme_path = os.path.join(_ROOT, "README.md")
    readme = open(readme_path, encoding="utf-8").read()
    if LEADERBOARD_START not in readme or LEADERBOARD_END not in readme:
        raise SystemExit("README.md lacks the LEADERBOARD markers")
    section = (
        "Only rows reproducible from accepted scorecards in `results/`; generated by\n"
        "`python scripts/sejmbench.py leaderboard`, never hand-edited. `\\*` = non-model\n"
        "baseline. Layer-1 rows appear only after the §10 dictionary freezes.\n"
        "Prediction-backtest numbers live in `results/backtest-*.md` and are never\n"
        "merged with these rows.\n\n"
        + _render_table(rows) + "\n"
    )
    new_readme = (readme.split(LEADERBOARD_START)[0] + LEADERBOARD_START + "\n" + section
                  + LEADERBOARD_END + readme.split(LEADERBOARD_END, 1)[1])

    if args.check:
        ok = (new_jsonl == old_jsonl and new_readme == readme)
        print(f"leaderboard --check: {'OK' if ok else 'DRIFT'}")
        return 0 if ok else 1
    with open(jsonl_path, "w", encoding="utf-8") as fh:
        fh.write(new_jsonl)
    with open(readme_path, "w", encoding="utf-8") as fh:
        fh.write(new_readme)
    print(f"leaderboard: {len(rows)} rows written to results/leaderboard.jsonl + README table")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sejmbench", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("score", help="deterministic offline scoring of a submission")
    p.add_argument("--submission", nargs="+", required=True,
                   help="submission file(s) or a directory of per-fixture files")
    p.add_argument("--set", default="public", choices=["public"])
    p.add_argument("--layers", default="0.1,0.2", help="comma list; layer 1 refuses until frozen")
    p.add_argument("--out", help="scorecard output path (relative to repo root)")
    p.add_argument("--model-id", help="override model id (defaults to the files' 'model')")
    p.add_argument("--provider", help="provider name/surface actually used")
    p.add_argument("--revision", help="immutable model revision/snapshot, if the provider exposes one")
    p.add_argument("--declared-cutoff", help="model training-cutoff date, else 'unknown'")
    p.add_argument("--eval-date", help="evaluation date override (UTC date)")
    p.add_argument("--top-p", type=float, help="decoding setting actually used")
    p.add_argument("--max-tokens", type=int, help="decoding setting actually used")
    p.add_argument("--token-usage-in", type=int)
    p.add_argument("--token-usage-out", type=int)
    p.add_argument("--cost-usd", type=float)
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("baselines", help="regenerate non-LLM baseline scorecards")
    p.add_argument("--set", default="public", choices=["public"])
    p.set_defaults(func=cmd_baselines)

    p = sub.add_parser("compare", help="paired bootstrap comparison of two scorecards")
    p.add_argument("scorecard_a")
    p.add_argument("scorecard_b")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("rescore-check", help="CI gate: rescore committed scorecards from artifacts")
    p.add_argument("scorecards", nargs="+", help="scorecard paths or glob patterns")
    p.set_defaults(func=cmd_rescore_check)

    p = sub.add_parser("leaderboard", help="regenerate leaderboard.jsonl + README table")
    p.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    p.set_defaults(func=cmd_leaderboard)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
