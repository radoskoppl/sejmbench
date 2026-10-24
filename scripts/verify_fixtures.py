"""Verify fixture integrity against manifest.json sha256 pins."""

import hashlib
import json
import os

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")

manifest = json.load(open(os.path.join(FIXTURES, "manifest.json"), encoding="utf-8"))
ok = True
for fx in manifest["fixtures"]:
    path = os.path.join(os.path.dirname(FIXTURES), fx["file"])
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    status = "OK " if h == fx["sha256"] else "FAIL"
    if h != fx["sha256"]:
        ok = False
    print(f"{status} {fx['file']} {h[:12]}")
print("ALL OK" if ok else "MISMATCH")
raise SystemExit(0 if ok else 1)
