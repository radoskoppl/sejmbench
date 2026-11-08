#!/usr/bin/env python3
"""Descriptive T8 vs T10 close-division comparison (issue #19 — no causal claims).

Inputs:
- docs/population/gt-full.jsonl.gz (committed) — winner, margin_all, n_active,
  inni_totals, polarization, fixture date/sitting/votingNumber;
- results/basal-9b-full.scorecard.json (HF artifact, local copy) — per-item
  layer0_1 pred/gt/correct;
- optional --votings: term-8/10 slice of the mirror rebuild (build_extra output)
  for the vote-type axis — descriptions are NOT in the GT stream; the exact-formula
  inventory (docs/inventory-description.json) is bound to mirror frame 3b3a659a,
  and term-8/10 rows are historical and stable across mirror refreshes.

Writes results/t8-t10-close-gap-2026-11-08.md. Descriptive only (issue #19)."""
import argparse
import gzip
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOSE_LO, CLOSE_HI = 6, 50
DECILES = [(6, 10), (11, 20), (21, 35), (36, 50)]
FOCUS = ("term8", "term10")


def med(vals):
    vals = sorted(vals)
    return vals[len(vals) // 2] if vals else None

def mean(vals):
    return (sum(vals) / len(vals)) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--votings", help="term-8/10 mirror subset JSONL (vote-type axis)")
    ap.add_argument("--card", default=os.path.join(ROOT, "results", "basal-9b-full.scorecard.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "t8-t10-close-gap-2026-11-08.md"))
    args = ap.parse_args()

    gt = {}
    with gzip.open(os.path.join(ROOT, "docs", "population", "gt-full.jsonl.gz"), "rt") as fh:
        for line in fh:
            d = json.loads(line)
            gt[d["id"]] = d["metric"]

    card = json.load(open(args.card, encoding="utf-8"))
    items = {}
    for it in card["items"]:
        if it.get("status") == "excluded":
            continue
        name = it["fixture"][:-5] if it["fixture"].endswith(".json") else it["fixture"]
        items[name] = it["layer0_1"]

    # hard join-completeness checks (external review of #19)
    if set(items) != set(gt) or len(items) != len(gt):
        raise SystemExit(f"population mismatch: card {len(items)} vs GT {len(gt)}")
    for gid, it in items.items():
        if it.get("correct") not in (0, 1):
            raise SystemExit(f"item {gid}: correct must be 0 or 1, got {it.get('correct')!r}")

    recs = defaultdict(list)  # term -> close-bucket records
    div_per_sitting = defaultdict(int)  # (term, sitting) -> all divisions (true sitting length)
    for gid, m in gt.items():
        term = gid.split("-")[0]
        sit = int(gid.split("-")[1][1:])
        div_per_sitting[(term, sit)] += 1
        it = items.get(gid)
        if it is None:
            continue
        margin_raw = m.get("margin_all")
        if margin_raw is None:
            continue  # unbucketed — a missing margin must not become a tie
        margin = abs(int(margin_raw))
        if not (CLOSE_LO <= margin <= CLOSE_HI):
            continue
        s, v = int(gid.split("-")[1][1:]), int(gid.split("-")[2][1:])
        inni = m.get("inni_totals") or {}
        inni_active = inni.get("YES", 0) + inni.get("NO", 0) + inni.get("ABSTAIN", 0)
        n_active = m.get("n_active") or 0
        inni_all = sum(inni.values())
        inni_nonv = ((inni.get("ABSENT", 0) + inni.get("NO_VOTE", 0)) / inni_all) if inni_all else 0
        recs[term].append({
            "sitting": int(s), "voting": int(v), "margin": margin,
            "pred": it.get("pred"), "gt": it.get("gt"),
            "correct": 1 if it.get("correct") else 0,
            "gt_yes": 1 if it.get("gt") == "yes" else 0,
            "pred_yes": 1 if it.get("pred") == "yes" else 0,
            "n_active": n_active, "n_tracks": len(m.get("tracks") or {}),
            "inni_share": (inni_active / (n_active + inni_active)) if (n_active + inni_active) else 0.0,
            "inni_nonv": inni_nonv,
            "polarization": m.get("overall_polarization") or 0.0,
            "date": (m.get("fixture") or {}).get("date") or "",
        })

    terms = sorted(recs, key=lambda t: int(t[4:]))

    def term_row(term):
        rs = recs[term]
        n = len(rs)
        acc = sum(r["correct"] for r in rs) / n if n else None
        margins = [r["margin"] for r in rs]
        act = [r["n_active"] for r in rs]
        trk = [r["n_tracks"] for r in rs]
        nonv = [r["inni_nonv"] for r in rs]
        pol = [r["polarization"] for r in rs]
        inni = [r["inni_share"] for r in rs]
        gt_yes = sum(r["gt_yes"] for r in rs) / n if n else None
        pred_yes = sum(r["pred_yes"] for r in rs) / n if n else None
        f_yes = sum(1 for r in rs if r["pred"] == "yes" and r["gt"] == "no")
        f_no = sum(1 for r in rs if r["pred"] == "no" and r["gt"] == "yes")
        per_sitting = defaultdict(int)
        for r in rs:
            per_sitting[r["sitting"]] += 1
        vps = list(per_sitting.values())
        sittings_all = [n for (t, _), n in div_per_sitting.items() if t == term]
        dates = sorted(r["date"][:10] for r in rs if r["date"])
        return {
            "n": n, "acc": acc, "margin_med": med(margins),
            "f_yes": f_yes, "f_no": f_no,
            "f_yes_rate": (f_yes / n if n else None), "f_no_rate": (f_no / n if n else None),
            "gt_yes": gt_yes, "pred_yes": pred_yes,
            "n_active_med": med(act), "n_tracks_med": med(trk),
            "inni_mean": mean(inni), "inni_nonv_mean": mean(nonv),
            "pol_mean": mean(pol),
            "sittings": len(per_sitting), "close_vps_mean": mean(vps),
            "vps_mean": mean(sittings_all) if sittings_all else None,
            "date_min": dates[0] if dates else "", "date_max": dates[-1] if dates else "",
        }

    rows = {t: term_row(t) for t in terms}

    L = []
    A = L.append
    A("# T8 vs T10: descriptive comparison of close divisions (§13 bucket `close`, margin 6–50)")
    A("")
    A("Issue #19. Data: committed GT stream + the 9B scorecard (basal-omni-1.0-ultra, n=66,104, temp 0).")
    A("All axes are descriptive — **no causal attribution** (issue #19). The vote-type axis")
    A("joins the mirror rebuild (`build_extra` output, term-8/10 slice) because the GT stream")
    A("carries no descriptions; the exact-formula inventory is bound to mirror frame `3b3a659a`")
    A("(the 9B frame) and term-8/10 rows are historical and stable across refreshes.")
    A("")
    A("## 1. Close-bucket comparison by term (context: all terms 3–10)")
    A("")
    A("| term | n | close acc | margin med | false-yes | false-no | false-yes rate | false-no rate | gt-yes share | pred-yes share |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for t in terms:
        r = rows[t]
        A(f"| {t[4:]} | {r['n']} | {r['acc']:.4f} | {r['margin_med']} | {r['f_yes']} | {r['f_no']} "
          f"| {r['f_yes_rate']:.4f} | {r['f_no_rate']:.4f} | {r['gt_yes']:.4f} | {r['pred_yes']:.4f} |")
    A("")
    A("## 2. Structure axes (T8 vs T10 close divisions)")
    A("")
    A("| axis | term 8 | term 10 |")
    A("|---|---|---|")
    for label, key, fmt in (
        ("n active, median", "n_active_med", "{:.0f}"),
        ("club tracks, median", "n_tracks_med", "{:.0f}"),
        ("inni share of active, mean", "inni_mean", "{:.4f}"),
        ("inni ABSENT+NO_VOTE share, mean", "inni_nonv_mean", "{:.4f}"),
        ("polarization, mean", "pol_mean", "{:.4f}"),
        ("votings per sitting, mean (all divisions of the term)", "vps_mean", "{:.1f}"),
        ("close divisions per sitting, mean (sittings with >=1 close)", "close_vps_mean", "{:.1f}"),
        ("sittings with close divisions", "sittings", "{:.0f}"),
        ("date span", None, "{}"),
    ):
        if key is None:
            A(f"| {label} | {rows['term8']['date_min']} → {rows['term8']['date_max']} "
              f"| {rows['term10']['date_min']} → {rows['term10']['date_max']} |")
        else:
            A(f"| {label} | {fmt.format(rows['term8'][key])} | {fmt.format(rows['term10'][key])} |")
    A("")

    A("## 3. Close accuracy by margin band (T8 vs T10)")
    A("")
    A("| margin band | term 8 n | term 8 acc | term 10 n | term 10 acc | gap (T10 − T8) |")
    A("|---|---|---|---|---|---|")
    for lo, hi in DECILES:
        cells = []
        for term in FOCUS:
            rs = [r for r in recs[term] if lo <= r["margin"] <= hi]
            n = len(rs)
            acc = (sum(r["correct"] for r in rs) / n) if n else None
            cells.append((n, acc))
        gap = (cells[1][1] - cells[0][1]) if (cells[0][1] is not None and cells[1][1] is not None) else None
        A(f"| {lo}–{hi} | {cells[0][0]} | {cells[0][1]:.4f} | {cells[1][0]} | {cells[1][1]:.4f} | "
          f"{gap:+.4f} |" if gap is not None else
          f"| {lo}–{hi} | {cells[0][0]} | {cells[0][1]:.4f} | {cells[1][0]} | {cells[1][1]:.4f} | n/a |")

    A("")
    A("## 3b. T10 close divisions split at the §9 cutoff (2026-01-01)")
    A("")
    A("The §9 temporal split (post = strictly after the cutoff) applied to the T10 close")
    A("bucket — connects the close-division collapse to the contamination control")
    A("(`declared_cutoff` stays `unknown`; descriptive, no causal claim).")
    A("")
    A("| period | n | close acc | gt-yes share | pred-yes share | false-no rate |")
    A("|---|---|---|---|---|---|")
    rs10 = recs["term10"]
    pre = [r for r in rs10 if r["date"][:10] <= "2026-01-01"]
    post = [r for r in rs10 if r["date"][:10] > "2026-01-01"]
    for label, rs in (("pre (<= 2026-01-01)", pre), ("post (> 2026-01-01)", post)):
        n = len(rs)
        acc = (sum(r["correct"] for r in rs) / n) if n else None
        gy = (sum(r["gt_yes"] for r in rs) / n) if n else None
        py = (sum(r["pred_yes"] for r in rs) / n) if n else None
        fn = (sum(1 for r in rs if r["pred"] == "no" and r["gt"] == "yes") / n) if n else None
        f = lambda x: "n/a" if x is None else f"{x:.4f}"
        A(f"| {label} | {n} | {f(acc)} | {f(gy)} | {f(py)} | {f(fn)} |")

    A("")
    A("## 4. Vote-type axis (mirror join, close divisions)")

    if args.votings and os.path.exists(args.votings):
        meta = {}
        with open(args.votings, encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                meta[(d["term"], d["sitting"], d["votingNumber"])] = d
        inv = json.load(open(os.path.join(ROOT, "docs", "inventory-description.json"), encoding="utf-8"))
        bkt = json.load(open(os.path.join(ROOT, "docs", "layer1-formula-buckets.json"), encoding="utf-8"))
        formula_texts = {e["text"] for e in inv["formulas"]}
        f2b = {e["text"]: e["bucket"] for e in bkt["formulas"]}

        stats = {}
        for term in FOCUS:
            described = [r for r in recs[term]
                         if (meta.get((int(term[4:]), r["sitting"], r["voting"])) or {}).get("description")]
            matched = [(r, f2b.get(d["description"])) for r in described
                       for d in [(meta.get((int(term[4:]), r["sitting"], r["voting"])))]
                       if d["description"] in formula_texts]
            n_desc = len(described)
            n_match = len(matched)
            bd = defaultdict(list)
            for r, bucket in matched:
                bd[bucket].append(r)
            stats[term] = {
                "n_close": len(recs[term]), "n_described": n_desc, "n_matched": n_match,
                "desc_share": n_desc / len(recs[term]) if recs[term] else 0,
                "buckets": {b: {"n": len(rs), "acc": (sum(r["correct"] for r in rs) / len(rs)) if rs else None}
                            for b, rs in sorted(bd.items(), key=lambda kv: -len(kv[1]))},
            }
        A("")
        A("Vote-type join: only mirror rows carrying a description can be classified")
        A("(inventory: 10,479 of 66,427 mirror rows; the described subset is *not* representative")
        A("of all close divisions — treat the mix comparison as conditional on description availability).")
        A("")
        A("| term | close n | with description | matched to a formula | matched share of described |")
        A("|---|---|---|---|---|")
        for term in FOCUS:
            s = stats[term]
            A(f"| {term[4:]} | {s['n_close']} | {s['n_described']} | {s['n_matched']} | "
              f"{(s['n_matched'] / s['n_described']) if s['n_described'] else 0:.4f} |")
        A("")
        A("Bucket mix among matched close divisions (top buckets by pooled n):")
        A("")
        A("| bucket | T8 n | T8 acc | T10 n | T10 acc |")
        A("|---|---|---|---|---|")
        pooled = defaultdict(lambda: {"term8": None, "term10": None})
        for term in FOCUS:
            for b, s in stats[term]["buckets"].items():
                pooled[b][term] = s

        def cells(x):
            if x and x["n"]:
                return str(x["n"]), (f"{x['acc']:.4f}" if x["acc"] is not None else "n/a")
            return "0", "n/a"

        for b, s in sorted(pooled.items(), key=lambda kv: -sum(x["n"] or 0 for x in kv[1].values() if x)):
            t8, t10 = s["term8"], s["term10"]
            n8, a8 = cells(t8)
            n10, a10 = cells(t10)
            A(f"| {b} | {n8} | {a8} | {n10} | {a10} |")
    else:
        A("")
        A("(vote-type axis skipped: pass --votings with the term-8/10 mirror slice)")

    A("")
    A("## 5. Definitional reconciliation: the #14 numbers used the seed-rule margin")
    A("")
    A("The #14 body's error analysis (98.7% / 84.0%) predates §13; it keyed close on the")
    A("seed-rule margin (club-tracked, excludes unaffiliated `inni`). §13 froze the headline")
    A("`margin_all` (includes `inni`) — the T10 close set gains 137 divisions (1,461 → 1,598)")
    A("and the accuracy moves 84.0% → 84.7%; T8 is unchanged (98.8%). Same construct up to")
    A("the `inni` inclusion; the frozen §13 definition is canonical going forward.")
    A("")
    A("| close definition | T8 n (acc) | T10 n (acc) |")
    A("|---|---|---|")
    for label, key in (("seed-rule margin (the #14 body)", "seed"),
                       ("§13 headline margin_all", "headline")):
        row = []
        for term in FOCUS:
            rs = []
            for gid, m in gt.items():
                if not gid.startswith(f"{term}-"):
                    continue
                it = items.get(gid)
                if it is None:
                    continue
                margin = (m.get("seed_rule") or {}).get("margin") if key == "seed" else m.get("margin_all")
                if margin is None:
                    continue
                margin = abs(int(margin))
                if CLOSE_LO <= margin <= CLOSE_HI:
                    rs.append(it["correct"])
            acc = (sum(rs) / len(rs)) if rs else None
            row.append(f"{len(rs)} ({acc:.4f})" if acc is not None else "0 (n/a)")
        A(f"| {label} | {row[0]} | {row[1]} |")

    A("")
    A("## Candidate explanations (ranked; evidence from the tables above)")
    A("")
    A("1. **Winner-side composition shift that the model's yes-rate did not track.** Close")
    A("   divisions are won by \"yes\" far more often in T10 (31.7%) than in T8 (15.2%) —")
    A("   and post-cutoff even more (34.1%). The model's pred-yes share rose only 13.98% →")
    A("   20.21% while the actual share rose 15.16% → 31.73%. The accuracy gap (14.09 pp)")
    A("   decomposes as Δfalse-no (12.21 pp) + Δfalse-yes (1.88 pp); the net")
    A("   yes-underprediction changed by 10.34 pp (gt-yes shift 16.57 pp − pred-yes shift")
    A("   6.23 pp) — related to, but not identical with, the accuracy gap. The error mass")
    A("   is one-sided: false-no dominates (1.18% → 13.39%) while false-yes is 0 in T8")
    A("   and 1.88% in T10. Caveat: T9 had an even higher yes-share (37.7%) and scored")
    A("   0.9871 — the share alone does not determine accuracy.")
    A("2. **The T10 close collapse deepens after the §9 cutoff.** Within T10, close")
    A("   accuracy drops 0.8688 (pre-2026) → 0.8099 (post-2026), −5.9 pp — much larger")
    A("   than the −1.7 pp overall pre/post gap, so the close bucket carries most of the")
    A("   within-term temporal signal. The model's pred-yes share *falls* post-cutoff")
    A("   (0.208 → 0.192) while the yes-win share rises (0.304 → 0.341). Descriptive")
    A("   only: three cutoff points, no CIs, `declared_cutoff` unknown; a cluster")
    A("   bootstrap by sitting is queued as a follow-up.")
    A("3. **The observed gap persists within major vote types in the described subset.**")
    A("   bill_whole 0.953 → 0.661, resolution_whole 1.000 → 0.696, appointment 1.000 →")
    A("   0.714, wotum 1.000 → 0.636; only `first_reading_rejection` is nearly flat")
    A("   (0.923 → 0.890) — the one type whose outcome is structurally one-sided")
    A("   (rejection motions almost always fail). The described subset is small (T8 258,")
    A("   T10 300) and conditional on description availability.")
    A("4. **The measured room-structure axes are mostly flat — except sitting length.**")
    A("   n_active (422/424), club tracks (6/7), polarization (0.908/0.904), inni share")
    A("   (0.012/0.018) are flat; votings per sitting differs (95.9 vs 76.7) and the")
    A("   non-active `inni` share is higher in T8 (0.170 vs 0.112) — measured, but their")
    A("   connection to accuracy is unproven. The gap may live in party-system alignment")
    A("   structure or a training-data era effect — not captured by these artifacts.")
    A("5. **Margin-band composition contributes but does not explain.** T10 close")
    A("   divisions concentrate in higher bands (36–50: 1,021 vs T8 161) and the gap is")
    A("   largest at 11–20/21–35 (−0.28/−0.22) — but even the 36–50 band shows −0.09,")
    A("   and T10 outperforms T8 at 6–10 (+0.17).")
    A("")
    A("Definitional note: the #14 body's numbers (98.7% / 84.0%) were computed on the")
    A("seed-rule margin (club-tracked, excludes `inni`) — section 5; under the frozen")
    A("§13 definition (headline `margin_all`, includes `inni`) they are 98.8% / 84.7%.")
    A("Canonical going forward: the frozen §13 definition.")
    A("")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
