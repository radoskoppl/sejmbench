#!/usr/bin/env python3
"""#9A: term-10 smoke evaluation of a local basal server (issue #9).

Streams the frozen term-10 population, sends each division to the basal
server as ONE choice question over the winner task (the typed API cannot
emit per-club numeric estimates — layer 0.2 is reported as abstained), and
writes per-item submission files consumable by `sejmbench score --set term10`.

Frozen contract for this run (do not tune mid-run):
  - prompt variant: corpus (club | vote lines), pinned hash;
  - decoding: server default, single attempt per item; transport errors
    retried up to 3x the SAME request, content never re-rolled;
  - winner mapping: za->yes, przeciw->no, nie_do_okreslenia->abstain. `remis`
    maps to ABSTAIN, never silently to yes (owner decision 2026-11-04; the
    benchmark tie convention is applied by the scorer to GT, not by the adapter).

Resume: rerun skips items whose output file exists. Status: <out>/status.json.
Usage: python3 scripts/run_term10_eval.py --server http://192.168.0.18:8000 \
         --dump ~/sejm-dump --out results/basal-9a-term10
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

PROMPT_HASH = scoring.corpus_reference_prompt_hash()
MODEL_ID = "basal-omni-1.0-ultra (local)"
MAX_TRANSPORT_RETRIES = 3

STATE_TMPL = ("Sejm, kadencja {term}, posiedzenie {sitting}, głosowanie nr {vn}.\n"
              "Rekordy imienne (club | vote):\n{lines}")

QUESTIONS = {
    "wynik": {
        "type": "choice",
        "instructions": "Która strona wygrała to głosowanie imienne?",
        "criteria": {
            "za": "więcej głosów ważnych ZA niż PRZECIW",
            "przeciw": "więcej głosów ważnych PRZECIW niż ZA",
            "remis": "liczba głosów ZA równa się liczbie PRZECIW (w tym 0:0)",
            "nie_do_okreslenia": "dane nie pozwalają rozstrzygnąć",
        },
    }
}

MAP = {"za": ("yes", False), "przeciw": ("no", False),
       "remis": (None, False), "nie_do_okreslenia": (None, False)}


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://192.168.0.18:8000")
    ap.add_argument("--dump", default=os.path.expanduser("~/sejm-dump"))
    ap.add_argument("--ids", default=os.path.join(ROOT, "docs", "population", "ids-term10.txt"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "basal-9a-term10"))
    ap.add_argument("--limit", type=int, default=0, help="stop after N items (smoke)")
    args = ap.parse_args()

    ids = set()
    with open(args.ids, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                t, s, v = line.strip().split(":")
                ids.add(f"term{t}-s{s}-v{v}")
    print(f"population: {len(ids)} items", file=sys.stderr)

    os.makedirs(args.out, exist_ok=True)
    t_start = time.time()
    done = errors = 0
    status_path = os.path.join(args.out, "status.json")

    def write_status(cur_id):
        n = done + errors
        eta = (time.time() - t_start) / max(n, 1) * (len(ids) - n)
        with open(status_path + ".tmp", "w") as fh:
            json.dump({"done": done, "errors": errors, "total": len(ids),
                       "eta_s": round(eta), "last_id": cur_id}, fh)
        os.replace(status_path + ".tmp", status_path)

    with open(os.path.join(args.dump, "divisions_3_10.jsonl"),
              encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            item_id = f"term{d['term']}-s{d['sitting']}-v{d['votingNumber']}"
            if item_id not in ids:
                continue
            out_path = os.path.join(args.out, item_id + ".json")
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
            winner, tie_flag = MAP.get(choice, (None, False))
            raw: dict = {"winner": winner} if winner else {"abstain": True}
            if winner:
                raw["tracks_abstained"] = "typed-decision API cannot emit per-club numeric estimates"
            rec = {"model": MODEL_ID,
                   "date": time.strftime("%Y-%m-%d"),
                   "temperature": 0,
                   "prompt_hash": PROMPT_HASH,
                   "declared_cutoff": "unknown",
                   "fixture": item_id + ".json",
                   "raw_output": raw,
                   "input_tokens": resp.get("usage", {}).get("input_tokens"),
                   "context_overflow": False,
                   "inference_attempts": attempts,
                   "model_answer": {"choice": choice,
                                    "confidence": ans.get("confidence"),
                                    "tie_flag": tie_flag,
                                    "probabilities": ans.get("probabilities"),
                                    "abstain": ans.get("abstain")}}
            tmp = out_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(rec, fh, ensure_ascii=False)
            os.replace(tmp, out_path)
            done += 1
            if args.limit and done >= args.limit:
                break
            if done % 50 == 0:
                write_status(item_id)
                print(f"{done}/{len(ids)} errors={errors} "
                      f"eta={round((time.time()-t_start)/done*(len(ids)-done))}s",
                      file=sys.stderr, flush=True)
    write_status("done")
    print(f"DONE done={done} errors={errors} elapsed={round(time.time()-t_start)}s",
          file=sys.stderr)


if __name__ == "__main__":
    main()
