#!/usr/bin/env python3
"""Counterfactual report builder (issue #15): arms → per-item verdicts → report.

Compares the perturbed arm (scripts/cf_run_eval.py output) with the original
arm (an existing committed run over the same items — e.g.
results/m3-preview-term10) and writes:
  <cf-dump>/cf-report.md      — the issue-#15 metrics, one section per arm
  <cf-dump>/cf-verdicts.jsonl — per-item: item_id, arm, original answer,
                                perturbed answer, perturbed GT (from
                                manifest-cf.json), match flags

Metrics (issue #15):
  flip         rate of answers matching the ORIGINAL outcome instead of the
               PERTURBED one (high = input-dependence failure);
  reorder      answer-stability rate (expect 1.0 — GT unchanged);
  club-label pseudonymization
               answer-stability rate (GT unchanged; a dependence on labels
               rather than the tally shows up here).

Both arms are matched by item_id; items missing from either arm are counted
as coverage, not errors.

Usage:
  python3 scripts/cf_report.py --cf-dump ~/cf-dump --run ~/cf-dump/run \
      --original-dir ~/sejmbench/results/m3-preview-term10
"""
import argparse
import json
import os
from collections import Counter

MAP = {"za": "yes", "przeciw": "no", "remis": "tie", "nie_do_okreslenia": None}


def load_arm(directory):
    """item_id -> choice for a run directory of per-item submissions."""
    out = {}
    if not os.path.isdir(directory):
        return out
    for name in os.listdir(directory):
        if not name.endswith(".json") or name == "status.json":
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            rec = json.load(fh)
        item_id = name[:-len(".json")]
        choice = (rec.get("model_answer") or {}).get("choice") \
            if "model_answer" in rec else (rec.get("raw_output") or {}).get("choice")
        if choice is None:
            choice = (rec.get("raw_output") or {}).get("outcome")
        out[item_id] = choice
    return out


def norm(choice):
    return MAP.get(choice, choice)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cf-dump", default=os.path.expanduser("~/cf-dump"))
    ap.add_argument("--run", default=None, help="perturbed-arm submissions dir")
    ap.add_argument("--original-dir", default=None,
                    help="original-arm dir (committed run over the same items)")
    ap.add_argument("--model-id", default=None, help="label for the report header")
    args = ap.parse_args()

    manifest_path = os.path.join(args.cf_dump, "manifest-cf.json")
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    items_by_id = {e["item_id"]: e for e in manifest["items"]}

    run_dir = args.run or os.path.join(args.cf_dump, "run")
    if not args.original_dir:
        raise SystemExit("--original-dir is required (the arm-A submissions)")

    perturbed = load_arm(run_dir)
    original = load_arm(args.original_dir)

    verdicts = []
    for item_id, e in sorted(items_by_id.items()):
        pert_choice = perturbed.get(item_id)
        orig_choice = original.get(item_id)
        pw = norm(pert_choice) if pert_choice else None
        ow = norm(orig_choice) if orig_choice else None
        gt_perturbed = e["gt_perturbed"]["winner"]
        gt_original = e["gt_original"]["winner"]
        kind = e["perturbation"]
        if pw is None or ow is None:
            match_perturbed = match_original = None  # coverage gap
        else:
            match_perturbed = (pw == gt_perturbed)
            match_original = (pw == gt_original)
        verdicts.append({
            "item_id": item_id, "arm": kind,
            "answer_original_run": ow, "answer_perturbed_run": pw,
            "gt_original": gt_original, "gt_perturbed": gt_perturbed,
            "changed_answer_vs_original_run": (pw != ow) if (pw and ow) else None,
            "matches_perturbed_gt": match_perturbed,
            "matches_original_gt": match_original,
        })

    verdicts_path = os.path.join(args.cf_dump, "cf-verdicts.jsonl")
    with open(verdicts_path, "w", encoding="utf-8") as fh:
        for v in verdicts:
            fh.write(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n")

    report_path = os.path.join(args.cf_dump, "cf-report.md")
    lines = [f"# Counterfactual input-reliance report (issue #15)",
             "",
             f"Perturbed arm: `{run_dir}`; original arm: `{args.original_dir}`.",
             (f"Model: {args.model_id}" if args.model_id else ""),
             "",
             "Both arms answered the SAME items with the SAME prompt contract;",
             "only the records differ. Answers matched per item_id.", ""]
    for arm in ("flip", "reorder", "club_label_pseudonymize"):
        rows = [v for v in verdicts if v["arm"] == arm]
        n = len(rows)
        covered = sum(1 for v in rows if v["matches_perturbed_gt"] is not None)
        if not n:
            lines.append(f"## {arm}: no items")
            lines.append("")
            continue
        if arm == "flip":
            match_pert = sum(1 for v in rows if v["matches_perturbed_gt"])
            match_orig = sum(1 for v in rows if v["matches_original_gt"])
            both_missing = sum(1 for v in rows if v["matches_perturbed_gt"] is None)
            lines.append(f"## flip (n={n}, covered {covered})")
            lines.append("")
            lines.append(f"- follows PERTURBED GT: **{match_pert}/{covered}** "
                         f"({match_pert/covered:.3f})" if covered else "- no coverage")
            lines.append(f"- matches the ORIGINAL outcome (input-dependence "
                         f"failure signal): **{match_orig}/{covered}**"
                         + (f" ({match_orig/covered:.3f})" if covered else ""))
            lines.append(f"- missing from an arm: {n - covered}")
        else:
            stable = sum(1 for v in rows
                         if v["changed_answer_vs_original_run"] is False)
            changed = sum(1 for v in rows
                          if v["changed_answer_vs_original_run"] is True)
            missing = sum(1 for v in rows
                          if v["changed_answer_vs_original_run"] is None)
            lines.append(f"## {arm} (n={n}, covered {n - missing})")
            lines.append("")
            lines.append(f"- answer unchanged vs original run (stability): "
                         f"**{stable}/{n - missing}**"
                         + (f" ({stable/(n-missing):.3f})" if n > missing else ""))
            lines.append(f"- answer changed (order/label dependence signal): {changed}")
            lines.append(f"- missing from an arm: {missing}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("These numbers are a separate counterfactual track (issue #15):")
    lines.append("never merged with accuracy scorecards or the leaderboard.")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"wrote {verdicts_path} ({len(verdicts)} verdicts)")
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
