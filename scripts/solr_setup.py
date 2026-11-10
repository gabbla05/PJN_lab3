"""Tworzy kolekcje Solra z wlasnym schematem (Schema API) i wylaczonym schemaless.

Uzycie: python solr_setup.py arxiv [arxiv_50 arxiv_10 ...]
"""
import json
import sys

import requests

from common import ROOT, SOLR

SCHEMA = json.loads((ROOT / "solr" / "schema.json").read_text(encoding="utf-8"))


def check(r: requests.Response):
    if r.status_code >= 400:
        raise SystemExit(f"{r.status_code} {r.url}\n{r.text[:2000]}")
    return r.json()


def setup(coll: str):
    existing = check(requests.get(f"{SOLR}/admin/collections",
                                  params={"action": "LIST", "wt": "json"})).get("collections", [])
    if coll in existing:
        check(requests.get(f"{SOLR}/admin/collections", params={"action": "DELETE", "name": coll}))
        print(f"usunieto istniejaca kolekcje {coll}")
    # osobny configset na kolekcje (kopia _default), zeby zmiany schematu sie nie mieszaly
    conf = f"{coll}_conf"
    configs = check(requests.get(f"{SOLR}/admin/configs", params={"action": "LIST"})).get("configSets", [])
    if conf in configs:
        check(requests.get(f"{SOLR}/admin/configs", params={"action": "DELETE", "name": conf}))
    check(requests.get(f"{SOLR}/admin/configs", params={
        "action": "CREATE", "name": conf, "baseConfigSet": "_default"}))
    check(requests.get(f"{SOLR}/admin/collections", params={
        "action": "CREATE", "name": coll, "numShards": 1, "replicationFactor": 1,
        "collection.configName": conf}))
    print(f"utworzono kolekcje {coll}")

    # wylaczenie trybu schemaless (nie tworzy pol automatycznie)
    check(requests.post(f"{SOLR}/{coll}/config",
                        json={"set-user-property": {"update.autoCreateFields": "false"}}))
    # wlasny schemat
    check(requests.post(f"{SOLR}/{coll}/schema", json=SCHEMA))
    print(f"schemat zastosowany do {coll}")


if __name__ == "__main__":
    for c in sys.argv[1:] or ["arxiv"]:
        setup(c)
