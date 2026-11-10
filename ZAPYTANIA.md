# Zapytania uzyte w pomiarach (100% danych)


URL-e mozna wkleic do przegladarki (Solr musi dzialac na localhost:8983). W Admin UI -> kolekcja `arxiv` -> Query wpisujemy te same wartosci parametrow q, fq, fl, sort, rows.


## Q1 - slowo: galaxy


**LIKE** (60,580 wynikow):
```sql
SELECT count(*) FROM arxiv WHERE (title ILIKE '%galaxy%' OR abstract ILIKE '%galaxy%');
```

**PostgreSQL FTS** (84,073 wynikow):
```sql
SELECT count(*) FROM arxiv WHERE tsv @@ to_tsquery('english', 'galaxy');
```

**Solr** (numFound 84,129):
```
http://localhost:8983/solr/arxiv/select?q=text%3Agalaxy&fl=id%2Ctitle%2Cyear%2Carchive%2Cscore&sort=score+desc%2Cid+asc&rows=10
```

**Wariant z filtrem i sortowaniem** - SQL (29,022):
```sql
SELECT id, title, year, archive FROM arxiv WHERE tsv @@ to_tsquery('english', 'galaxy') AND year >= 2015 ORDER BY year DESC, id LIMIT 10;
```
Solr (numFound 29,048):
```
http://localhost:8983/solr/arxiv/select?q=text%3Agalaxy&fq=year%3A%5B2015+TO+%2A%5D&fl=id%2Ctitle%2Cyear%2Carchive&sort=year+desc%2Cid+asc&rows=10
```

**Ranking top-10** - SQL `ts_rank_cd`:
```sql
SELECT id, title, year, archive, ts_rank_cd(tsv, q, 1) AS rank FROM arxiv, to_tsquery('english', 'galaxy') q WHERE tsv @@ q ORDER BY rank DESC, id LIMIT 10;
```
Solr eDisMax:
```
http://localhost:8983/solr/arxiv/select?defType=edismax&qf=title%5E2.5+abstract&q.op=OR&q=galaxy&fl=id%2Ctitle%2Cyear%2Carchive%2Cscore&sort=score+desc%2Cid+asc&rows=10
```


## Q2 - fraza: "dark matter halo"


**LIKE** (5,105 wynikow):
```sql
SELECT count(*) FROM arxiv WHERE (title ILIKE '%dark matter halo%' OR abstract ILIKE '%dark matter halo%');
```

**PostgreSQL FTS** (5,413 wynikow):
```sql
SELECT count(*) FROM arxiv WHERE tsv @@ phraseto_tsquery('english', 'dark matter halo');
```

**Solr** (numFound 5,423):
```
http://localhost:8983/solr/arxiv/select?q=text%3A%22dark+matter+halo%22&fl=id%2Ctitle%2Cyear%2Carchive%2Cscore&sort=score+desc%2Cid+asc&rows=10
```

**Wariant z filtrem i sortowaniem** - SQL (5,156):
```sql
SELECT id, title, year, archive FROM arxiv WHERE tsv @@ phraseto_tsquery('english', 'dark matter halo') AND archive = 'astro-ph' ORDER BY year DESC, id LIMIT 10;
```
Solr (numFound 5,166):
```
http://localhost:8983/solr/arxiv/select?q=text%3A%22dark+matter+halo%22&fq=archive%3Aastro-ph&fl=id%2Ctitle%2Cyear%2Carchive&sort=year+desc%2Cid+asc&rows=10
```

**Ranking top-10** - SQL `ts_rank_cd`:
```sql
SELECT id, title, year, archive, ts_rank_cd(tsv, q, 1) AS rank FROM arxiv, phraseto_tsquery('english', 'dark matter halo') q WHERE tsv @@ q ORDER BY rank DESC, id LIMIT 10;
```
Solr eDisMax:
```
http://localhost:8983/solr/arxiv/select?defType=edismax&qf=title%5E2.5+abstract&q.op=OR&q=%22dark+matter+halo%22&fl=id%2Ctitle%2Cyear%2Carchive%2Cscore&sort=score+desc%2Cid+asc&rows=10
```


## Q3 - neural AND (image OR speech) AND NOT convolutional


**PostgreSQL FTS** (10,692 wynikow):
```sql
SELECT count(*) FROM arxiv WHERE tsv @@ to_tsquery('english', 'neural & (image | speech) & !convolutional');
```

**Solr** (numFound 10,713):
```
http://localhost:8983/solr/arxiv/select?q=%2Btext%3Aneural+%2B%28text%3Aimage+text%3Aspeech%29+-text%3Aconvolutional&fl=id%2Ctitle%2Cyear%2Carchive%2Cscore&sort=score+desc%2Cid+asc&rows=10
```

**Wariant z filtrem i sortowaniem** - SQL (7,999):
```sql
SELECT id, title, year, archive FROM arxiv WHERE tsv @@ to_tsquery('english', 'neural & (image | speech) & !convolutional') AND archive = 'cs' ORDER BY year DESC, id LIMIT 10;
```
Solr (numFound 8,018):
```
http://localhost:8983/solr/arxiv/select?q=%2Btext%3Aneural+%2B%28text%3Aimage+text%3Aspeech%29+-text%3Aconvolutional&fq=archive%3Acs&fl=id%2Ctitle%2Cyear%2Carchive&sort=year+desc%2Cid+asc&rows=10
```

**Ranking top-10** - SQL `ts_rank_cd`:
```sql
SELECT id, title, year, archive, ts_rank_cd(tsv, q, 1) AS rank FROM arxiv, to_tsquery('english', 'neural & (image | speech) & !convolutional') q WHERE tsv @@ q ORDER BY rank DESC, id LIMIT 10;
```
Solr eDisMax:
```
http://localhost:8983/solr/arxiv/select?defType=edismax&qf=title%5E2.5+abstract&q.op=OR&q=%2Bneural+%2B%28image+speech%29+-convolutional&fl=id%2Ctitle%2Cyear%2Carchive%2Cscore&sort=score+desc%2Cid+asc&rows=10
```


## Facety vs GROUP BY (Q1)


Solr:
```
http://localhost:8983/solr/arxiv/select?q=text%3Agalaxy&rows=0&facet=true&facet.field=archive&facet.field=primary_category&facet.limit=10&facet.mincount=1&facet.range=year&facet.range.start=1991&facet.range.end=2026&facet.range.gap=5
```

SQL `group_archive`:
```sql
SELECT archive, count(*) c FROM arxiv WHERE tsv @@ to_tsquery('english', 'galaxy') GROUP BY archive ORDER BY c DESC, archive LIMIT 10;
```

SQL `group_primary_category`:
```sql
SELECT primary_category, count(*) c FROM arxiv WHERE tsv @@ to_tsquery('english', 'galaxy') GROUP BY primary_category ORDER BY c DESC, primary_category LIMIT 10;
```

SQL `group_year_range`:
```sql
SELECT (1991 + ((year - 1991) / 5) * 5) AS y, count(*) c FROM arxiv WHERE tsv @@ to_tsquery('english', 'galaxy') GROUP BY y ORDER BY y;
```

SQL `grouping_sets`:
```sql
SELECT archive, primary_category, (1991 + ((year - 1991) / 5) * 5) AS y, count(*) c FROM arxiv WHERE tsv @@ to_tsquery('english', 'galaxy') GROUP BY GROUPING SETS ((archive), (primary_category), ((1991 + ((year - 1991) / 5) * 5)));
```


## Podswietlanie


Q1 Solr:
```
http://localhost:8983/solr/arxiv/select?defType=edismax&qf=title%5E2.5+abstract&q.op=OR&q=galaxy&fl=id%2Ctitle&sort=score+desc%2Cid+asc&rows=3&hl=true&hl.fl=title%2Cabstract&hl.snippets=1&hl.fragsize=160&hl.method=unified&hl.tag.pre=%3Cb%3E&hl.tag.post=%3C%2Fb%3E
```
SQL:
```sql
SELECT id, ts_headline('english', abstract, q, 'StartSel=<b>, StopSel=</b>, MaxWords=25, MinWords=10, MaxFragments=1') FROM (SELECT id, abstract, q FROM arxiv, to_tsquery('english', 'galaxy') q WHERE tsv @@ q ORDER BY ts_rank_cd(tsv, q, 1) DESC, id LIMIT 3) t;
```

Q2 Solr:
```
http://localhost:8983/solr/arxiv/select?defType=edismax&qf=title%5E2.5+abstract&q.op=OR&q=%22dark+matter+halo%22&fl=id%2Ctitle&sort=score+desc%2Cid+asc&rows=3&hl=true&hl.fl=title%2Cabstract&hl.snippets=1&hl.fragsize=160&hl.method=unified&hl.tag.pre=%3Cb%3E&hl.tag.post=%3C%2Fb%3E
```
SQL:
```sql
SELECT id, ts_headline('english', abstract, q, 'StartSel=<b>, StopSel=</b>, MaxWords=25, MinWords=10, MaxFragments=1') FROM (SELECT id, abstract, q FROM arxiv, phraseto_tsquery('english', 'dark matter halo') q WHERE tsv @@ q ORDER BY ts_rank_cd(tsv, q, 1) DESC, id LIMIT 3) t;
```