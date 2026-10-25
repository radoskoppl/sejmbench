#!/usr/bin/env python3
"""SejmBench backtest — layer 2 (pairwise club affinity) + layer 3 (title kNN).

Chronological, prediction uses only history strictly earlier than the scored
division (no leakage). Metrics follow CODEBOOK v0.2: winner exact match
(seed rule: expected YES vs expected NO over club tracks), per-track
yes_share MAE.

Layers
  baselines : always_yes, club_mean, carry_last          (bars from v0.1)
  ewma      : recency-weighted club means (half-life H)  (drift-aware)
  affinity  : diffusion over pairwise co-voting graph    (layer 2)
  knn       : TF-IDF retrieval of most similar past division titles (layer 3)
  blend     : arithmetic mean of expected counts, affinity + knn

Club continuity (curated from MP-set overlap, term 10):
  Nowa_Lewica -> Lewica, PSL -> PSL-TD, Polska2050 -> Polska2050-TD
  (100% MP overlap, renames). Centrum / RozwojPlus / Konfederacja_KP are
  splinters, kept separate on purpose.
"""
import json
import math
import re
import sys
import zlib
from collections import defaultdict

import numpy as np

SRC = sys.argv[1] if len(sys.argv) > 1 else "divisions.jsonl"
WARMUP = 60
MIN_TRACK = 5
HL = 30                 # EWMA half-life, in divisions
LAM = 1.0               # affinity diffusion strength
ITERS = 2               # diffusion iterations
KNN_K = 5
KNN_M = 0.1             # pseudo-count weight toward prior per retrieved vote
                        # (swept: broad plateau m 0.1-0.3, k 3-10; see results)
VHASH = 1 << 15         # TF-IDF hashing vocabulary
KNN_BLOCK = 256         # rebuild CSR every N stored past vectors

CLUB_MAP = {"Nowa_Lewica": "Lewica", "PSL": "PSL-TD", "Polska2050": "Polska2050-TD"}
WORD = re.compile(r"[a-ząćęłńóśźż]{3,}")


def club(c):
    return CLUB_MAP.get(c, c)


def load():
    rows, seen = [], set()
    with open(SRC) as f:
        for line in f:
            d = json.loads(line)
            key = (d["term"], d["sitting"], d["votingNumber"])
            if key not in seen:
                seen.add(key)
                rows.append(d)
    rows.sort(key=lambda d: (d["date"] or "", d["sitting"], d["votingNumber"]))
    return rows


def agg_clubs(d):
    """club -> [yes, no, abstain]; inactive values excluded."""
    agg = defaultdict(lambda: [0, 0, 0])
    for v in d["votes"]:
        val = v["vote"]
        if val not in ("YES", "NO", "ABSTAIN"):
            continue  # ABSENT / PRESENT / VOTE_VALID: inactive per CODEBOOK v0.2
        agg[club(v["club"])][{"YES": 0, "NO": 1, "ABSTAIN": 2}[val]] += 1
    return agg


def actuals(d):
    agg = agg_clubs(d)
    tracks = {c: s for c, s in agg.items() if sum(s) >= MIN_TRACK}
    ty = sum(s[0] for s in tracks.values())
    tn = sum(s[1] for s in tracks.values())
    n = ty + tn + sum(s[2] for s in tracks.values())
    if n == 0:
        return None
    shares = {c: s[0] / sum(s) for c, s in tracks.items() if sum(s) > 0}
    return dict(winner="yes" if ty > tn else "no", shares=shares)


# ---------------------------------------------------------------- layer state
class Hist:
    def __init__(self):
        self.alpha = 1 - 0.5 ** (1.0 / HL)
        self.sum_yes = {}     # full-history counts (club_mean baseline)
        self.sum_active = {}
        self.ew_share = {}    # recency-weighted share
        self.ew_size = {}     # recency-weighted active size
        self.n_seen = {}
        self.agree = {}       # (c, c') sorted -> [agree, disagree]
        self.last_share = {}

    def update(self, d):
        agg = agg_clubs(d)
        active = {c: s for c, s in agg.items() if sum(s) > 0}
        sides = {}
        for c, s in active.items():
            if s[0] + s[1] > 0 and s[0] != s[1]:
                sides[c] = "YES" if s[0] > s[1] else "NO"
            self.n_seen[c] = self.n_seen.get(c, 0) + 1
            self.sum_yes[c] = self.sum_yes.get(c, 0) + s[0]
            self.sum_active[c] = self.sum_active.get(c, 0) + sum(s)
            share = s[0] / sum(s)
            prev = self.ew_share.get(c, share)
            self.ew_share[c] = prev + self.alpha * (share - prev)
            psize = self.ew_size.get(c, sum(s))
            self.ew_size[c] = psize + self.alpha * (sum(s) - psize)
            self.last_share[c] = share
        cs = sorted(sides)
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                k = (cs[i], cs[j])
                a = self.agree.setdefault(k, [0, 0])
                if sides[cs[i]] == sides[cs[j]]:
                    a[0] += 1
                else:
                    a[1] += 1

    def prior(self, c, gmean):
        if c in self.ew_share:
            return self.ew_share[c]
        return gmean

    def size(self, c):
        if c in self.ew_size:
            return self.ew_size[c]
        return 0.0

    def affinity(self, c, others):
        """normalized affinity weights {c': A(c,c')/sum} over other clubs."""
        w = {}
        for o in others:
            if o == c:
                continue
            a = self.agree.get((c, o) if c < o else (o, c))
            if a:
                w[o] = (a[0] + 1) / (a[0] + a[1] + 2)
        s = sum(w.values())
        if s > 0:
            w = {k: v / s for k, v in w.items()}
        return w


def predict_affinity(hist, clubs_now, gmean):
    """Jacobi-style diffusion: clubs borrow strength from past co-voters."""
    pri = {c: hist.prior(c, gmean) for c in clubs_now}
    p = dict(pri)
    for _ in range(ITERS):
        old = dict(p)
        p = {}
        for c in clubs_now:
            w = hist.affinity(c, clubs_now)
            nb = sum(w.get(o, 0.0) * old[o] for o in w)
            wsum = sum(w.values())
            p[c] = (pri[c] + LAM * nb) / (1 + LAM * wsum) if wsum > 0 else pri[c]
    return p


# ---------------------------------------------------------------- layer 3
class Tfidf:
    def __init__(self):
        self.df = defaultdict(int)
        self.n = 0
        self.vecs = []        # per stored vote: (indices, data) unit-norm
        self.flat_idx = np.zeros(0, dtype=np.int64)
        self.flat_data = np.zeros(0, dtype=np.float64)
        self.indptr = np.array([0], dtype=np.int64)
        self.norms = np.zeros(0)
        self.dirty = 0

    @staticmethod
    def text(d):
        parts = [d.get("title") or "", d.get("topic") or "", d.get("description") or ""]
        return " ".join(p for p in parts if p).lower()

    def tokenize(self, d):
        tf = defaultdict(int)
        for w in WORD.findall(self.text(d)):
            tf[zlib.crc32(w.encode()) % VHASH] += 1   # stable across runs
        return tf

    def encode(self, tf):
        v = {}
        for b, t in tf.items():
            v[b] = t * math.log(1 + self.n / (1 + self.df[b]))
        nrm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {b: x / nrm for b, x in v.items()}, v

    def add(self, d):
        tf = self.tokenize(d)
        vec, _ = self.encode(tf)   # idf from PAST docs only
        for b in tf:
            self.df[b] += 1
        self.n += 1
        self.vecs.append((sorted(vec), [vec[b] for b in sorted(vec)]))
        self.dirty += 1
        if self.dirty >= KNN_BLOCK:
            self.rebuild()

    def rebuild(self):
        if not self.dirty:
            return
        idx, data, ptr = [], [], [0]
        for vi, di in self.vecs:
            idx.extend(vi)
            data.extend(di)
            ptr.append(len(idx))
        self.flat_idx = np.array(idx, dtype=np.int64)
        self.flat_data = np.array(data, dtype=np.float64)
        self.indptr = np.array(ptr, dtype=np.int64)
        self.dirty = 0

    def knn(self, d, k=KNN_K):
        """return [(sim, vote_index)] over stored past votes, best k."""
        if self.n == 0:
            return []
        self.rebuild()
        tf = self.tokenize(d)
        q, _ = self.encode(tf)
        qi = sorted(q)
        qd = np.zeros(VHASH)
        qd[qi] = [q[b] for b in qi]
        scores = np.add.reduceat(qd[self.flat_idx] * self.flat_data,
                                 self.indptr[:-1])
        best = np.argpartition(-scores, min(k, len(scores) - 1))[:k]
        out = [(float(scores[i]), int(i)) for i in best if scores[i] > 0]
        out.sort(reverse=True)
        return out


# ---------------------------------------------------------------- main
def main():
    rows = load()
    hist = Hist()
    tfidf = Tfidf()
    past_aggs = []   # club tracks per stored division, index-aligned with vecs
    scores = defaultdict(list)
    maes = defaultdict(list)
    scored = 0
    yes_wins = 0
    for i, d in enumerate(rows):
        act = actuals(d)
        if act is None:
            continue
        if i >= WARMUP:
            scored += 1
            yes_wins += act["winner"] == "yes"
            gmean = (sum(hist.sum_yes.values()) + 1) / \
                    (sum(hist.sum_active.values()) + 2) if hist.sum_active else 0.5
            clubs_now = sorted(set(hist.ew_share) | set(act["shares"]))

            def score(name, pred_shares, sizes):
                ey = sum(pred_shares.get(c, gmean) * sizes.get(c, 0) for c in clubs_now)
                en = sum((1 - pred_shares.get(c, gmean)) * sizes.get(c, 0) for c in clubs_now)
                scores[name].append(("yes" if ey > en else "no") == act["winner"])
                for c, s in act["shares"].items():
                    if c in pred_shares:
                        maes[name].append(abs(pred_shares[c] - s))

            # baselines
            scores["always_yes"].append(act["winner"] == "yes")
            cm = {c: (hist.sum_yes.get(c, 0) + 1) / (hist.sum_active.get(c, 0) + 2)
                  for c in clubs_now}
            score("club_mean", cm, {c: hist.sum_active.get(c, 0) / max(hist.n_seen.get(c, 1), 1)
                                    for c in clubs_now})
            cl = {c: hist.last_share.get(c, gmean) for c in clubs_now}
            score("carry_last", cl, {c: hist.ew_size.get(c, 0) for c in clubs_now})

            # layer 2
            ew = {c: hist.prior(c, gmean) for c in clubs_now}
            score("ewma", ew, {c: hist.ew_size.get(c, 0) for c in clubs_now})
            aff = predict_affinity(hist, clubs_now, gmean)
            score("affinity", aff, {c: hist.ew_size.get(c, 0) for c in clubs_now})

            # layer 3: title kNN
            hits = tfidf.knn(d)
            if hits:
                knn_p = {}
                for c in clubs_now:
                    num = den = 0.0
                    for sim, vi in hits:
                        vrows = past_aggs[vi]
                        if c in vrows:
                            s = vrows[c]
                            a = sum(s)
                            if a >= MIN_TRACK:
                                w = sim * sim
                                num += w * (s[0] / a)
                                den += w
                    knn_p[c] = (num + KNN_M * aff.get(c, gmean)) / (den + KNN_M)
                sizes = {c: hist.ew_size.get(c, 0) for c in clubs_now}
                score("knn", knn_p, sizes)
                # blend: mean of expected counts (affinity + knn)
                scores["blend"] = scores.get("blend", [])
                ey_a = sum(aff.get(c, gmean) * sizes[c] for c in clubs_now)
                en_a = sum((1 - aff.get(c, gmean)) * sizes[c] for c in clubs_now)
                ey_k = sum(knn_p.get(c, gmean) * sizes[c] for c in clubs_now)
                en_k = sum((1 - knn_p.get(c, gmean)) * sizes[c] for c in clubs_now)
                scores["blend"].append(
                    ("yes" if (ey_a + ey_k) > (en_a + en_k) else "no") == act["winner"])
                for c, s in act["shares"].items():
                    if c in knn_p:
                        maes["blend"].append(abs((aff.get(c, gmean) + knn_p[c]) / 2 - s))
            # store AFTER scoring (no leakage)
        # update history AFTER scoring; index gets ALL earlier divisions too
        hist.update(d)
        past_aggs.append({c: s for c, s in agg_clubs(d).items() if sum(s) > 0})
        tfidf.add(d)
    acc = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    mae = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    print(f"divisions loaded: {len(rows)}   scored: {scored} (warmup {WARMUP})")
    print(f"winner is YES in {yes_wins / max(scored,1):.1%} of scored divisions\n")
    print(f"{'method':<12} {'winner acc':>10} {'yes_share MAE':>14}")
    for name in ["always_yes", "club_mean", "carry_last", "ewma",
                 "affinity", "knn", "blend"]:
        print(f"{name:<12} {acc(scores[name]):>10.3f} {mae(maes[name]):>14.3f}")


if __name__ == "__main__":
    main()
