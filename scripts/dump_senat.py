#!/usr/bin/env python3
"""Senate roll-call mirror (dump_senat.py) - analog of dump_sejm_hf.py.

Source: senat.gov.pl (server-rendered HTML, robots.txt allows /prace/).
  * posiedzenia list (paginated, 65/page): /prace/posiedzenia/?page=N
  * per posiedzenie, per day: /prace/posiedzenia/przebieg,{pid},{day},glosowania.html
  * per voting row: number, title, type + voting-results:
      imienne  href="#" rel="id_{gid}"          (ajax per-senator view)
      kluby    szczegoly-glosowania,{pos},{nr},{kadencja}.html   (canonical key)
      drukuj   glosowanie-drukuj,{gid}.html      (print view: counts + roll-call)
  * print view: title, type, counts (glosowalo/za/przeciw/wstrzymalo) and
    100 <div class="senator"> blocks: name + vote as text (za/przeciw/wstrz./n.).

Output (JSONL, one voting per line):
  senat_votings.jsonl: {glosowanie_id, pos, nr, kadencja, przebieg_id, day,
                        number, title, typ, glosowalo, za, przeciw, wstrzymalo,
                        glosowanie_url}
  senat_votes.jsonl:   {glosowanie_id, senator, vote_raw, vote}

Usage:
  python3 dump_senat.py --posiedzenie 663          # scrape one posiedzenie (test)
  python3 dump_senat.py --pages 3                  # first 3 list pages
  python3 dump_senat.py --all                      # full archive
  python3 dump_senat.py --check-new --max-known 14783   # incremental: IDs > max-known
"""

import argparse
import collections
import html
import json
import os
import re
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
BASE = "https://www.senat.gov.pl"

VOTE_MAP = (("za", "ZA"), ("przec", "PRZECIW"), ("wstrz", "WSTRZYMAŁ_SIĘ"),
            ("nieob", "NIEOBECNY"), ("n.", "NIEOBECNY"), ("nie g", "NIE_GŁOSOWAŁ"))


def fetch(url, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def strip_tags(fragment):
    txt = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"\s+", " ", txt).strip()


def norm_vote(raw):
    v = raw.strip().lower()
    for prefix, vote in VOTE_MAP:
        if v.startswith(prefix):
            return vote
    return v.upper() or "NIEZNANY"


def list_posiedzenia(pages):
    """Posiedzenia from the list: {pid: {title, days: set}} via przebieg links."""
    pos = {}
    for page in range(1, pages + 1):
        t = fetch(f"{BASE}/prace/posiedzenia/?page={page}")
        links = re.findall(r'href="(/prace/posiedzenia/przebieg,(\d+),(\d+),[^"]+)"[^>]*>([\s\S]{0,300}?)</a>', t)
        if not links:
            break
        for _href, pid, day, anchor in links:
            pid, day = int(pid), int(day)
            rec = pos.setdefault(pid, {"pid": pid, "title": "", "days": set()})
            rec["days"].add(day)
            title = strip_tags(anchor)
            if title and (not rec["title"] or len(title) > len(rec["title"])):
                if "wersja do druku" not in title and "głosowania" not in title.lower():
                    rec["title"] = title
    return pos


MONTHS = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
          "lipca": 7, "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12}


def parse_day_date(fragment):
    m = re.search(r"(\d{1,2})\s+(stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)\s+(\d{4})", fragment)
    if m:
        return f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    return None


def parse_day_page(t, pid, day):
    """One glosowania day page -> voting records.

    Rows are <hr>-separated; each segment: [number][title][typ][imienne]
    [kluby i koło][wersja do druku] + the ogolne-wyniki counts header.
    """
    out = []
    for seg in re.split(r"<hr[^>]*>", t):
        m_rel = re.search(r'rel="id_(\d+)"', seg)
        m_kluby = re.search(r"szczegoly-glosowania,(\d+),(\d+),(\d+)\.html", seg)
        m_drukuj = re.search(r"glosowanie-drukuj,(\d+)\.html", seg)
        if not (m_rel or m_drukuj or m_kluby):
            continue
        lines = [x for x in (html.unescape(re.sub(r"<[^>]+>", "", ln)).strip()
                             for ln in seg.split("\n")) if x]
        i_ymi = next((i for i, x in enumerate(lines) if x == "imienne"), None)
        number = title = typ = None
        if i_ymi:
            pre = lines[:i_ymi]
            num_idx = next((i for i in range(len(pre) - 1, max(-1, len(pre) - 7), -1)
                            if re.fullmatch(r"\d{1,3}", pre[i])), None)
            if num_idx is not None:
                number = pre[num_idx]
                title = pre[num_idx + 1] if num_idx + 1 < len(pre) else None
                typ = " ".join(pre[num_idx + 2:]) or None
        gid = int(m_rel.group(1)) if m_rel else (int(m_drukuj.group(1)) if m_drukuj else None)
        if gid is None:
            continue
        out.append({
            "glosowanie_id": gid,
            "pos": int(m_kluby.group(1)) if m_kluby else None,
            "nr": int(m_kluby.group(2)) if m_kluby else None,
            "kadencja": int(m_kluby.group(3)) if m_kluby else None,
            "przebieg_id": pid,
            "day": day,
            "date": parse_day_date(seg) or parse_day_date(t),
            "number": number,
            "title": title,
            "typ": typ,
            "glosowanie_url": f"{BASE}/prace/posiedzenia/glosowanie-drukuj,{gid}.html",
        })
    return out


def parse_print(t):
    """Print view -> (counts, roll-call)."""
    counts = {}
    body = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", t)
    txt = html.unescape(re.sub(r"<[^>]+>", "\n", body))
    for label, key in (("głosowało:", "glosowalo"), ("za:", "za"), ("przeciw:", "przeciw"),
                       ("wstrzymało się:", "wstrzymalo")):
        m = re.search(re.escape(label) + r"\s*\n?\s*(\d+)", txt)
        if m:
            counts[key] = int(m.group(1))
    votes = []
    for m in re.finditer(
            r'<div class="senator">\s*<div class="col-lg-3[^"]*">\s*([^<]+?)\s*</div>\s*'
            r'<div class="col-lg-1[^"]*">\s*([^<]+?)\s*</div>', t):
        name = html.unescape(m.group(1)).strip()
        raw = html.unescape(m.group(2)).strip()
        votes.append({"senator": name, "vote_raw": raw, "vote": norm_vote(raw)})
    return counts, votes


def scrape_posiedzenie(pid, day, out_v, out_s, seen):
    t = fetch(f"{BASE}/prace/posiedzenia/przebieg,{pid},{day},glosowania.html")
    rows = parse_day_page(t, pid, day)
    got = 0
    for rec in rows:
        gid = rec["glosowanie_id"]
        if gid in seen:
            continue
        seen.add(gid)
        pt = fetch(rec["glosowanie_url"])
        counts, votes = parse_print(pt)
        rec.update(counts)
        out_v.write(json.dumps(rec, ensure_ascii=False) + "\n")
        for v in votes:
            v["glosowanie_id"] = gid
            out_s.write(json.dumps(v, ensure_ascii=False) + "\n")
        got += 1
        time.sleep(0.15)
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--posiedzenie", type=int, help="scrape a single posiedzenie (all its days)")
    ap.add_argument("--days", type=int, default=0, help="limit days per posiedzenie (0 = all)")
    ap.add_argument("--pages", type=int, default=1, help="list pages to enumerate")
    ap.add_argument("--all", action="store_true", help="enumerate all list pages")
    ap.add_argument("--out-dir", default="senat-dump")
    ap.add_argument("--check-new", action="store_true", help="incremental: IDs > --max-known only")
    ap.add_argument("--max-known", type=int, default=0)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    fv = open(os.path.join(args.out_dir, "senat_votings.jsonl"), "a", encoding="utf-8")
    fs = open(os.path.join(args.out_dir, "senat_votes.jsonl"), "a", encoding="utf-8")
    seen = set()

    if args.check_new:
        # incremental: newest list page only; skip glosowanie_id <= max_known
        t = fetch(f"{BASE}/prace/posiedzenia/?page=1")
        pids = sorted({int(p) for p in re.findall(r"przebieg,(\d+),\d+,glosowania\.html", t)}, reverse=True)
        total = 0
        for pid in pids[:3]:
            day = 1
            while True:
                t_day = fetch(f"{BASE}/prace/posiedzenia/przebieg,{pid},{day},glosowania.html")
                rows = parse_day_page(t_day, pid, day)
                fresh = [r for r in rows if r["glosowanie_id"] > args.max_known]
                if not fresh and day > 1:
                    break
                if not rows:
                    break
                for rec in fresh:
                    if rec["glosowanie_id"] in seen:
                        continue
                    seen.add(rec["glosowanie_id"])
                    pt = fetch(rec["glosowanie_url"])
                    counts, votes = parse_print(pt)
                    rec.update(counts)
                    fv.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    for v in votes:
                        v["glosowanie_id"] = rec["glosowanie_id"]
                        fs.write(json.dumps(v, ensure_ascii=False) + "\n")
                    total += 1
                    time.sleep(0.15)
                day += 1
                if day > 12:
                    break
        print(f"check-new: {total} new votings (max_known={args.max_known})")
        fv.close()
        fs.close()
        return

    if args.posiedzenie:
        total = 0
        empty_streak = 0
        for day in range(1, 31):
            try:
                got = scrape_posiedzenie(args.posiedzenie, day, fv, fs, seen)
            except Exception as exc:  # noqa: BLE001
                print(f"day {day}: {exc}")
                break
            if got == 0:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                continue
            empty_streak = 0
            total += got
        fv.close()
        fs.close()
        print(f"posiedzenie {args.posiedzenie}: {total} votings scraped")
        return

    pages = 999 if args.all else args.pages
    pos = list_posiedzenia(pages)
    print(f"posiedzenia: {len(pos)}")
    for pid in sorted(pos, reverse=True):
        total = 0
        empty_streak = 0
        day = 1
        while day <= (args.days or 30):
            try:
                got = scrape_posiedzenie(pid, day, fv, fs, seen)
            except Exception as exc:  # noqa: BLE001
                print(f"posiedzenie {pid} day {day}: {exc}")
                break
            if got == 0:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                empty_streak += 0
                day += 1
                continue
            empty_streak = 0
            total += got
            day += 1
        if total:
            print(f"posiedzenie {pid}: {total} votings")
    fv.close()
    fs.close()
    print("done")


if __name__ == "__main__":
    main()
