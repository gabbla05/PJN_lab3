"""Pomiar czasu zapytan: PostgreSQL (EXPLAIN ANALYZE + klient) i Solr (QTime + klient).

Metodyka: 1 uruchomienie rozgrzewajace (nie liczone), potem RUNS uruchomien -> mediana.
"""
import json
import statistics
import time
import urllib.parse

import requests

from common import SOLR

RUNS = 5
_session = requests.Session()


def _median(xs):
    return round(statistics.median(xs), 2)


def pg_measure(conn, sql, runs=RUNS):
    """Zwraca liczbe wynikow (count(*) lub liczbe wierszy), mediane czasu klienta
    i mediane 'Execution Time' z EXPLAIN (ANALYZE, BUFFERS)."""
    rows = conn.execute(sql).fetchall()          # rozgrzewka
    client, server = [], []
    for _ in range(runs):
        t0 = time.perf_counter()
        rows = conn.execute(sql).fetchall()
        client.append((time.perf_counter() - t0) * 1000)
        plan = conn.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}").fetchone()[0]
        server.append(plan[0]["Execution Time"])
    is_count = sql.lstrip().upper().startswith("SELECT COUNT(*)")
    result = rows[0][0] if is_count else len(rows)
    return {"sql": sql, "result": result, "rows": rows if not is_count else None,
            "server_ms": _median(server), "client_ms": _median(client),
            "server_all_ms": [round(x, 2) for x in server]}


def solr_url(coll, params, handler="select"):
    return f"{SOLR}/{coll}/{handler}?" + urllib.parse.urlencode(params, doseq=True)


def solr_measure(coll, params, runs=RUNS, handler="select"):
    """Zwraca numFound, mediane QTime i czasu klienta oraz ostatnia odpowiedz."""
    url = solr_url(coll, params, handler)
    _session.get(url).raise_for_status()           # rozgrzewka
    qtimes, client = [], []
    js = None
    for _ in range(runs):
        t0 = time.perf_counter()
        r = _session.get(url)
        client.append((time.perf_counter() - t0) * 1000)
        r.raise_for_status()
        js = r.json()
        qtimes.append(js["responseHeader"]["QTime"])
    return {"url": url, "numFound": js.get("response", {}).get("numFound"),
            "qtime_ms": _median(qtimes), "client_ms": _median(client),
            "qtime_all_ms": qtimes, "response": js}


def dump(obj, path):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
