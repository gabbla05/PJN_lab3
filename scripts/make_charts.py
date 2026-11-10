"""Wykresy do sprawozdania na podstawie results/*.json -> results/charts/*.png"""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import RESULTS  # noqa: E402

CH = RESULTS / "charts"
CH.mkdir(exist_ok=True)
C_LIKE, C_PG, C_SOLR = "#c0392b", "#2c7fb8", "#e67e22"


def load(name):
    return json.loads((RESULTS / name).read_text(encoding="utf-8-sig"))


def scaling():
    b = load("bench_basic.json")
    sizes = sorted(b, key=int)
    recs = [b[s]["records"] for s in sizes]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=True)
    for ax, qid in zip(axes, ["Q1", "Q2", "Q3"]):
        q = [b[s]["queries"][qid] for s in sizes]
        if "like" in q[0]:
            ax.plot(recs, [x["like"]["server_ms"] for x in q], "o-", color=C_LIKE, label="LIKE (ILIKE)")
        ax.plot(recs, [x["pg_fts"]["server_ms"] for x in q], "s-", color=C_PG, label="PostgreSQL tsvector+GIN")
        ax.plot(recs, [max(x["solr_nocache"]["qtime_ms"], 0.5) for x in q], "^-", color=C_SOLR,
                label="Solr QTime (bez cache wynikow)")
        ax.plot(recs, [x["solr_nocache"]["client_ms"] for x in q], "^:", color="#f5b041",
                label="Solr czas klienta (HTTP)")
        ax.set_yscale("log")
        ax.set_title(f"{qid}: {q[0]['label']}", fontsize=9)
        ax.set_xlabel("liczba rekordow")
        ax.grid(alpha=.3, which="both")
        ax.ticklabel_format(axis="x", style="plain")
        ax.set_xticks(recs)
        ax.set_xticklabels([f"{r / 1e6:.1f} mln" for r in recs])
    axes[0].set_ylabel("czas [ms] (mediana z 5, skala log)")
    axes[0].legend(fontsize=8)
    fig.suptitle("Skalowanie: 10% / 50% / 100% zbioru")
    fig.tight_layout()
    fig.savefig(CH / "scaling.png", dpi=150)


def query_times():
    b = load("bench_basic.json")["100"]["queries"]
    labels, like, pg, solr = [], [], [], []
    for qid, q in b.items():
        labels.append(qid)
        like.append(q["like"]["server_ms"] if "like" in q else 0)
        pg.append(q["pg_fts"]["server_ms"])
        solr.append(max(q["solr_nocache"]["qtime_ms"], 0.5))
    x = range(len(labels))
    w = .27
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - w for i in x], like, w, color=C_LIKE, label="LIKE")
    ax.bar(x, pg, w, color=C_PG, label="PostgreSQL FTS")
    ax.bar([i + w for i in x], solr, w, color=C_SOLR, label="Solr (QTime bez cache)")
    ax.set_yscale("log")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("czas [ms], skala log")
    ax.set_title("Czasy zapytan, 100% danych (mediana z 5)")
    ax.legend()
    ax.grid(alpha=.3, axis="y", which="both")
    fig.tight_layout()
    fig.savefig(CH / "query_times.png", dpi=150)


def load_times():
    pg = load("load_postgres.json")["timings_s"]
    so = load("load_solr.json")["arxiv"]
    pg_copy = next(v for k, v in pg.items() if k.startswith("copy"))
    pg_idx = next(v for k, v in pg.items() if k.startswith("indexes"))
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.barh(["PostgreSQL"], [pg_copy], color=C_PG, label="PG: COPY (+ tsvector)")
    ax.barh(["PostgreSQL"], [pg_idx], left=[pg_copy], color="#7fb3d5", label="PG: indeksy (GIN, btree, trgm)")
    ax.barh(["Solr"], [so["send_s"]], color=C_SOLR, label="Solr: /update (paczki)")
    ax.barh(["Solr"], [so["commit_s"]], left=[so["send_s"]], color="#f5b041", label="Solr: commit")
    ax.set_xlabel("czas [s]")
    ax.set_title("Ladowanie i indeksowanie 2 mln rekordow")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(CH / "load_times.png", dpi=150)


def paging():
    e = load("extensions.json")["paging"]
    d = [int(k) for k in e["start_rows"]]
    x = [max(k, 100) for k in d]      # glebokosc 0 rysowana jako 100 (skala log)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x, [max(e["start_rows"][str(k)]["qtime_ms"], 0.5) for k in d], "o-", color=C_SOLR, label="Solr start/rows")
    ax.plot(x, [e["cursor"][str(k)]["qtime_ms"] for k in d], "o--", color="#8e44ad", label="Solr cursorMark")
    ax.plot(x, [e["pg_offset"][str(k)]["server_ms"] for k in d], "s-", color=C_PG, label="SQL OFFSET")
    ax.plot(x, [e["pg_keyset"][str(k)]["server_ms"] for k in d], "s--", color="#16a085", label="SQL keyset (id > ...)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(["0", "1k", "10k", "100k", "500k", "1M"])
    ax.set_xlabel("glebokosc (numer pierwszego wyniku)")
    ax.set_ylabel("czas strony [ms]")
    ax.set_title(f"Glebokie stronicowanie (rows={e['rows']})")
    ax.legend()
    ax.grid(alpha=.3, which="both")
    fig.tight_layout()
    fig.savefig(CH / "paging.png", dpi=150)


if __name__ == "__main__":
    for f in (scaling, query_times, load_times, paging):
        try:
            f()
            print("ok", f.__name__)
        except (FileNotFoundError, KeyError) as e:
            print("pominieto", f.__name__, e)
