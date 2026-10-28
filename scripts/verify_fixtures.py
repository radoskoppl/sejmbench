"""Verify fixture integrity against manifest.json sha256 pins.

Checks (exit 1 on any failure):
  * every manifest entry has `file` and `sha256` (64 hex chars)
  * no duplicate `file` entries
  * every listed file exists and matches its pin
  * every fixture *.json file is listed in the manifest (no orphans)
  * optional `layers` field, when present, is a non-empty list of known layers
"""

import glob
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")
KNOWN_LAYERS = {"0.1", "0.2", "1", "2", "3", "4"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def verify(fixtures_dir=FIXTURES):
    manifest = json.load(open(os.path.join(fixtures_dir, "manifest.json"), encoding="utf-8"))
    ok = True
    seen = set()
    for fx in manifest["fixtures"]:
        fname = fx.get("file")
        sha = fx.get("sha256")
        if not fname or not sha:
            print(f"FAIL manifest entry missing file/sha256: {fx}")
            ok = False
            continue
        if not HEX64.match(str(sha)):
            print(f"FAIL manifest sha256 not 64 hex chars: {fname}")
            ok = False
        name = os.path.basename(fname)
        if name in seen:
            print(f"FAIL duplicate manifest entry: {fname}")
            ok = False
        seen.add(name)

        layers = fx.get("layers")
        if layers is not None:
            if not isinstance(layers, list) or not layers or not set(map(str, layers)) <= KNOWN_LAYERS:
                print(f"FAIL invalid layers field for {fname}: {layers}")
                ok = False

        path = os.path.join(fixtures_dir, name)
        if not os.path.isfile(path):
            print(f"FAIL missing file {fname}")
            ok = False
            continue
        h = hashlib.sha256(open(path, "rb").read()).hexdigest()
        status = "OK " if h == sha else "FAIL"
        if h != sha:
            ok = False
        print(f"{status} {fname} {h[:12]}")

    for path in sorted(glob.glob(os.path.join(fixtures_dir, "*.json"))):
        name = os.path.basename(path)
        if name == "manifest.json":
            continue
        if name not in seen:
            print(f"FAIL orphan fixture file not in manifest: {name}")
            ok = False
    print("ALL OK" if ok else "MISMATCH")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if verify() else 1)
