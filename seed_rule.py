"""SejmBench seed rule v0.2 — winner determination from a roll-call division.

Scope (CODEBOOK.md 0.2, frozen):
  * A "track" is a club label appearing on >= 5 vote records in the division.
    Labels with fewer records are grouped as "inni" (not scored separately).
  * Track activity n = YES + NO + ABSTAIN (ABSENT and NO_VOTE excluded;
    NO_VOTE is a term-3-era non-active value - CODEBOOK section 1).
  * yes_share = YES / n  (abstention counts in the denominator, stated openly).
  * polarization = 1 - |YES - NO| / n  (0 = unanimous, ->1 = 50/50;
    ABSTAIN dilutes the split, it never inflates polarization).
  * Seed rule: the seed with majority of active votes wins the division.
    Ties resolve by seeding order (earlier seed wins) - deterministic.
    v0.3 addition: the result exposes `seed_rule.tie` (true iff YES == NO,
    including 0:0) so ties are explicit and never reported as "passed".
"""

from __future__ import annotations

MIN_TRACK_RECORDS = 5
TRACK_MIN_VOTES = 5  # a track with < 5 active votes is not scored


def compute_metric(division: dict) -> dict:
    """Compute the v0.2 metric for one division fixture.

    `division` is the JSON saved by scripts/fetch_fixtures.py: the Sejm API
    voting detail with a `votes` list of records
    {MP, club, firstName, lastName, secondName, vote}.
    """
    votes = division["votes"]

    # --- club tallies -----------------------------------------------------
    club_counts: dict[str, dict[str, int]] = {}
    for v in votes:
        club = v["club"]
        c = club_counts.setdefault(club, {"YES": 0, "NO": 0, "ABSTAIN": 0, "ABSENT": 0,
                                          "NO_VOTE": 0})
        c[v["vote"]] += 1

    tracks = {c: t for c, t in club_counts.items() if sum(t.values()) >= MIN_TRACK_RECORDS}
    inni = {c: t for c, t in club_counts.items() if c not in tracks}

    inni_totals = {"YES": 0, "NO": 0, "ABSTAIN": 0, "ABSENT": 0, "NO_VOTE": 0}
    for t in inni.values():
        for k in inni_totals:
            inni_totals[k] += t[k]

    # --- seed rule ---------------------------------------------------------
    seed_totals = {"YES": 0, "NO": 0, "ABSTAIN": 0}
    for t in tracks.values():
        for k in seed_totals:
            seed_totals[k] += t[k]
    n_active = seed_totals["YES"] + seed_totals["NO"] + seed_totals["ABSTAIN"]
    if seed_totals["YES"] > seed_totals["NO"]:
        winner, method = "yes", "majority"
    elif seed_totals["NO"] > seed_totals["YES"]:
        winner, method = "no", "majority"
    else:
        # ties (incl. both zero) resolve by seeding order: earlier seed wins.
        # The yes-seed is defined as the earlier seed (CODEBOOK 0.2).
        winner, method = "yes", "tie_seed_order"

    margin = seed_totals["YES"] - seed_totals["NO"]

    # --- cohesion per track -------------------------------------------------
    track_stats = {}
    for club, t in sorted(tracks.items()):
        n = t["YES"] + t["NO"] + t["ABSTAIN"]
        if n < TRACK_MIN_VOTES:
            continue
        yes_share = t["YES"] / n
        polarization = 1 - abs(t["YES"] - t["NO"]) / n
        track_stats[club] = {
            "n": n,
            "yes": t["YES"],
            "no": t["NO"],
            "abstain": t["ABSTAIN"],
            "yes_share": round(yes_share, 4),
            "polarization": round(polarization, 4),
        }

    overall_n = seed_totals["YES"] + seed_totals["NO"] + seed_totals["ABSTAIN"]
    overall_polarization = (
        1 - abs(seed_totals["YES"] - seed_totals["NO"]) / overall_n if overall_n else 0.0
    )

    margin_all = (
        (seed_totals["YES"] + inni_totals["YES"])
        - (seed_totals["NO"] + inni_totals["NO"])
    )

    return {
        "schema": "sejmbench.metric/0.3",
        "fixture": {
            "term": division.get("term"),
            "sitting": division.get("sitting"),
            "votingNumber": division.get("votingNumber"),
            "title": division.get("title"),
            "date": division.get("date"),
        },
        "seed_rule": {"winner": winner, "method": method, "margin": margin,
                      "tie": seed_totals["YES"] == seed_totals["NO"]},
        "margin_all": margin_all,
        "seed_totals": seed_totals,
        "inni_totals": inni_totals,
        "n_active": n_active,
        "overall_polarization": round(overall_polarization, 4),
        "tracks": track_stats,
        "inni_clubs": sorted(inni.keys()),
    }
