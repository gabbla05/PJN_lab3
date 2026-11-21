"""Rozszerzenia (4.0: >=1, 5.0: >=2 kolejne):

  E1 (4.0) synonimy zarzadzane przez REST w Solrze (ManagedSynonymGraphFilter)
  E2 (5.0) odpornosc na literowki: fuzzy (~) w Solrze vs LIKE / pg_trgm
  E3 (5.0) glebokie stronicowanie: start/rows vs cursorMark (+ OFFSET vs keyset w SQL)
  E4 (5.0) wlasny typ pola z jawnym lancuchem analizy: Analysis API vs to_tsvector

Uzycie: python extensions.py [synonyms fuzzy paging analysis]
"""
import statistics
import sys
import time

import psycopg
import requests

from common import PG_DSN, RESULTS, SOLR
from timing import dump, pg_measure, solr_measure, solr_url

T = "arxiv"
S = requests.Session()

# ---------------------------------------------------------------- E1 synonimy
SYN_GROUPS = {
    "cnn": ["cnn", "convolutional neural network"],
    "gw": ["gw", "gravitational wave"],
    "qcd": ["qcd", "quantum chromodynamics"],
    "bec": ["bec", "bose einstein condensate"],
}
SYN_URL = f"{SOLR}/{T}/schema/analysis/synonyms/english"


def count(q, field="text"):
    # wielowyrazowe terminy jako fraza (jak <-> w SQL); q.op=AND
    if " " in q:
        q = f'"{q}"'
    p = {"defType": "edismax", "qf": field, "q": q, "q.op": "AND", "rows": 0}
    js = S.get(f"{SOLR}/{T}/select", params=p).json()
    return js["response"]["numFound"]


def reload_collection():
    S.get(f"{SOLR}/admin/collections", params={"action": "RELOAD", "name": T}).raise_for_status()


def synonyms(conn):
    # stan poczatkowy: usun ewentualne wpisy z poprzedniego uruchomienia
    for k in S.get(SYN_URL).json()["synonymMappings"]["managedMap"]:
        S.delete(f"{SYN_URL}/{requests.utils.quote(k)}")
    reload_collection()

    before = {}
    for key, terms in SYN_GROUPS.items():
        before[key] = {t: count(t) for t in terms}

    # PUT kazdej grupy synonimow (plaska lista = synonimy rownowazne w obie strony)
    for terms in SYN_GROUPS.values():
        S.put(SYN_URL, json=terms).raise_for_status()
    reload_collection()
    managed = S.get(SYN_URL).json()["synonymMappings"]["managedMap"]

    after = {}
    for key, terms in SYN_GROUPS.items():
        after[key] = {t: count(t) for t in terms}

    # odpowiednik w SQL: recznie rozpisany OR w tsquery
    pg = {}
    for key, terms in SYN_GROUPS.items():
        parts = [" <-> ".join(t.split()) for t in terms]
        tsq = " | ".join(f"({p})" for p in parts)
        sql = f"SELECT count(*) FROM {T} WHERE tsv @@ to_tsquery('english', '{tsq}')"
        pg[key] = {"sql": sql, "count": conn.execute(sql).fetchone()[0]}

    for key in SYN_GROUPS:
        print(f"syn {key}: przed {before[key]} -> po {after[key]} | SQL (OR) {pg[key]['count']}")
    return {"groups": SYN_GROUPS, "managed_map": managed, "before": before,
            "after": after, "pg_or_equivalent": pg,
            "rest_calls": [f'PUT {SYN_URL}  body: ["cnn", "convolutional neural network"]  (x4 grupy)',
                           f"GET {SOLR}/admin/collections?action=RELOAD&name={T}"]}


# ---------------------------------------------------------------- E2 literowki
TYPOS = [("galxy", "galaxy"), ("quantim", "quantum"), ("superconductvity", "superconductivity")]


def fuzzy(conn):
    conn.execute("SET pg_trgm.word_similarity_threshold = 0.6")
    out = {}
    for typo, correct in TYPOS:
        # Solr: zapytanie rozmyte (odleglosc edycyjna Damerau-Levenshteina <= 2) w tytule
        s = solr_measure(T, {"q": f"title:{typo}~2", "fl": "id,title", "rows": 3})
        s_docs = s.pop("response")["response"]["docs"]
        s_exact = solr_measure(T, {"q": f"title:{correct}", "rows": 0})
        s_exact.pop("response")
        like = pg_measure(conn, f"SELECT count(*) FROM {T} WHERE title ILIKE '%{typo}%'")
        trgm = pg_measure(conn, f"SELECT count(*) FROM {T} WHERE '{typo}' <% title")
        trgm_top = conn.execute(
            f"SELECT id, title, word_similarity('{typo}', title) ws FROM {T} "
            f"WHERE '{typo}' <% title ORDER BY ws DESC, id LIMIT 3").fetchall()
        out[typo] = {"correct": correct, "solr_fuzzy": s, "solr_fuzzy_top": s_docs,
                     "solr_exact_correct": s_exact, "like": like, "pg_trgm": trgm,
                     "pg_trgm_top": [list(r) for r in trgm_top]}
        print(f"typo {typo}: Solr~2 {s['numFound']:,} ({s['qtime_ms']}ms) | "
              f"Solr '{correct}' {s_exact['numFound']:,} | LIKE {like['result']} ({like['server_ms']}ms) | "
              f"pg_trgm {trgm['result']:,} ({trgm['server_ms']}ms)")
    return out


# ---------------------------------------------------------------- E3 stronicowanie
DEPTHS = [0, 1000, 10000, 100000, 500000, 1000000]
ROWS = 20


def paging(conn):
    # wyniki pomiarów dla różnych metod stronicowania
    out = {"rows": ROWS, "start_rows": {}, "cursor": {}, "pg_offset": {}, "pg_keyset": {}}

    # wspólne parametry wszystkich zapytań Solr
    base = {"q": "*:*", "sort": "id asc", "fl": "id", "rows": ROWS}

    # klasyczne stronicowanie Solra (start + rows)
    # mierzymy czas pobrania strony znajdującej się na różnych głębokościach
    for d in DEPTHS:
        s = solr_measure(T, {**base, "start": d})
        s.pop("response")
        out["start_rows"][d] = s

    # cursorMark:
    # przechodzimy do kolejnych głębokich pozycji i zapamiętujemy
    # kursor odpowiadający danej głębokości
    t0 = time.perf_counter()
    cursor, pos, step = "*", 0, 10000

    # dla każdej głębokości będziemy pamiętać odpowiadający jej cursorMark
    marks = {0: "*"}

    for d in sorted(DEPTHS[1:]):
        while pos < d:
            # przesuwaj się po wynikach dużymi krokami
            n = min(step, d - pos)

            js = S.get(
                f"{SOLR}/{T}/select",
                params={**base, "rows": n, "cursorMark": cursor}
            ).json()

            cursor, pos = js["nextCursorMark"], pos + n

        marks[d] = cursor

    walk_s = time.perf_counter() - t0

    # zmierz czas pobrania strony przy użyciu cursorMark
    for d, m in marks.items():
        s = solr_measure(T, {**base, "cursorMark": m})
        s.pop("response")
        out["cursor"][d] = s

    # koszt "dojścia" kursorem do największej głębokości
    out["cursor_walk_to_1M_s"] = round(walk_s, 1)

    # SQL: klasyczne stronicowanie OFFSET
    ids = {}

    for d in DEPTHS:
        out["pg_offset"][d] = pg_measure(
            conn,
            f"SELECT id FROM {T} ORDER BY id OFFSET {d} LIMIT {ROWS}"
        )

        out["pg_offset"][d].pop("rows")

        # zapamiętaj ostatni identyfikator przed daną stroną,
        # będzie potrzebny do keyset pagination
        if d:
            ids[d] = conn.execute(
                f"SELECT id FROM {T} ORDER BY id OFFSET {d - 1} LIMIT 1"
            ).fetchone()[0]

    # SQL keyset pagination (WHERE id > ostatni_id)
    for d in DEPTHS:
        cond = f"WHERE id > '{ids[d]}' " if d else ""

        out["pg_keyset"][d] = pg_measure(
            conn,
            f"SELECT id FROM {T} {cond}ORDER BY id LIMIT {ROWS}"
        )

        out["pg_keyset"][d].pop("rows")

    # zestawienie wszystkich metod dla tej samej głębokości
    for d in DEPTHS:
        print(
            f"depth {d:>8}: "
            f"start/rows {out['start_rows'][d]['qtime_ms']:>7}ms | "
            f"cursorMark {out['cursor'][d]['qtime_ms']:>5}ms | "
            f"OFFSET {out['pg_offset'][d]['server_ms']:>8}ms | "
            f"keyset {out['pg_keyset'][d]['server_ms']}ms"
        )

    return out


# ---------------------------------------------------------------- E4 analiza

# Zdania testowe używane do porównania analizy tekstu
# w Solr (text_en_lab) oraz PostgreSQL (to_tsvector).
SENTENCES = [
    "The galaxies' rotation curves were measured using running averages.",
    "We studied Bose-Einstein condensates of ultracold atoms in optical lattices.",
    "Convolutional neural networks are not the only models for image classification.",
]


def analysis(conn):
    # wyniki analizy każdego zdania
    out = []

    for sent in SENTENCES:

        # pobierz z Solra kolejne etapy łańcucha analizy
        # zdefiniowanego dla typu text_en_lab
        js = S.get(
            f"{SOLR}/{T}/analysis/field",
            params={
                "analysis.fieldtype": "text_en_lab",
                "analysis.fieldvalue": sent,
                "wt": "json"
            }
        ).json()

        idx = js["analysis"]["field_types"]["text_en_lab"]["index"]

        stages = []

        # odczytaj tokeny po każdym filtrze
        # (tokenizer, lowercase, stopwords, stemming itd.)
        for i in range(0, len(idx), 2):
            name = idx[i].split(".")[-1]
            toks = [t["text"] for t in idx[i + 1]]

            stages.append({
                "stage": name,
                "tokens": toks
            })

        # analiza PostgreSQL z konfiguracją angielską
        # (stop words + stemming)
        pg_vec = conn.execute(
            "SELECT to_tsvector('english', %s)::text",
            (sent,)
        ).fetchone()[0]

        # analiza PostgreSQL bez stemmera i stoplisty
        # wykorzystywana do porównania ("simple")
        pg_simple = conn.execute(
            "SELECT to_tsvector('simple', %s)::text",
            (sent,)
        ).fetchone()[0]

        out.append({
            "sentence": sent,
            "solr_stages": stages,
            "pg_english": pg_vec,
            "pg_simple": pg_simple
        })

        # wypisz końcowy wynik Solra i PostgreSQL
        print(sent)
        print("   Solr:", stages[-1]["tokens"])
        print("   PG  :", pg_vec)

    return out


def main():
    which = sys.argv[1:] or ["synonyms", "fuzzy", "paging", "analysis"]
    path = RESULTS / "extensions.json"
    import json
    res = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    with psycopg.connect(PG_DSN, autocommit=True) as conn:
        for w in which:
            print(f"===== {w}")
            res[w] = globals()[w](conn)
    dump(res, path)
    print("zapisano", path)


if __name__ == "__main__":
    main()
