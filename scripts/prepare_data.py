"""Strumieniowa konwersja arxiv-abstracts.jsonl.gz -> data/arxiv.csv.

Zrodlo: https://huggingface.co/datasets/gfissore/arxiv-abstracts-2021 (CC0 1.0),
mirror metadanych arXiv (Cornell University, Kaggle).

Pola wyjsciowe:
  id               - identyfikator arXiv (klucz unikalny)
  title            - tytul (tekst)
  abstract         - abstrakt (tekst, jezyk angielski)
  primary_category - pierwsza kategoria z listy, np. cs.LG, hep-ph   (kategoryczne)
  archive          - archiwum = czesc przed kropka, np. cs, math, hep-ph (kategoryczne)
  categories       - wszystkie kategorie oddzielone spacja (wielowartosciowe)
  year             - rok zgloszenia wyznaczony z identyfikatora (YYMM)  (liczbowe)
  n_versions       - liczba wersji pracy (liczbowe)
  abstract_len     - dlugosc abstraktu w znakach (liczbowe)
  bucket           - crc32(id) % 100, do deterministycznych podzbiorow 10% / 50%

Pole authors/submitter jest celowo pomijane (dane osobowe).
Uzycie: python prepare_data.py <wejscie.jsonl.gz> <wyjscie.csv>
"""
import csv
import gzip
import json
import re
import sys
import zlib
from collections import Counter

WS = re.compile(r"\s+")
NEW_ID = re.compile(r"^(\d{2})(\d{2})\.\d{4,5}$")   # 0704.0001, 2107.05988
OLD_ID = re.compile(r"^[a-z\-]+(?:\.[A-Z]{2})?/(\d{2})(\d{2})\d{3}$")  # math/0601001


def year_from_id(arxiv_id: str):
    m = NEW_ID.match(arxiv_id) or OLD_ID.match(arxiv_id)
    if not m:
        return None
    yy = int(m.group(1))
    return 1900 + yy if yy >= 91 else 2000 + yy


def clean(text) -> str:
    return WS.sub(" ", text or "").strip()


def main(src: str, dst: str) -> None:
    n = skipped = total_len = 0
    archives, years = Counter(), Counter()
    with gzip.open(src, "rt", encoding="utf-8") as fin, \
            open(dst, "w", encoding="utf-8", newline="") as fout:
        w = csv.writer(fout)
        w.writerow(["id", "title", "abstract", "primary_category", "archive",
                    "categories", "year", "n_versions", "abstract_len", "bucket"])
        for line in fin:
            r = json.loads(line)
            aid = r["id"].strip()
            abstract = clean(r.get("abstract"))
            title = clean(r.get("title"))
            raw = r.get("categories") or []
            # w mirrorze HF lista moze miec jeden element "cs.LG stat.ML"
            cats = " ".join(raw if isinstance(raw, list) else [raw]).split()
            year = year_from_id(aid)
            if not abstract or not cats or year is None:
                skipped += 1
                continue
            primary = cats[0]
            archive = primary.split(".")[0]
            versions = r.get("versions") or []
            w.writerow([aid, title, abstract, primary, archive, " ".join(cats),
                        year, len(versions) or 1, len(abstract),
                        zlib.crc32(aid.encode()) % 100])
            n += 1
            total_len += len(abstract)
            archives[archive] += 1
            years[year] += 1
            if n % 250000 == 0:
                print(f"  {n:,} rekordow...", flush=True)

    print(f"Zapisano {n:,} rekordow, pominieto {skipped:,}")
    print(f"Srednia dlugosc abstraktu: {total_len / n:.0f} znakow")
    print(f"Liczba archiwow: {len(archives)}; top-10: {archives.most_common(10)}")
    print(f"Lata: {min(years)}-{max(years)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
