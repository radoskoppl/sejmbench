import json, os, time
from urllib.parse import quote
import threading
import concurrent.futures as cf
import requests

OUT = "/home/porwat/sejm-dump"
BASE = os.path.join(OUT, "pdfs")
UA = "sejmbench-dump/0.1 (github.com/radoskoppl/sejmbench)"

rows = [json.loads(l) for l in open(os.path.join(OUT, "druki.jsonl"), encoding="utf-8")]
tasks = []
for r in rows:
    safe = str(r["number"]).replace("/", "_").strip()
    for url in r["attachment_urls"]:
        raw_name = url.rsplit("/", 1)[1]
        fname = " ".join(raw_name.split())  # normalize whitespace/newlines
        path = "/sejm/term" + str(r["term"]) + "/prints/" + str(r["number"]) + "/" + fname
        url_q = "https://api.sejm.gov.pl" + quote(path, safe="/")
        dest = os.path.join(BASE, "term" + str(r["term"]), safe, fname)
        tasks.append((url_q, dest))
print("pdf tasks:", len(tasks), flush=True)

tl = threading.local()


def fetch(t):
    url, dest = t
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return "skip"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    try:
        s = getattr(tl, "s", None)
        if s is None:
            s = requests.Session()
            s.headers["User-Agent"] = UA
            tl.s = s
        r = s.get(url, timeout=120)
        if r.status_code != 200 or len(r.content) < 100:
            with open("/home/porwat/sejm-dump/bad_urls.txt", "a") as bf:
                bf.write(str(r.status_code) + "\t" + url + "\n")
            return "bad:" + str(r.status_code)
        with open(tmp, "wb") as f:
            f.write(r.content)
        os.replace(tmp, dest)
        return "ok"
    except Exception as e:
        return "err:" + str(e)[:60]


ok = skip = bad = err = 0
t0 = time.time()
with cf.ThreadPoolExecutor(24) as ex:
    for i, res in enumerate(ex.map(fetch, tasks)):
        if res == "skip":
            skip += 1
        elif res == "ok":
            ok += 1
        elif res.startswith("bad"):
            bad += 1
        else:
            err += 1
            if err <= 50:
                print("ERR", res, flush=True)
        if (i + 1) % 500 == 0:
            rate = (ok + skip + bad + err) / (time.time() - t0)
            print(f"[{i+1}/{len(tasks)}] ok={ok} skip={skip} bad={bad} err={err} rate={rate:.1f}/s", flush=True)

print("DONE ok=", ok, "skip=", skip, "bad=", bad, "err=", err, flush=True)
raise SystemExit(0 if (ok + skip) >= (ok + skip + bad + err) * 0.9 else 1)
