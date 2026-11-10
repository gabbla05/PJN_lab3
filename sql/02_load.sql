-- Import CSV (plik zamontowany w kontenerze jako /data/arxiv.csv)
COPY arxiv (id, title, abstract, primary_category, archive, categories,
            year, n_versions, abstract_len, bucket)
FROM '/data/arxiv.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
