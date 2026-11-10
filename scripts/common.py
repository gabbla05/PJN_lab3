"""Wspolna konfiguracja polaczen."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

PG_DSN = os.environ.get("PG_DSN", "host=localhost port=5433 dbname=lab3 user=lab3 password=lab3")
SOLR = os.environ.get("SOLR_URL", "http://localhost:8983/solr")


def sql_statements(path: Path):
    """Dzieli prosty plik SQL (bez funkcji/blokow $$) na instrukcje."""
    text = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
    return [s.strip() for s in text.split(";") if s.strip()]
