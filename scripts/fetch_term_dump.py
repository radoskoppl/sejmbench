#!/usr/bin/env python3
"""Download all term-10 roll-call divisions (detail level) to JSONL, resumable."""
import json, os, urllib.request, sys, time

OUT = "/opt/data/cache/scratch/sejmbench/divisions.jsonl"
UA = {"User-Agent": "sejmbench-backtest/0.1 (github.com/radoskoppl/sejmbench)"}

def get(u):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

have = set()
if os.path.exists(OUT):
    with open(OUT) as f:
        for line in f:
            try:
                d = json.loads(line)
                have.add((d["term"], d["sitting"], d["votingNumber"]))
            except Exception:
                pass
print(f"already have {len(have)}", flush=True)

targets = []
for sitting in range(1, 80):
    try:
        lst = get(f"https://api.sejm.gov.pl/sejm/term10/votings/{sitting}")
    except Exception:
        continue
    if not lst:
        continue
    for x in lst:
        key = (10, x["sitting"], x["votingNumber"])
        if key not in have:
            targets.append(key)
print(f"targets {len(targets)}", flush=True)

with open(OUT, "a") as f:
    for i, (t, s, v) in enumerate(targets):
        for attempt in (1, 2, 3):
            try:
                d = get(f"https://api.sejm.gov.pl/sejm/term{t}/votings/{s}/{v}")
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
                f.flush()
                break
            except Exception as e:
                time.sleep(1.5 * attempt)
        if i % 50 == 0:
            print(f"{i}/{len(targets)}", flush=True)
print("DONE", flush=True)
