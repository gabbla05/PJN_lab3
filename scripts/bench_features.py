"""Poziom 4.0/5.0: ranking top-10, GROUP BY, facety, facet zakresowy, podswietlanie.

Uzycie: python bench_features.py
"""
import psycopg

from common import PG_DSN, RESULTS
from queries import QUERIES, pg_top10_sql, solr_edismax_params
from timing import dump, pg_measure, solr_measure

T = "arxiv"
FACET_Q = "Q1"           # zapytanie, dla ktorego liczymy facety / GROUP BY
YEAR_START, YEAR_END, YEAR_GAP = 1991, 2026, 5


def ranking(conn):
    out = {}
    for qid in QUERIES:
        pg = pg_measure(conn, pg_top10_sql(T, qid))
        pg_docs = [{"id": r[0], "title": r[1], "year": r[2], "archive": r[3],
                    "rank": round(float(r[4]), 4)} for r in pg.pop("rows")]
        s = solr_measure(T, solr_edismax_params(qid))
        js = s.pop("response")
        solr_docs = js["response"]["docs"]
        pg_ids = [d["id"] for d in pg_docs]
        solr_ids = [d["id"] for d in solr_docs]
        common = [i for i in pg_ids if i in solr_ids]
        out[qid] = {"label": QUERIES[qid]["label"], "pg": pg, "pg_docs": pg_docs,
                    "solr": s, "solr_docs": solr_docs,
                    "overlap": len(common), "common_ids": common}
        print(f"{qid}: top-10 wspolnych: {len(common)}/10 | PG {pg['server_ms']}ms, "
              f"Solr eDisMax QTime {s['qtime_ms']}ms numFound {s['numFound']:,}")
    return out


def facets_vs_groupby(conn):
    tsq = QUERIES[FACET_Q]["tsquery"]
    yb = f"({YEAR_START} + ((year - {YEAR_START}) / {YEAR_GAP}) * {YEAR_GAP})"
    sql = {
        "group_archive": f"SELECT archive, count(*) c FROM {T} WHERE tsv @@ {tsq} "
                         f"GROUP BY archive ORDER BY c DESC, archive LIMIT 10",
        "group_primary_category": f"SELECT primary_category, count(*) c FROM {T} WHERE tsv @@ {tsq} "
                                  f"GROUP BY primary_category ORDER BY c DESC, primary_category LIMIT 10",
        "group_year_range": f"SELECT {yb} AS y, count(*) c FROM {T} WHERE tsv @@ {tsq} "
                            f"GROUP BY y ORDER BY y",
        # wszystkie trzy agregacje w jednym zapytaniu (jedno przejscie po wynikach)
        "grouping_sets": f"SELECT archive, primary_category, {yb} AS y, count(*) c "
                         f"FROM {T} WHERE tsv @@ {tsq} "
                         f"GROUP BY GROUPING SETS ((archive), (primary_category), ({yb}))",
    }
    pg = {k: pg_measure(conn, v) for k, v in sql.items()}
    for k in pg:
        pg[k]["rows"] = [list(r) for r in pg[k]["rows"]]
    pg_sum = round(sum(pg[k]["server_ms"] for k in
                       ("group_archive", "group_primary_category", "group_year_range")), 2)

    params = {"q": QUERIES[FACET_Q]["solr_q"], "rows": 0, "facet": "true",
              "facet.field": ["archive", "primary_category"], "facet.limit": 10,
              "facet.mincount": 1,
              "facet.range": "year", "facet.range.start": YEAR_START,
              "facet.range.end": YEAR_END, "facet.range.gap": YEAR_GAP}
    s = solr_measure(T, params)
    js = s.pop("response")
    fc = js["facet_counts"]
    s["facet_fields"] = {k: list(zip(v[::2], v[1::2])) for k, v in fc["facet_fields"].items()}
    s["facet_ranges"] = {k: list(zip(v["counts"][::2], v["counts"][1::2]))
                         for k, v in fc["facet_ranges"].items()}
    print(f"facety Solr: QTime {s['qtime_ms']}ms | SQL 3x GROUP BY: {pg_sum}ms | "
          f"GROUPING SETS: {pg['grouping_sets']['server_ms']}ms")
    return {"query": FACET_Q, "pg": pg, "pg_3_queries_sum_ms": pg_sum, "solr": s}


def groupby_4(conn):
    """4.0: jedna agregacja GROUP BY dla wynikow zapytania pelnotekstowego (Q3)."""
    sql = (f"SELECT archive, count(*) c FROM {T} WHERE tsv @@ {QUERIES['Q3']['tsquery']} "
           f"GROUP BY archive ORDER BY c DESC")
    r = pg_measure(conn, sql)
    r["rows"] = [list(x) for x in r["rows"]]
    params = {"q": QUERIES["Q3"]["solr_q"], "rows": 0, "facet": "true",
              "facet.field": "archive", "facet.mincount": 1}
    s = solr_measure(T, params)
    v = s.pop("response")["facet_counts"]["facet_fields"]["archive"]
    s["facet"] = list(zip(v[::2], v[1::2]))
    return {"pg": r, "solr": s}


def highlighting(conn):
    out = {}
    for qid in ("Q1", "Q2"):
        p = {**solr_edismax_params(qid), "rows": 3, "fl": "id,title",
             "hl": "true", "hl.fl": "title,abstract", "hl.snippets": 1, "hl.fragsize": 160,
             "hl.method": "unified", "hl.tag.pre": "<b>", "hl.tag.post": "</b>"}
        s = solr_measure(T, p)
        js = s.pop("response")
        s["snippets"] = {d["id"]: {f: (js["highlighting"].get(d["id"], {}).get(f) or [""])[0]
                                   for f in ("title", "abstract")}
                         for d in js["response"]["docs"]}
        tsq = QUERIES[qid]["tsquery"]
        sql = (f"SELECT id, ts_headline('english', abstract, q, "
               f"'StartSel=<b>, StopSel=</b>, MaxWords=25, MinWords=10, MaxFragments=1') "
               f"FROM (SELECT id, abstract, q FROM {T}, {tsq} q WHERE tsv @@ q "
               f"ORDER BY ts_rank_cd(tsv, q, 1) DESC, id LIMIT 3) t")
        pg = pg_measure(conn, sql)
        pg["snippets"] = {r[0]: r[1] for r in pg.pop("rows")}
        out[qid] = {"solr": s, "pg": pg}
        print(f"hl {qid}: Solr QTime {s['qtime_ms']}ms | PG ts_headline {pg['server_ms']}ms")
    return out


def main():
    with psycopg.connect(PG_DSN, autocommit=True) as conn:
        res = {"ranking": ranking(conn), "groupby_4": groupby_4(conn),
               "facets_vs_groupby": facets_vs_groupby(conn),
               "highlighting": highlighting(conn)}
    dump(res, RESULTS / "bench_features.json")
    print("zapisano results/bench_features.json")


if __name__ == "__main__":
    main()
