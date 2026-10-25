import json, os, urllib.request

OUT = "/home/porwat/sejm-dump"
UA = {"User-Agent": "sejmbench-dump/0.1 (github.com/radoskoppl/sejmbench)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as f:
        return json.load(f)


rows = []
pdf_total = 0
for t in range(1, 13):
    try:
        lst = get("https://api.sejm.gov.pl/sejm/term" + str(t) + "/prints")
    except Exception as e:
        print("term", t, "skip:", e)
        continue
    n_pdf = sum(len(x.get("attachments") or []) for x in lst)
    pdf_total += n_pdf
    print("term", t, "prints:", len(lst), "pdfs:", n_pdf)
    for x in lst:
        num = str(x["number"])
        att = x.get("attachments") or []
        rows.append({
            "term": t,
            "number": num,
            "title": x.get("title"),
            "deliveryDate": x.get("deliveryDate"),
            "documentDate": x.get("documentDate"),
            "changeDate": x.get("changeDate"),
            "processPrint": x.get("processPrint"),
            "attachments": att,
            "attachment_urls": ["https://api.sejm.gov.pl/sejm/term" + str(t) +
                                "/prints/" + num + "/" + a for a in att],
            "source_url": "https://api.sejm.gov.pl/sejm/term" + str(t) + "/prints/" + num,
        })
rows.sort(key=lambda r: (r["term"], r["number"]))
with open(os.path.join(OUT, "druki.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("druki rows:", len(rows), "| total pdfs:", pdf_total)

from datasets import Dataset

tok = open(os.path.expanduser("~/.hf-token")).read().strip()
ds = Dataset.from_json(os.path.join(OUT, "druki.jsonl"))
ds.push_to_hub("patrykorwat/sejm-votings", config_name="druki", token=tok)
print("pushed druki:", len(ds))

card_path = os.path.join(OUT, "dataset_card.md")
s = open(card_path).read()
if "config_name: druki" not in s:
    j = s.index("\n---\n", 3)
    s = s[:j] + "\n- config_name: druki\n  data_files: \"druki/*.parquet\"" + s[j:]
    open(card_path, "w").write(s)
from huggingface_hub import HfApi

HfApi(token=tok).upload_file(
    path_or_fileobj=card_path, path_in_repo="README.md",
    repo_id="patrykorwat/sejm-votings", repo_type="dataset",
    commit_message="Add druki config (Sejm prints metadata + PDF urls)")
print("card updated")
