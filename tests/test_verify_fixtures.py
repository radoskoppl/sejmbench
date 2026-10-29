import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import verify_fixtures  # noqa: E402


def _make(tmp_path, entries, files):
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"fixtures": entries}), encoding="utf-8")
    return verify_fixtures.verify(str(tmp_path))


def _data():
    return json.dumps({"votes": []})


def _sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def test_valid_manifest_passes(tmp_path):
    data = _data()
    assert _make(tmp_path, [{"file": "a.json", "sha256": _sha(data)}], {"a.json": data}) is True


def test_tampered_file_fails(tmp_path):
    data = _data()
    assert _make(tmp_path, [{"file": "a.json", "sha256": _sha(data)}], {"a.json": data + " "}) is False


def test_orphan_file_fails(tmp_path):
    data = _data()
    sha = _sha(data)
    assert _make(tmp_path, [{"file": "a.json", "sha256": sha}], {"a.json": data, "b.json": "{}"}) is False


def test_duplicate_entry_fails(tmp_path):
    data = _data()
    sha = _sha(data)
    entries = [{"file": "a.json", "sha256": sha}, {"file": "a.json", "sha256": sha}]
    assert _make(tmp_path, entries, {"a.json": data}) is False


def test_bad_sha_format_fails(tmp_path):
    data = _data()
    assert _make(tmp_path, [{"file": "a.json", "sha256": "abc"}], {"a.json": data}) is False


def test_missing_sha_fails(tmp_path):
    data = _data()
    assert _make(tmp_path, [{"file": "a.json"}], {"a.json": data}) is False


def test_layers_valid_and_invalid(tmp_path):
    data = _data()
    sha = _sha(data)
    assert _make(tmp_path, [{"file": "a.json", "sha256": sha, "layers": ["0.1"]}], {"a.json": data}) is True
    assert _make(tmp_path, [{"file": "a.json", "sha256": sha, "layers": ["9.9"]}], {"a.json": data}) is False
    assert _make(tmp_path, [{"file": "a.json", "sha256": sha,
                             "layers": {"0.1": True, "0.2": True, "1": False}}], {"a.json": data}) is True
    assert _make(tmp_path, [{"file": "a.json", "sha256": sha,
                             "layers": {"9.9": True}}], {"a.json": data}) is False
    assert _make(tmp_path, [{"file": "a.json", "sha256": sha,
                             "layers": {"0.1": "yes"}}], {"a.json": data}) is False
    assert _make(tmp_path, [{"file": "a.json", "sha256": sha,
                             "layers": {}}], {"a.json": data}) is False


def test_selection_file_is_not_an_orphan(tmp_path):
    data = _data()
    sha = _sha(data)
    files = {"a.json": data, "selection.json": json.dumps({"seed": 20261027})}
    assert _make(tmp_path, [{"file": "a.json", "sha256": sha}], files) is True
