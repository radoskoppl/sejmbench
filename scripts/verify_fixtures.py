"""Verify fixture integrity against manifest.json sha256 pins.

Checks (exit 1 on any failure):
  * every manifest entry has `file` and `sha256`
  * no duplicate `file` entries
  * every listed file exists and matches its pin
  * optional `layers` field, when present, is a non-empty list of known layers
"""

import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")
KNOWN_LAYERS = {"0.1", "0.2", "1", "2", "3", "4"}

manifest = json.load(open(os.path.join(FIXTURES, "manifest.json"), encoding="utf-8"))
ok = True
seen = set()

for fx in manifest["fixtures"]:
    fname = fx.get("file")
    if not fname or not fx.get("sha256"):
        print(f"FAIL manifest entry missing file/sha256: {fx}")
        ok = False
        continue
    if fname in seen:
        print(f"FAIL duplicate manifest entry: {fname}")
        ok = False
    seen.add(fname)

    layers = fx.get("layers")
    if layers is not None:
        if not isinstance(layers, list) or not layers or not set(map(str, layers)) <= KNOWN_LAYERS:
            print(f"FAIL invalid layers field for {fname}: {layers}")
            ok = False

    path = os.path.join(ROOT, fname)
    if not os.path.isfile(path):
        print(f"FAIL missing file {fname}")
        ok = False
        continue
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    status = "OK " if h == fx["sha256"] else "FAIL"
    if h != fx["sha256"]:
        ok = False
    print(f"{status} {fname} {h[:12]}")

print("ALL OK" if ok else "MISMATCH")
raise SystemExit(0 if ok else 1)
