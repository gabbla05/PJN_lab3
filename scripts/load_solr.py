"""Indeksuje data/arxiv.csv do Solra przez /update: paczki JSON, jeden commit na koncu.

Uzycie: python load_solr.py <kolekcja> [--max-bucket N] [--batch 5000] [--workers 4]
  --max-bucket 10 -> tylko rekordy z bucket < 10 (10% danych)
Wynik (czasy) dopisywany do results/load_solr.json.
"""
import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from common import RESULTS, ROOT, SOLR

csv.field_size_limit(sys.maxsize)


def docs(path, max_bucket):
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            b = int(r["bucket"])
            if b >= max_bucket:
                continue
            yield {
                "id": r["id"],
                "title": r["title"],
                "abstract": r["abstract"],
                "primary_category": r["primary_category"],
                "archive": r["archive"],
                "categories": r["categories"].split(),
                "year": int(r["year"]),
                "n_versions": int(r["n_versions"]),
                "abstract_len": int(r["abstract_len"]),
                "bucket": b,
            }


def batches(it, size):
    buf = []
    for d in it:
        buf.append(d)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("collection")
    ap.add_argument("--max-bucket", type=int, default=100)
    ap.add_argument("--batch", type=int, default=5000)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    session = requests.Session()
    url = f"{SOLR}/{a.collection}/update"

    def send(batch):
        r = session.post(url, data=json.dumps(batch), headers={"Content-Type": "application/json"})
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code}: {r.text[:500]}")
        return len(batch)

    t0 = time.perf_counter()
    n = 0
    with ThreadPoolExecutor(a.workers) as ex:
        pending = []
        for b in batches(docs(ROOT / "data" / "arxiv.csv", a.max_bucket), a.batch):
            pending.append(ex.submit(send, b))
            if len(pending) >= a.workers * 2:          # ograniczenie pamieci
                n += pending.pop(0).result()
                if n % 100000 < a.batch:
                    print(f"  {n:,} dok. {time.perf_counter() - t0:.0f}s", flush=True)
        for p in pending:
            n += p.result()
    t_send = time.perf_counter() - t0

    t1 = time.perf_counter()
    r = session.get(url, params={"commit": "true", "openSearcher": "true"})
    r.raise_for_status()
    t_commit = time.perf_counter() - t1

    num = session.get(f"{SOLR}/{a.collection}/select", params={"q": "*:*", "rows": 0}).json()["response"]["numFound"]
    core = session.get(f"{SOLR}/admin/cores", params={"action": "STATUS"}).json()["status"]
    size = next((c["index"]["size"] for k, c in core.items() if k.startswith(a.collection + "_shard")), "?")

    res = {"collection": a.collection, "docs_sent": n, "numFound": num,
           "send_s": round(t_send, 1), "commit_s": round(t_commit, 1),
           "total_s": round(t_send + t_commit, 1), "index_size": size,
           "batch": a.batch, "workers": a.workers}
    print(json.dumps(res, indent=2))
    out = RESULTS / "load_solr.json"
    allres = json.loads(out.read_text()) if out.exists() else {}
    allres[a.collection] = res
    out.write_text(json.dumps(allres, indent=2))


if __name__ == "__main__":
    main()
