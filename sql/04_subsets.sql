-- Podzbiory do testu skalowania: 10% i 50% danych (deterministycznie po bucket)
DROP TABLE IF EXISTS arxiv_10, arxiv_50;

CREATE TABLE arxiv_10 (LIKE arxiv INCLUDING GENERATED INCLUDING CONSTRAINTS);
ALTER TABLE arxiv_10 ADD PRIMARY KEY (id);
INSERT INTO arxiv_10 (id, title, abstract, primary_category, archive, categories,
                      year, n_versions, abstract_len, bucket)
SELECT id, title, abstract, primary_category, archive, categories,
       year, n_versions, abstract_len, bucket
FROM arxiv WHERE bucket < 10;
CREATE INDEX arxiv_10_tsv_gin ON arxiv_10 USING gin (tsv);
ANALYZE arxiv_10;

CREATE TABLE arxiv_50 (LIKE arxiv INCLUDING GENERATED INCLUDING CONSTRAINTS);
ALTER TABLE arxiv_50 ADD PRIMARY KEY (id);
INSERT INTO arxiv_50 (id, title, abstract, primary_category, archive, categories,
                      year, n_versions, abstract_len, bucket)
SELECT id, title, abstract, primary_category, archive, categories,
       year, n_versions, abstract_len, bucket
FROM arxiv WHERE bucket < 50;
CREATE INDEX arxiv_50_tsv_gin ON arxiv_50 USING gin (tsv);
ANALYZE arxiv_50;
