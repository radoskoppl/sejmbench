import json, os, subprocess

OUT = "/home/porwat/sejm-dump"
BASE = os.path.join(OUT, "pdfs")
TARGET_EXT = (".doc", ".docm", ".dotx", ".xls", ".xlsx")

rows = []
with open(os.path.join(OUT, "druk_texts.jsonl"), encoding="utf-8") as f:
    for line in f:
        rows.append(json.loads(line))
print("loaded:", len(rows), flush=True)


def extract(dest):
    # catdoc first (UTF-8 output, good Polish), antiword as fallback
    try:
        r = subprocess.run(["catdoc", "-d", "utf-8", "-x", "txt", dest],
                           capture_output=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.decode("utf-8", "replace"), None
    except Exception as e:
        pass
    try:
        r = subprocess.run(["antiword", "-m", "utf-8.txt", dest],
                           capture_output=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.decode("utf-8", "replace"), None
        if r.returncode == 0:
            return "", "doc-empty"
        return "", "doc-fail-rc" + str(r.returncode)
    except Exception as e:
        return "", str(e)[:80]


fixed = still = 0
for i, r in enumerate(rows):
    err = r.get("error") or ""
    att = r["attachment"]
    ext = ("." + att.rsplit(".", 1)[-1].lower()) if "." in att else ""
    if not (err.startswith("no-extractor")
            or (ext == ".docm" and err.startswith("file"))):
        continue
    if ext == ".xlsx":
        still += 1
        continue
    dest = os.path.join(BASE, "term" + str(r["term"]),
                        r["number"].replace("/", "_"), att)
    if not os.path.exists(dest):
        still += 1
        continue
    text, e = extract(dest)
    if text:
        r["text"] = text
        r["text_len"] = len(text)
        r["error"] = None
        fixed += 1
    else:
        r["error"] = e
        still += 1
    if (fixed + still) % 1000 == 0:
        print("processed", fixed + still, "fixed", fixed, flush=True)

print("fixed:", fixed, "still-failed:", still, flush=True)
with open(os.path.join(OUT, "druk_texts.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

from datasets import Dataset

tok = open(os.path.expanduser("~/.hf-token")).read().strip()
ds = Dataset.from_json(os.path.join(OUT, "druk_texts.jsonl"))
ds.push_to_hub("patrykorwat/sejm-votings", config_name="druk_texts", token=tok)
print("pushed:", len(ds), flush=True)
