#!/usr/bin/env python3
"""Upload the counterfactual spike artifacts to patrykorwat/sejmbench-results
(dataset, public) — the same channel as the model scorecards. Idempotent;
prints per-file sha256 for verification.

Files: cf/manifest-cf.json, cf/divisions_cf.jsonl, cf/manifest-cf.sha256,
cf/README-CF.md (+ any run/ submissions if present are NOT uploaded — they
belong to the run, uploaded with the card after scoring).

Usage (on ATX): ~/sejm-venv/bin/python -s ~/cf_upload.py --dir ~/cf-dump
"""
import argparse
import hashlib
import json
import os
import sys

REPO = "patrykorwat/sejmbench-results"
FILES = ["manifest-cf.json", "divisions_cf.jsonl", "manifest-cf.sha256", "README-CF.md"]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.expanduser("~/cf-dump"))
    ap.add_argument("--token-file", default=os.path.expanduser("~/.hf-token"))
    args = ap.parse_args()

    from huggingface_hub import HfApi
    token = open(args.token_file).read().strip() if os.path.exists(args.token_file) else None
    api = HfApi(token=token)

    for name in FILES:
        path = os.path.join(args.dir, name)
        if not os.path.exists(path):
            print(f"skip (missing): {name}")
            continue
        data = open(path, "rb").read()
        remote = f"cf/{name}"
        api.upload_file(path_or_fileobj=path, path_in_repo=remote,
                        repo_id=REPO, repo_type="dataset")
        print(f"uploaded cf/{name}: {len(data)} bytes sha256={sha(data)}")

    # verify: re-download the small manifest and compare
    import urllib.request
    url = f"https://huggingface.co/datasets/{REPO}/resolve/main/cf/manifest-cf.sha256"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            remote_txt = r.read().decode()
        print("remote manifest-cf.sha256:", remote_txt.strip().splitlines()[0])
        print("local  manifest-cf.sha256:",
              open(os.path.join(args.dir, "manifest-cf.sha256")).read().strip().splitlines()[0])
    except Exception as exc:  # noqa: BLE001
        print(f"verify fetch failed (may need propagation time): {exc}")


if __name__ == "__main__":
    main()
