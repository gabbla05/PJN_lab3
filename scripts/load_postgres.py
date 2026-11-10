"""Tworzy schemat, importuje CSV przez COPY, buduje indeksy i podzbiory.
Mierzy czas kazdego kroku i zapisuje do results/load_postgres.json.

Uzycie: python load_postgres.py
"""
import json
import time

import psycopg

from common import PG_DSN, RESULTS, ROOT, sql_statements

STEPS = [
    ("schema", "01_schema.sql"),
    ("copy_load (COPY + wyliczenie tsvector)", "02_load.sql"),
    ("indexes (GIN tsv + btree + trigram) + ANALYZE", "03_indexes.sql"),
    ("subsets 10%/50% (+ GIN)", "04_subsets.sql"),
]


def main():
    timings = {}
    with psycopg.connect(PG_DSN, autocommit=True) as conn:
        for name, fname in STEPS:
            t0 = time.perf_counter()
            for stmt in sql_statements(ROOT / "sql" / fname):
                s0 = time.perf_counter()
                conn.execute(stmt)
                first = " ".join(stmt.split())[:70]
                print(f"   {time.perf_counter() - s0:8.1f}s  {first}")
            timings[name] = round(time.perf_counter() - t0, 1)
            print(f"[{name}] {timings[name]} s")

        stats = {}
        for t in ("arxiv", "arxiv_50", "arxiv_10"):
            cnt = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            size = conn.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{t}'))").fetchone()[0]
            stats[t] = {"rows": cnt, "total_size": size}
        for idx in ("arxiv_tsv_gin", "arxiv_title_trgm"):
            stats[idx] = conn.execute(f"SELECT pg_size_pretty(pg_relation_size('{idx}'))").fetchone()[0]
        stats["table_heap"] = conn.execute("SELECT pg_size_pretty(pg_table_size('arxiv'))").fetchone()[0]

    out = {"timings_s": timings, "stats": stats}
    (RESULTS / "load_postgres.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
