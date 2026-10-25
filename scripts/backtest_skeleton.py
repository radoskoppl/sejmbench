#!/usr/bin/env python3
"""SejmBench backtest skeleton — layer 3 lite, content-free by design.

Predict each division from structural history <= T only (no titles, no text).
Metrics follow CODEBOOK v0.2: winner exact match, per-track yes_share MAE.

Baselines:
  always_yes - predict YES winner always
  club_mean  - per club: historical mean yes_share x historical mean active size
  carry_last - replicate the previous division's per-club shares
"""
import json
import sys
from collections import defaultdict

SRC = sys.argv[1] if len(sys.argv) > 1 else "divisions.jsonl"
WARMUP = 60
MIN_TRACK = 5

def load():
    rows, seen = [], set()
    with open(SRC) as f:
        for line in f:
            d = json.loads(line)
            key = (d["term"], d["sitting"], d["votingNumber"])
            if key not in seen:
                seen.add(key)
                rows.append(d)
    rows.sort(key=lambda d: (d["date"], d["sitting"], d["votingNumber"]))
    return rows

def actuals(d):
    agg = defaultdict(lambda: [0, 0, 0])  # yes, no, abstain
    for v in d["votes"]:
        if v["vote"] not in ("YES", "NO", "ABSTAIN"):
            continue  # ABSENT / PRESENT / VOTE_VALID: inactive per CODEBOOK v0.2
        agg[v["club"]][{"YES": 0, "NO": 1, "ABSTAIN": 2}[v["vote"]]] += 1
    tracks = {c: s for c, s in agg.items() if sum(s) >= MIN_TRACK}
    ty = sum(s[0] for s in tracks.values())
    tn = sum(s[1] for s in tracks.values())
    n = ty + tn + sum(s[2] for s in tracks.values())
    if n == 0:
        return None
    shares = {c: s[0] / sum(s) for c, s in tracks.items() if sum(s) > 0}
    return dict(winner="yes" if ty > tn else "no", shares=shares,
                pol=1 - abs(ty - tn) / n)

def main():
    rows = load()
    hist = {}          # club -> [sum_yes, sum_active, votes_seen, sum_active_total]
    last = {}          # club -> last yes_share
    scores = {"always_yes": [], "club_mean": [], "carry_last": []}
    mae_mean, mae_carry = [], []
    scored = 0
    for i, d in enumerate(rows):
        act = actuals(d)
        if act is None:
            continue
        if i >= WARMUP:
            scored += 1
            scores["always_yes"].append(act["winner"] == "yes")
            # club_mean: expected yes/no counts from history
            ey = en = 0.0
            pred_shares = {}
            for c, (sy, sa, seen, _) in hist.items():
                p = (sy + 1) / (sa + 2)                     # Laplace-smoothed share
                exp_active = sa / seen if seen else 0       # mean active size
                ey += p * exp_active
                en += (1 - p) * exp_active
                pred_shares[c] = p
            scores["club_mean"].append(("yes" if ey > en else "no") == act["winner"])
            for c, s in act["shares"].items():
                if c in pred_shares:
                    mae_mean.append(abs(pred_shares[c] - s))
            # carry_last: previous shares, weighted by previous active sizes
            ey = en = 0.0
            for c, p in last.items():
                _, _, seen, sat = hist.get(c, (0, 0, 0, 0))
                exp_active = sat / seen if seen else 0
                ey += p * exp_active
                en += (1 - p) * exp_active
            scores["carry_last"].append(("yes" if ey > en else "no") == act["winner"])
            for c, s in act["shares"].items():
                if c in last:
                    mae_carry.append(abs(last[c] - s))
        # update history AFTER scoring this division (no leakage)
        agg = defaultdict(lambda: [0, 0, 0])
        for v in d["votes"]:
            if v["vote"] not in ("YES", "NO", "ABSTAIN"):
                continue
            agg[v["club"]][{"YES": 0, "NO": 1, "ABSTAIN": 2}[v["vote"]]] += 1
        for c, s in agg.items():
            active = sum(s)
            if active < MIN_TRACK:
                continue
            h = hist.setdefault(c, [0, 0, 0, 0])
            h[0] += s[0]
            h[1] += active
            h[2] += 1
            h[3] += active
            last[c] = s[0] / active
    acc = lambda x: sum(x) / len(x) if x else float("nan")
    print(f"divisions loaded: {len(rows)}   scored: {scored} (warmup {WARMUP})")
    print(f"winner acc:  always_yes {acc(scores['always_yes']):.3f}   "
          f"club_mean {acc(scores['club_mean']):.3f}   carry_last {acc(scores['carry_last']):.3f}")
    print(f"yes_share MAE:  club_mean {sum(mae_mean)/max(len(mae_mean),1):.4f}   "
          f"carry_last {sum(mae_carry)/max(len(mae_carry),1):.4f}")

if __name__ == "__main__":
    main()
