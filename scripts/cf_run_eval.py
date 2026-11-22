#!/usr/bin/env python3
"""Counterfactual spike runner (issue #15): perturbed twins → basal /v1/systemone.

Streams the perturbed divisions built by scripts/cf_build.py (default
~/cf-dump/divisions_cf.jsonl on the machine that ran the build), sends each
one to the basal server with the SAME frozen prompt contract as
run_term10_eval.py (corpus v0.4, outcome question, temperature 0, single
attempt per item with transport retries), and writes per-item submissions
consumable by a separate counterfactual scorer — never the accuracy
scorecard (issue #15: separate track).

Arm A (original answers) comes from an existing committed run — e.g.
results/m3-preview-term10 (same model/rev/engine) — so only the 208
perturbed items need GPU time. Pass --original-dir to point at it; items
missing there are recorded as missing in status.json (the report counts
only items present in BOTH arms).

Resume: rerun skips items whose output file exists (same contract as
run_term10_eval.py; transport errors are retried, content never re-rolled).
Status: <out>/status.json.

Usage (on the GPU host, after basal-serve is up):
  python3 scripts/cf_run_eval.py --server http://localhost:8000 \
      --cf-dump ~/cf-dump --out ~/cf-dump/run-mini \
      --model-id "basal-omni-2.0-mini-preview @ 2.8.1 fast (rev 2c8a5783, cf)"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import scoring  # noqa: E402

PROMPT_HASH = scoring.corpus_reference_prompt_v04_hash()
MAX_TRANSPORT_RETRIES = 3

STATE_TMPL = ("Sejm, kadencja {term}, posiedzenie {sitting}, głosowanie nr {vn}.\n"
              "Rekordy imienne (club | vote):\n{lines}")

QUESTIONS = {
    "wynik": {
        "type": "choice",
        "instructions": "Jaki był rzeczywisty wynik tego głosowania? (głosy ZA / PRZECIW / remis)",
        "criteria": {
            "za": "więcej głosów ważnych ZA niż PRZECIW",
            "przeciw": "więcej głosów ważnych PRZECIW niż ZA",
            "remis": "liczba głosów ZA równa się liczbie PRZECIW (w tym 0:0)",
            "nie_do_okreslenia": "dane nie pozwalają rozstrzygnąć",
        },
    }
}


def post(server: str, payload: dict, timeout: int = 120):
    last = None
    for attempt in range(1, MAX_TRANSPORT_RETRIES + 1):
        try:
            req = urllib.request.Request(
                server + "/v1/systemone",
                data=json.dumps(payload).encode(),
                headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read()), attempt
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            time.sleep(2 * attempt)
    raise RuntimeError(f"transport failed after {MAX_TRANSPORT_RETRIES} attempts: {last}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default="http://localhost:8000")
    ap.add_argument("--cf-dump", default=os.path.expanduser("~/cf-dump"),
                    help="directory with divisions_cf.jsonl + manifest-cf.json (from cf_build.py)")
    ap.add_argument("--out", default=None,
                    help="output dir for submissions (default <cf-dump>/run)")
    ap.add_argument("--model-id", default="counterfactual run (local basal)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N items (smoke)")
    args = ap.parse_args()

    out = args.out or os.path.join(args.cf_dump, "run")
    jsonl_path = os.path.join(args.cf_dump, "divisions_cf.jsonl")
    if not os.path.exists(jsonl_path):
        raise SystemExit(f"missing {jsonl_path} — run scripts/cf_build.py first")

    rows = []
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
    print(f"population: {len(rows)} items", file=sys.stderr)

    os.makedirs(out, exist_ok=True)
    t_start = time.time()
    done = errors = 0
    status_path = os.path.join(out, "status.json")

    def write_status(cur_id):
        n = done + errors
        eta = (time.time() - t_start) / max(n, 1) * (len(rows) - n) if n else 0
        with open(status_path + ".tmp", "w") as fh:
            json.dump({"done": done, "errors": errors, "total": len(rows),
                       "eta_s": round(eta), "last_id": cur_id}, fh)
        os.replace(status_path + ".tmp", status_path)

    for d in rows:
        item_id = f"term{d['term']}-s{d['sitting']}-v{d['votingNumber']}"
        out_path = os.path.join(out, item_id + ".json")
        if os.path.exists(out_path):
            done += 1
            continue
        lines = "\n".join(f"{v['club']} | {v['vote']}" for v in d["votes"])
        payload = {"state": {"message": STATE_TMPL.format(
                       term=d["term"], sitting=d["sitting"],
                       vn=d["votingNumber"], lines=lines)},
                   "questions": QUESTIONS}
        try:
            resp, attempts = post(args.server, payload)
        except RuntimeError as exc:
            errors += 1
            print(f"ERROR {item_id}: {exc}", file=sys.stderr, flush=True)
            write_status(item_id)
            continue
        ans = resp["answers"]["wynik"]
        choice = ans.get("choice")
        rec = {"model": args.model_id,
               "date": time.strftime("%Y-%m-%d"),
               "temperature": 0,
               "prompt_hash": PROMPT_HASH,
               "declared_cutoff": "unknown",
               "fixture": item_id + ".json",
               "raw_output": {"choice": choice,
                              "confidence": ans.get("confidence"),
                              "probabilities": ans.get("probabilities"),
                              "abstain": ans.get("abstain")},
               "input_tokens": resp.get("usage", {}).get("input_tokens"),
               "context_overflow": False,
               "inference_attempts": attempts}
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False)
        os.replace(tmp, out_path)
        done += 1
        if args.limit and done >= args.limit:
            break
        if done % 25 == 0:
            write_status(item_id)
            print(f"{done}/{len(rows)} errors={errors} "
                  f"eta={round((time.time()-t_start)/done*(len(rows)-done))}s",
                  file=sys.stderr, flush=True)
    write_status("done")
    print(f"DONE done={done} errors={errors} elapsed={round(time.time()-t_start)}s",
          file=sys.stderr)


if __name__ == "__main__":
    main()
