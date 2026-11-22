#!/usr/bin/env python3
"""Per-term club-label overlap report from the committed membership snapshot.

Input: docs/club-identity-membership.json.gz (built by scripts/club_collect.py
from a votes.jsonl dump; one entry per (term, raw API club label) with the set
of MP ids — MP id is unique within a term — plus per-sitting membership and
the divisions each label appears in).

Modes:
  report    write the per-term overlap report (default stdout, or --out)
  --json    machine-readable relations next to the report
  verify    recompute every relation recorded in docs/club-identity.json from
            the raw snapshot and fail loudly on any mismatch

Classification rules (frozen here; the report applies them verbatim):
  relay    B continues A: time-adjacent (gap <= 2 sittings) and
           jaccard(A, B) >= 0.7. Canonical representative of the chain is the
           terminal (latest-ending) label.
  alias    same members concurrently: jaccard >= 0.99, overlapping spans and
           both labels span >= 3 sittings. Canonical = terminal label; the
           alias edge is kept.
  split:X  X (the smaller label) sits inside the other: |X ∩ other| / |X| >=
           0.8 with overlapping spans and unequal sizes. X stays its own
           canonical id.
  absorbed majority continuation across adjacent spans (0.5 <= |A∩B|/|A| <
           0.7); informational.
  coabsorbed informational overlap in that band for concurrent labels.
  (relations below the thresholds are not recorded; the full pairwise table
  with jaccard >= 0.5 is printed in the report for auditability.)

Usage:
    python3 scripts/club_overlap_report.py report [--out docs/club-identity-report.md]
    python3 scripts/club_overlap_report.py verify
"""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MEMBERSHIP = os.path.join(ROOT, "docs", "club-identity-membership.json.gz")
IDENTITY = os.path.join(ROOT, "docs", "club-identity.json")

RELAY_GAP = 2
RELAY_JACCARD = 0.7
ALIAS_JACCARD = 0.99
ALIAS_MIN_SPAN = 3
SPLIT_CONTAINMENT = 0.8
ABSORB_CONTAINMENT = 0.5
REPORT_JACCARD = 0.5


def load_membership(path=MEMBERSHIP):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        raw = json.load(fh)
    by_term = {}
    for key, entry in raw["clubs"].items():
        term, label = key.split("|", 1)
        by_term.setdefault(int(term), {})[label] = entry
    return raw, by_term


def pair_stats(a: dict, b: dict):
    sa, sb = set(a["mp_ids"]), set(b["mp_ids"])
    inter = len(sa & sb)
    union = len(sa | sb)
    return {
        "jaccard": inter / union if union else 0.0,
        "cont_a": inter / len(sa) if sa else 0.0,
        "cont_b": inter / len(sb) if sb else 0.0,
        "n_inter": inter,
    }


def classify(by_term):
    """Return {term: [(kinds, a, b, stats)]} using the frozen rules.

    Direction comes from the data (successor = label that starts after the
    other ends), never from alphabetical pair order. A pair can carry more
    than one kind (e.g. a relay chain whose members also all sit inside a
    concurrent parent).
    """
    out = {}
    for term, labels in sorted(by_term.items()):
        rels = []
        for a, b in itertools.combinations(sorted(labels), 2):
            ea, eb = labels[a], labels[b]
            sa, sb = ea["sittings"], eb["sittings"]
            stats = pair_stats(ea, eb)
            gap_ab = sb[0] - sa[1]  # >0 when B starts after A ends
            gap_ba = sa[0] - sb[1]
            overlapping = gap_ab <= 0 and gap_ba <= 0
            span_a = sa[1] - sa[0] + 1
            span_b = sb[1] - sb[0] + 1
            kinds = []

            if overlapping and stats["jaccard"] >= ALIAS_JACCARD \
                    and min(span_a, span_b) >= ALIAS_MIN_SPAN:
                kinds.append("alias")

            if not overlapping and min(gap_ab, gap_ba) <= RELAY_GAP:
                if stats["jaccard"] >= RELAY_JACCARD:
                    kinds.append("relay")
                elif max(stats["cont_a"], stats["cont_b"]) >= ABSORB_CONTAINMENT:
                    kinds.append("absorbed")
            elif overlapping:
                small, big = (a, b) if len(ea["mp_ids"]) <= len(eb["mp_ids"]) else (b, a)
                st_small_in_big = stats if small == a else \
                    {"cont": pair_stats(eb, ea)["cont_a"]}
                cont_small = stats["cont_b"] if small == b else stats["cont_a"]
                if cont_small >= SPLIT_CONTAINMENT and len(ea["mp_ids"]) != len(eb["mp_ids"]):
                    kinds.append(f"split:{small}")
                elif ABSORB_CONTAINMENT <= stats["cont_a"] < RELAY_JACCARD or \
                        ABSORB_CONTAINMENT <= stats["cont_b"] < RELAY_JACCARD:
                    kinds.append("coabsorbed")
            if kinds:
                rels.append((kinds, a, b, stats))
        out[term] = rels
    return out


def render_report(raw, by_term, rels) -> str:
    prov = raw["provenance"]
    lines = [
        "# Club-identity overlap report (per term, terms 3-10)",
        "",
        f"Generated from `docs/club-identity-membership.json.gz` "
        f"({prov['rows']:,} vote rows, {prov['input_sha256'][:12]}…; dates from `votings.jsonl`).",
        "MP id is unique within a term, so membership sets are exact. `niez.`",
        "(non-attached) is always its own canonical label — nothing is mapped",
        "into it and it is never mapped into anything.",
        "",
        "## Frozen classification rules",
        "",
        f"- **relay** — B continues A: `B.first <= A.last + {RELAY_GAP}` and jaccard ≥ {RELAY_JACCARD}.",
        f"- **alias** — same members concurrently: jaccard ≥ {ALIAS_JACCARD} with both spans ≥ {ALIAS_MIN_SPAN} sittings.",
        f"- **split** — B splits from a persisting A: `|A∩B|/|B| ≥ {SPLIT_CONTAINMENT}`, `|B| < |A|`, overlapping spans.",
        f"- **absorbed** — informational majority continuation (`{ABSORB_CONTAINMENT} ≤ |A∩B|/|A| < {RELAY_JACCARD}`, time-adjacent).",
        "- Pairwise rows with jaccard ≥ "
        f"{REPORT_JACCARD} are printed for audit; anything else is unrecorded.",
        "",
        "The curated mapping lives in `docs/club-identity.json`; `verify` mode",
        "recomputes every recorded relation from the snapshot.",
        "",
    ]
    for term in sorted(by_term):
        labels = by_term[term]
        lines.append(f"## Term {term} — {len(labels)} labels")
        lines.append("")
        lines.append("| label | MPs | divisions | sittings | first → last |")
        lines.append("|---|---|---|---|---|")
        for name in sorted(labels, key=lambda c: labels[c]["first_date"] or ""):
            e = labels[name]
            lines.append(f"| `{name}` | {len(e['mp_ids'])} | {e['n_divisions']} | "
                         f"{e['sittings'][0]}–{e['sittings'][1]} | "
                         f"{(e['first_date'] or '')[:10]} → {(e['last_date'] or '')[:10]} |")
        term_rels = rels[term]
        if term_rels:
            lines.append("")
            lines.append("| kinds | pair | jaccard | cont A→B | cont B→A |")
            lines.append("|---|---|---|---|---|")
            for kinds, a, b, st in term_rels:
                lines.append(f"| {'; '.join(kinds)} | `{a}` × `{b}` | {st['jaccard']:.2f} | "
                             f"{st['cont_a']:.2f} | {st['cont_b']:.2f} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def verify(by_term):
    """Recompute every relation recorded in the identity table from the snapshot."""
    table = json.load(open(IDENTITY, encoding="utf-8"))
    problems = []
    checked = 0

    def containment(sets_from, sets_to):
        return len(sets_from & sets_to) / len(sets_from) if sets_from else 0.0

    for term_s, entry in table["terms"].items():
        term = int(term_s)
        for label, rec in entry["labels"].items():
            if label not in by_term.get(term, {}):
                problems.append(f"term {term}: label `{label}` not in snapshot")
                continue
            e = by_term[term][label]
            se = set(e["mp_ids"])
            if rec.get("first_date") != (e["first_date"] or "")[:10]:
                problems.append(f"term {term} `{label}`: first_date mismatch")
            if rec.get("last_date") != (e["last_date"] or "")[:10]:
                problems.append(f"term {term} `{label}`: last_date mismatch")
            if rec.get("n_mps") != len(e["mp_ids"]):
                problems.append(f"term {term} `{label}`: n_mps mismatch")
            for edge in rec.get("relations", []):
                other = edge["with"]
                if other not in by_term.get(term, {}):
                    problems.append(f"term {term} `{label}`: relation target `{other}` not in snapshot")
                    continue
                so = set(by_term[term][other]["mp_ids"])
                checked += 1
                st = pair_stats(e, by_term[term][other])
                if abs(st["jaccard"] - edge["jaccard"]) > 0.005:
                    problems.append(f"term {term} `{label}`→`{other}`: jaccard {edge['jaccard']} != {st['jaccard']:.3f}")
                kind = edge["kind"]
                if kind in ("split-from", "absorbed-into", "coalition-component") \
                        and containment(se, so) < ABSORB_CONTAINMENT:
                    problems.append(f"term {term} `{label}` {kind} `{other}`: containment lost ({containment(se, so):.2f})")
                if kind == "split-source" and containment(so, se) < ABSORB_CONTAINMENT:
                    problems.append(f"term {term} `{label}` split-source `{other}`: containment lost ({containment(so, se):.2f})")
    return problems, checked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    rep = sub.add_parser("report")
    rep.add_argument("--out")
    rep.add_argument("--json-out", help="write relations JSON here")
    sub.add_parser("verify")
    args = ap.parse_args()

    raw, by_term = load_membership()
    if args.cmd == "verify" or args.cmd is None and os.path.exists(IDENTITY) and "--verify" in sys.argv:
        problems, checked = verify(by_term)
        if problems:
            for p in problems:
                print("FAIL", p, file=sys.stderr)
            return 1
        print(f"club-identity verify OK: {checked} relations recomputed from the snapshot")
        return 0
    if args.cmd == "report":
        rels = classify(by_term)
        text = render_report(raw, by_term, rels)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(f"wrote {args.out}")
        else:
            print(text)
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                json.dump({str(t): [{"kinds": k, "a": a, "b": b, **s} for k, a, b, s in r]
                           for t, r in rels.items()}, fh, indent=1, ensure_ascii=False)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
