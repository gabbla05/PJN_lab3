-- Lab3: schemat tabeli z artykulami arXiv (PostgreSQL 17)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DROP TABLE IF EXISTS arxiv_10, arxiv_50, arxiv CASCADE;

CREATE TABLE arxiv (
    id               varchar(32)  PRIMARY KEY,
    title            text         NOT NULL,
    abstract         text         NOT NULL,
    primary_category varchar(32)  NOT NULL,   -- kategoryczne, ~150 wartosci
    archive          varchar(32)  NOT NULL,   -- kategoryczne, 38 wartosci
    categories       text         NOT NULL,   -- lista kategorii oddzielona spacjami
    year             smallint     NOT NULL,   -- liczbowe: 1991-2021
    n_versions       smallint     NOT NULL,
    abstract_len     integer      NOT NULL,
    bucket           smallint     NOT NULL,   -- crc32(id) % 100 -> podzbiory 10%/50%
    -- dokument pelnotekstowy: tytul (waga A) + abstrakt (waga B), konfiguracja english
    -- (stemmer Snowball + stoplista angielska)
    tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', title), 'A') ||
        setweight(to_tsvector('english', abstract), 'B')
    ) STORED
);
