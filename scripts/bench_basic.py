"""Poziom 3.0 + pomiary 4.0 + skalowanie 5.0.

Dla kazdej wielkosci zbioru (10%, 50%, 100%):
  - Q1 przez LIKE (ILIKE, bo LIKE w PostgreSQL rozroznia wielkosc liter),
  - Q1..Q3 przez indeks pelnotekstowy (tsvector + GIN) -> count(*),
  - Q1..Q3 w Solrze (parser lucene, q/fl/sort/rows) -> numFound.
Dla 100% dodatkowo warianty z filtrem i sortowaniem (fq/sort vs WHERE/ORDER BY).

Uzycie: python bench_basic.py [--sizes 10 50 100]
"""
import argparse

import psycopg

from common import PG_DSN, RESULTS
from queries import (QUERIES, pg_count_sql, pg_filtered_count_sql, pg_filtered_sql,
                     pg_like_sql, solr_basic_params, solr_filtered_params)
from timing import dump, pg_measure, solr_measure

TABLE = {10: "arxiv_10", 50: "arxiv_50", 100: "arxiv"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 50, 100])
    a = ap.parse_args()

    out = {}
    with psycopg.connect(PG_DSN, autocommit=True) as conn:
        for size in a.sizes:
            t = TABLE[size]
            n = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            res = {"records": n, "queries": {}}
            print(f"=== {size}% ({t}, {n:,} rekordow)")
            for qid, q in QUERIES.items():
                r = {"label": q["label"]}
                if q["like"]:
                    r["like"] = pg_measure(conn, pg_like_sql(t, qid))
                r["pg_fts"] = pg_measure(conn, pg_count_sql(t, qid))
                s = solr_measure(t, solr_basic_params(qid))
                s.pop("response")
                r["solr"] = s
                # wariant bez queryResultCache (kazde powtorzenie liczone od nowa)
                p = solr_basic_params(qid)
                p["q"] = "{!cache=false}" + p["q"]
                nc = solr_measure(t, p)
                nc.pop("response")
                r["solr_nocache"] = nc
                if size == 100:
                    r["pg_filtered_count"] = pg_measure(conn, pg_filtered_count_sql(t, qid))
                    pf = pg_measure(conn, pg_filtered_sql(t, qid))
                    r["pg_filtered_top10"] = pf
                    sf = solr_measure(t, solr_filtered_params(qid))
                    sf["docs"] = sf.pop("response")["response"]["docs"]
                    r["solr_filtered"] = sf
                res["queries"][qid] = r
                like = r.get("like")
                print(f"  {qid}: " +
                      (f"LIKE {like['result']:>8,} {like['server_ms']:>9.1f}ms | " if like else "") +
                      f"FTS {r['pg_fts']['result']:>8,} {r['pg_fts']['server_ms']:>8.1f}ms | "
                      f"Solr {s['numFound']:>8,} QTime {s['qtime_ms']:>6.1f}ms (klient {s['client_ms']:.1f}ms) "
                      f"| bez cache {nc['qtime_ms']:.1f}ms")
            out[size] = res

    path = RESULTS / ("bench_basic.json" if a.sizes == [10, 50, 100] else
                      f"bench_basic_{'_'.join(map(str, a.sizes))}.json")
    dump(out, path)
    print("zapisano", path)


if __name__ == "__main__":
    main()
