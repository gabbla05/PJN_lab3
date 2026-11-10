"""Definicje 3 zapytan testowych - te same w PostgreSQL i w Solrze.

Q1 - pojedyncze slowo w dowolnej formie: "galaxy" (znajduje galaxy / galaxies)
Q2 - fraza: "dark matter halo" (slowa obok siebie, w tej kolejnosci)
Q3 - logika z negacja: neural AND (image OR speech) AND NOT convolutional

Przeszukiwany jest tytul + abstrakt (w SQL kolumna tsv, w Solrze pole `text` = copyField).
"""

QUERIES = {
    "Q1": {
        "label": "slowo: galaxy",
        "tsquery": "to_tsquery('english', 'galaxy')",
        "like": "(title ILIKE '%galaxy%' OR abstract ILIKE '%galaxy%')",
        "solr_q": "text:galaxy",
        "edismax_q": "galaxy",
        # wariant z filtrem + sortowaniem (fq / sort w Solrze, WHERE / ORDER BY w SQL)
        "pg_filter": "year >= 2015", "solr_fq": "year:[2015 TO *]",
        "pg_order": "year DESC, id", "solr_sort": "year desc,id asc",
    },
    "Q2": {
        "label": "fraza: \"dark matter halo\"",
        "tsquery": "phraseto_tsquery('english', 'dark matter halo')",
        "like": "(title ILIKE '%dark matter halo%' OR abstract ILIKE '%dark matter halo%')",
        "solr_q": 'text:"dark matter halo"',
        "edismax_q": '"dark matter halo"',
        "pg_filter": "archive = 'astro-ph'", "solr_fq": "archive:astro-ph",
        "pg_order": "year DESC, id", "solr_sort": "year desc,id asc",
    },
    "Q3": {
        "label": "neural AND (image OR speech) AND NOT convolutional",
        "tsquery": "to_tsquery('english', 'neural & (image | speech) & !convolutional')",
        "like": None,
        "solr_q": "+text:neural +(text:image text:speech) -text:convolutional",
        "edismax_q": "+neural +(image speech) -convolutional",
        "pg_filter": "archive = 'cs'", "solr_fq": "archive:cs",
        "pg_order": "year DESC, id", "solr_sort": "year desc,id asc",
    },
}

# eDisMax: wagi pol odpowiadajace wagom A (tytul) / B (abstrakt) w tsvector
EDISMAX = {"defType": "edismax", "qf": "title^2.5 abstract", "q.op": "OR"}

# ts_rank_cd: wagi {D,C,B,A} = {0.1,0.2,0.4,1.0} (domyslne), normalizacja 1 = / (1 + log(dlugosc))
PG_RANK = "ts_rank_cd(tsv, q, 1)"


def pg_count_sql(table, qid):
    return f"SELECT count(*) FROM {table} WHERE tsv @@ {QUERIES[qid]['tsquery']}"


def pg_like_sql(table, qid):
    return f"SELECT count(*) FROM {table} WHERE {QUERIES[qid]['like']}"


def pg_top10_sql(table, qid):
    return (f"SELECT id, title, year, archive, {PG_RANK} AS rank "
            f"FROM {table}, {QUERIES[qid]['tsquery']} q "
            f"WHERE tsv @@ q ORDER BY rank DESC, id LIMIT 10")


def solr_basic_params(qid):
    """Zapytanie 'podstawowe' (parser lucene) z q, fq, fl, sort, rows."""
    return {"q": QUERIES[qid]["solr_q"], "fl": "id,title,year,archive,score",
            "sort": "score desc,id asc", "rows": 10}


def pg_filtered_sql(table, qid):
    q = QUERIES[qid]
    return (f"SELECT id, title, year, archive FROM {table} "
            f"WHERE tsv @@ {q['tsquery']} AND {q['pg_filter']} "
            f"ORDER BY {q['pg_order']} LIMIT 10")


def pg_filtered_count_sql(table, qid):
    q = QUERIES[qid]
    return f"SELECT count(*) FROM {table} WHERE tsv @@ {q['tsquery']} AND {q['pg_filter']}"


def solr_filtered_params(qid):
    q = QUERIES[qid]
    return {"q": q["solr_q"], "fq": q["solr_fq"], "fl": "id,title,year,archive",
            "sort": q["solr_sort"], "rows": 10}


def solr_edismax_params(qid):
    return {**EDISMAX, "q": QUERIES[qid]["edismax_q"],
            "fl": "id,title,year,archive,score", "sort": "score desc,id asc", "rows": 10}
