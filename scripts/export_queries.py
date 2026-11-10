"""Zapisuje ZAPYTANIA.md: dokladne SQL i pelne URL-e Solra uzyte w pomiarach
(do wklejenia w przegladarke lub Admin UI -> Query)."""
import json

from common import RESULTS, ROOT


def load(n):
    return json.loads((RESULTS / n).read_text(encoding="utf-8"))


def main():
    b = load("bench_basic.json")["100"]["queries"]
    f = load("bench_features.json")
    L = ["# Zapytania uzyte w pomiarach (100% danych)\n",
         "URL-e mozna wkleic do przegladarki (Solr musi dzialac na localhost:8983). "
         "W Admin UI -> kolekcja `arxiv` -> Query wpisujemy te same wartosci parametrow q, fq, fl, sort, rows.\n"]
    for qid, q in b.items():
        L.append(f"## {qid} - {q['label']}\n")
        if "like" in q:
            L.append(f"**LIKE** ({q['like']['result']:,} wynikow):\n```sql\n{q['like']['sql']};\n```")
        L.append(f"**PostgreSQL FTS** ({q['pg_fts']['result']:,} wynikow):\n```sql\n{q['pg_fts']['sql']};\n```")
        L.append(f"**Solr** (numFound {q['solr']['numFound']:,}):\n```\n{q['solr']['url']}\n```")
        L.append(f"**Wariant z filtrem i sortowaniem** - SQL ({q['pg_filtered_count']['result']:,}):\n"
                 f"```sql\n{q['pg_filtered_top10']['sql']};\n```\nSolr (numFound {q['solr_filtered']['numFound']:,}):\n"
                 f"```\n{q['solr_filtered']['url']}\n```")
        r = f["ranking"][qid]
        L.append(f"**Ranking top-10** - SQL `ts_rank_cd`:\n```sql\n{r['pg']['sql']};\n```\n"
                 f"Solr eDisMax:\n```\n{r['solr']['url']}\n```\n")
    fv = f["facets_vs_groupby"]
    L.append("## Facety vs GROUP BY (Q1)\n")
    L.append(f"Solr:\n```\n{fv['solr']['url']}\n```")
    for k, v in fv["pg"].items():
        L.append(f"SQL `{k}`:\n```sql\n{v['sql']};\n```")
    L.append("\n## Podswietlanie\n")
    for qid, h in f["highlighting"].items():
        L.append(f"{qid} Solr:\n```\n{h['solr']['url']}\n```\nSQL:\n```sql\n{h['pg']['sql']};\n```")
    (ROOT / "ZAPYTANIA.md").write_text("\n\n".join(L), encoding="utf-8")
    print("zapisano ZAPYTANIA.md")


if __name__ == "__main__":
    main()
