"""Cross-process determinism of the cf_build.py generator (issue #15 review P1).

Runs scripts/cf_build.py twice in separate subprocesses with RANDOMIZED hash
seeds (PYTHONHASHSEED=random) over a tiny synthetic dump, and asserts the two
runs produce byte-identical outputs — the SHA-256-derived per-item seeds must
not depend on Python's salted hash().
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "scripts", "cf_build.py")


def _make_fixture_repo(tmp_path):
    """Minimal repo: seed_rule importable, ids list, 4-row synthetic dump."""
    repo = tmp_path / "repo"
    (repo / "docs" / "population").mkdir(parents=True)
    with open(os.path.join(ROOT, "seed_rule.py"), encoding="utf-8") as fh:
        src = fh.read()
    (repo / "seed_rule.py").write_text(src, encoding="utf-8")
    rows = []
    # 4 divisions: margins 4 (narrow), 30 (close), 200 (wide), plus one extra
    # for the reorder/pseudonymize pool
    for i, (yes, no) in enumerate([(52, 48), (115, 85), (300, 100), (60, 40)]):
        rows.append({
            "term": 10, "sitting": 1, "votingNumber": i + 1,
            "date": "2025-01-01T12:00:00", "title": f"t{i}", "topic": None,
            "description": None, "kind": "ELECTRONIC",
            "yes": yes, "no": no, "abstain": 0, "notParticipating": 0,
            "present": 0, "totalVoted": yes + no, "sittingDay": 1,
            "votes": ([{"MP": j, "club": "A", "vote": "YES"} for j in range(yes)]
                      + [{"MP": 1000 + j, "club": "B", "vote": "NO"}
                         for j in range(no)]),
        })
    dump = tmp_path / "dump"
    dump.mkdir()
    with open(dump / "divisions_3_10.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(repo / "docs" / "population" / "ids-term10.txt", "w") as fh:
        for r in rows:
            fh.write(f"{r['term']}:{r['sitting']}:{r['votingNumber']}\n")
    return str(repo), str(dump)


def _run_build(repo, dump, out, env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    r = subprocess.run([sys.executable, CF, "--repo", repo, "--dump", dump,
                        "--out", out],
                       capture_output=True, text=True, env=env, timeout=300)
    assert r.returncode == 0, r.stderr
    return r


def test_cf_build_byte_identical_across_processes(tmp_path):
    repo, dump = _make_fixture_repo(tmp_path)
    r1 = _run_build(repo, dump, str(tmp_path / "out1"),
                    {"PYTHONHASHSEED": "1"})
    r2 = _run_build(repo, dump, str(tmp_path / "out2"),
                    {"PYTHONHASHSEED": "2"})
    for name in ("manifest-cf.json", "divisions_cf.jsonl", "ids-cf.txt",
                 "manifest-cf.sha256"):
        a = (tmp_path / "out1" / name).read_bytes()
        b = (tmp_path / "out2" / name).read_bytes()
        assert a == b, f"{name} differs between processes"
    # and the recorded shas match the files
    manifest = json.loads((tmp_path / "out1" / "manifest-cf.json").read_text())
    jl = (tmp_path / "out1" / "divisions_cf.jsonl").read_bytes()
    assert manifest["jsonl"]["sha256"] == hashlib.sha256(jl).hexdigest()


def test_cf_manifest_records_perturbed_sha(tmp_path):
    """Every item records the sha256 of BOTH the original and the modified records."""
    repo, dump = _make_fixture_repo(tmp_path)
    _run_build(repo, dump, str(tmp_path / "out"), {"PYTHONHASHSEED": "0"})
    manifest = json.loads((tmp_path / "out" / "manifest-cf.json").read_text())
    for e in manifest["items"]:
        assert "records_sha256_original" in e
        assert "records_sha256_perturbed" in e
    # headline counters of flipped items recomputed from modified records
    by_id = {f"term{r['term']}-s{r['sitting']}-v{r['votingNumber']}": r
             for r in (json.loads(l) for l in
                       (tmp_path / "out" / "divisions_cf.jsonl").read_text().splitlines())}
    for e in manifest["items"]:
        if e["perturbation"] != "flip":
            continue
        dp = by_id[e["item_id"]]
        tally = {}
        for v in dp["votes"]:
            tally[v["vote"]] = tally.get(v["vote"], 0) + 1
        assert dp["yes"] == tally.get("YES", 0)
        assert dp["no"] == tally.get("NO", 0)
        assert dp["abstain"] == tally.get("ABSTAIN", 0)


def test_cf_manifest_records_shortfalls(tmp_path):
    repo, dump = _make_fixture_repo(tmp_path)
    _run_build(repo, dump, str(tmp_path / "out"), {"PYTHONHASHSEED": "0"})
    manifest = json.loads((tmp_path / "out" / "manifest-cf.json").read_text())
    # the synthetic dump has few narrow items — the shortfall must be recorded
    narrow = manifest["quotas"]["flip_narrow"]
    assert narrow["generated"] < narrow["requested"]
    assert narrow["shortfall_reason"]
