import gzip, json, os, urllib.request

RAW = "/home/porwat/sejm-dump/raw"
OUT = "/home/porwat/sejm-dump"
UA = {"User-Agent": "sejmbench-dump/0.1 (github.com/radoskoppl/sejmbench)"}


def get(u):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as f:
        return json.load(f)


VF = ("term", "sitting", "votingNumber", "date", "sittingDay", "title", "topic",
      "description", "motion", "kind", "yes", "no", "abstain", "notParticipating",
      "present", "totalVoted", "majorityType", "majorityVotes", "votingOptions", "links")

rows = []
for tdir in sorted(os.listdir(RAW)):
    for sdir in sorted(os.listdir(os.path.join(RAW, tdir))):
        for fn in sorted(os.listdir(os.path.join(RAW, tdir, sdir))):
            p = os.path.join(RAW, tdir, sdir, fn)
            with gzip.open(p, "rt", encoding="utf-8") as f:
                d = json.load(f)
            r = {k: d.get(k) for k in VF}
            vno = int(fn.split(".")[0].lstrip("v"))
            t_ = str(d["term"])
            s_ = str(d["sitting"])
            r["source_url"] = "https://api.sejm.gov.pl/sejm/term" + t_ + "/" + s_ + "/" + str(vno)
            rows.append(r)
rows.sort(key=lambda r: (int(r["term"]), int(r["sitting"]), int(r["votingNumber"])))
with open(os.path.join(OUT, "votings.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("votings rows:", len(rows))

srows = []
for t in range(1, 13):
    try:
        days = get("https://api.sejm.gov.pl/sejm/term" + str(t) + "/votings")
    except Exception as e:
        print("term", t, "skip:", e)
        continue
    for day in days:
        pr = str(day["proceeding"])
        srows.append({
            "term": t,
            "sitting": day["proceeding"],
            "date": day["date"],
            "votingsNum": day["votingsNum"],
            "source_url": "https://api.sejm.gov.pl/sejm/term" + str(t) + "/votings/" + pr,
        })
    print("term", t, "day-rows:", len(days))
with open(os.path.join(OUT, "sittings.jsonl"), "w", encoding="utf-8") as f:
    for r in srows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("sittings day-rows total:", len(srows))

from datasets import Dataset

tok = open(os.path.expanduser("~/.hf-token")).read().strip()
for cfg, path in (("votings", "votings.jsonl"), ("sittings", "sittings.jsonl")):
    ds = Dataset.from_json(os.path.join(OUT, path))
    ds.push_to_hub("patrykorwat/sejm-votings", config_name=cfg, token=tok)
    print("pushed:", cfg, len(ds))

card_path = os.path.join(OUT, "dataset_card.md")
s = open(card_path).read()
if "config_name: sittings" not in s:
    j = s.index("\n---\n", 3)
    s = s[:j] + "\n- config_name: sittings\n  data_files: \"sittings/*.parquet\"" + s[j:]
    open(card_path, "w").write(s)
from huggingface_hub import HfApi

HfApi(token=tok).upload_file(
    path_or_fileobj=card_path, path_in_repo="README.md",
    repo_id="patrykorwat/sejm-votings", repo_type="dataset",
    commit_message="Add sittings config; enrich votings with sittingDay")
print("card updated")
