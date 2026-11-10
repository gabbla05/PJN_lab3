-- Indeks pelnotekstowy: GIN na kolumnie tsvector
CREATE INDEX arxiv_tsv_gin ON arxiv USING gin (tsv);

-- Indeksy B-tree pod filtry / GROUP BY
CREATE INDEX arxiv_archive_idx ON arxiv (archive);
CREATE INDEX arxiv_year_idx ON arxiv (year);

-- Rozszerzenie (odpornosc na literowki): indeks trigramowy na tytule
CREATE INDEX arxiv_title_trgm ON arxiv USING gin (title gin_trgm_ops);

ANALYZE arxiv;
