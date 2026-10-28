"""Layer 1 vote-type classifier (SejmBench, issue #2).

Deterministic mapping from official Sejm API `description` strings to vote-type
buckets. Ground truth comes only from official strings (no third-party labels).

Matching semantics (CODEBOOK section 10):
  1. normalize: NFC, documented repairs, casefold, whitespace collapse
  2. apply ordered rules; first match wins; `contains` requires the needle as
     a substring, `prefix` requires the needle at the start; `and_any` lists
     additional needles of which at least one must also be present
  3. fallback: `unspecified`

Status: dictionary v0.1.0-draft - pending the hand-coded validation sample;
layer-1 scores may not be published until the dictionary is frozen.
"""

import json
import re
import os
import unicodedata

_HERE = os.path.dirname(os.path.abspath(__file__))
DICTIONARY_PATH = os.path.join(_HERE, "layer1_dictionary.json")


def normalize(text, repairs, strip=True):
    """Normalize an official description string.

    Order matters: NFC -> casefold -> documented repairs (keys lowercase, so
    case variants of an artifact are caught) -> whitespace collapse.
    strip=False preserves leading/trailing whitespace: needle normalization
    uses it so a leading space acts as a word-boundary anchor
    (" i czytaniu" must not match "w ii czytaniu").
    """
    if text is None:
        return ""
    s = unicodedata.normalize("NFC", str(text))
    s = s.casefold()
    for bad, good in repairs:
        s = s.replace(bad, good)
    s = re.sub(r"\s+", " ", s)
    return s.strip() if strip else s


def load_dictionary(path=DICTIONARY_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rule_matches(rule, t, repairs):
    needle = normalize(rule["needle"], repairs, strip=False)
    hit = t.startswith(needle) if rule["match"] == "prefix" else needle in t
    if not hit:
        return False
    extra = rule.get("and_any")
    if extra and not any(normalize(x, repairs, strip=False) in t for x in extra):
        return False
    excl = rule.get("not_contains")
    if excl and any(normalize(x, repairs, strip=False) in t for x in excl):
        return False
    return True


def classify(text, dictionary):
    """Return the bucket for an official description string (or fallback)."""
    if text is None:
        return dictionary["fallback"]
    norm_cfg = dictionary["normalization"]
    repairs = [tuple(r) for r in norm_cfg.get("repairs", [])]
    t = normalize(text, repairs)
    for rule in dictionary["rules"]:
        if _rule_matches(rule, t, repairs):
            return rule["bucket"]
    return dictionary["fallback"]


def classify_all(text, dictionary):
    """Return the deduped list of buckets matched by all rules (conflict audit).

    Used by the coverage report: a formula matching more than one bucket is a
    rule-order conflict that the dictionary must resolve explicitly.
    """
    if text is None:
        return []
    norm_cfg = dictionary["normalization"]
    repairs = [tuple(r) for r in norm_cfg.get("repairs", [])]
    t = normalize(text, repairs)
    out = []
    for rule in dictionary["rules"]:
        if _rule_matches(rule, t, repairs) and rule["bucket"] not in out:
            out.append(rule["bucket"])
    return out


if __name__ == "__main__":
    import sys

    d = load_dictionary(sys.argv[1] if len(sys.argv) > 1 else DICTIONARY_PATH)
    print(f"dictionary {d['version']} ({d['status'][:40]}...), {len(d['rules'])} rules")
    for sample in sys.argv[2:]:
        print(f"  {classify(sample, d):24s} <= {sample[:70]}")
