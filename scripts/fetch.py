#!/usr/bin/env python3
"""Build the catalogue of in-force SR texts from the Fedlex SPARQL endpoint and download
the latest consolidated version (Akoma Ntoso XML, else HTML) per language.

Usage: fetch.py [RAW_DIR] [--date YYYY-MM-DD] [--langs de,fr,it,rm] [--refresh]
       (RAW_DIR defaults to ../../_raw/ch relative to this script)

Output: RAW_DIR/catalog.json and RAW_DIR/files/<lang>/<eli-path>.<xml|html>
Downloads are cached: existing files are not fetched again.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import sys
import time
from pathlib import Path

import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
SPARQL = "https://fedlex.data.admin.ch/sparqlendpoint"
WORKERS = 4
PREFIX = """PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
IN_FORCE = "<https://fedlex.data.admin.ch/vocabulary/enforcement-status/0>"
LANGS = {"DEU": "de", "FRA": "fr", "ITA": "it", "ROH": "rm", "ENG": "en"}


def session():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def sparql(s, query, page=10000):
    """Run a SELECT query with LIMIT/OFFSET paging (unsorted results must stay well below
    Virtuoso's 10,000-row sort window; use batched VALUES for bigger sets)."""
    out = []
    off = 0
    while True:
        q = PREFIX + query + f"\nLIMIT {page} OFFSET {off}"
        for attempt in range(6):
            try:
                r = s.post(SPARQL, data={"query": q},
                           headers={"Accept": "application/sparql-results+json"}, timeout=300)
                if r.status_code == 200:
                    break
                print(f"  SPARQL HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            except requests.RequestException as e:
                print(f"  SPARQL error {e}", file=sys.stderr)
            time.sleep(2 ** attempt * 2)
        else:
            sys.exit("SPARQL failed")
        rows = [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]
        out.extend(rows)
        if len(rows) < page:
            return out
        off += page


def build_catalog(s, today):
    print("query: abstracts", file=sys.stderr)
    abstracts = {}
    for r in sparql(s, f"""SELECT DISTINCT ?abs ?sr ?td ?dd ?eif ?nlif WHERE {{
  ?abs a jolux:ConsolidationAbstract ; jolux:inForceStatus {IN_FORCE} .
  OPTIONAL {{ ?abs jolux:classifiedByTaxonomyEntry/skos:notation ?sr }}
  OPTIONAL {{ ?abs jolux:typeDocument ?td }}
  OPTIONAL {{ ?abs jolux:dateDocument ?dd }}
  OPTIONAL {{ ?abs jolux:dateEntryInForce ?eif }}
  OPTIONAL {{ ?abs jolux:dateNoLongerInForce ?nlif }}
}}"""):
        a = abstracts.setdefault(r["abs"], {"eli": r["abs"], "titles": {}, "short": {},
                                            "versions": {}})
        for k in ("sr", "td", "dd", "eif", "nlif"):
            if k in r:
                a[k] = r[k]
    print(f"  {len(abstracts)} abstracts", file=sys.stderr)

    def batched(query_tpl, n=150):
        keys = sorted(abstracts)
        for i in range(0, len(keys), n):
            vals = " ".join(f"<{k}>" for k in keys[i:i + n])
            yield from sparql(s, query_tpl.replace("%VALUES%", f"VALUES ?abs {{ {vals} }}"))

    print("query: titles", file=sys.stderr)
    for r in batched(f"""SELECT DISTINCT ?abs ?lang ?t ?ts WHERE {{
  %VALUES%
  ?abs jolux:isRealizedBy ?e .
  ?e jolux:language ?lang .
  OPTIONAL {{ ?e jolux:title ?t }}
  OPTIONAL {{ ?e jolux:titleShort ?ts }}
}}"""):
        lang = LANGS.get(r["lang"].rsplit("/", 1)[-1])
        a = abstracts.get(r["abs"])
        if not a or not lang:
            continue
        if "t" in r:
            a["titles"][lang] = r["t"].strip()
        if "ts" in r:
            a["short"][lang] = r["ts"].strip()

    print("query: manifestations", file=sys.stderr)
    for r in batched(f"""SELECT DISTINCT ?abs ?d ?lang ?fmt ?url WHERE {{
  %VALUES%
  ?c jolux:isMemberOf ?abs ; jolux:dateApplicability ?d ; jolux:isRealizedBy ?e .
  ?e jolux:language ?lang ; jolux:isEmbodiedBy ?m .
  ?m jolux:userFormat ?fmt ; jolux:isExemplifiedBy ?url .
  FILTER(?fmt IN (<https://fedlex.data.admin.ch/vocabulary/user-format/xml>,
                  <https://fedlex.data.admin.ch/vocabulary/user-format/html>))
  FILTER(?d <= "{today}"^^xsd:date)
}}"""):
        lang = LANGS.get(r["lang"].rsplit("/", 1)[-1])
        a = abstracts.get(r["abs"])
        if not a or not lang:
            continue
        fmt = r["fmt"].rsplit("/", 1)[-1]
        a["versions"].setdefault(lang, {}).setdefault(r["d"], {})[fmt] = r["url"]

    cat = []
    for a in abstracts.values():
        if a.get("nlif") and a["nlif"] <= today:
            continue
        if a.get("eif") and a["eif"] > today:
            continue
        a["files"] = {}
        for lang, vers in a["versions"].items():
            d = max(vers)
            fm = vers[d]
            fmt = "xml" if "xml" in fm else "html"
            a["files"][lang] = {"date": d, "format": fmt, "url": fm[fmt]}
        del a["versions"]
        cat.append(a)
    cat.sort(key=lambda a: (a.get("sr") or "~", a["eli"]))
    return cat


def local_path(raw, lang, entry):
    rel = entry["eli"].split("/eli/", 1)[1].replace("/", "_")
    return raw / "files" / lang / f"{rel}.{entry['files'][lang]['format']}"


def download(s, url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return True
    delay = 2
    for _ in range(6):
        try:
            r = s.get(url, timeout=180)
            if r.status_code == 200:
                tmp = dest.with_suffix(dest.suffix + ".part")
                tmp.write_bytes(r.content)
                tmp.rename(dest)
                return True
            if r.status_code == 404:
                print(f"  404 {url}", file=sys.stderr)
                return False
            print(f"  HTTP {r.status_code} {url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  error {e} {url}", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    return False


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="?", default=str(here.parent.parent / "_raw" / "ch"))
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--langs", default="de,fr,it,rm")
    ap.add_argument("--refresh", action="store_true", help="rebuild catalog.json")
    args = ap.parse_args()
    raw = Path(args.raw)
    raw.mkdir(parents=True, exist_ok=True)
    s = session()

    catf = raw / "catalog.json"
    if args.refresh or not catf.exists():
        cat = build_catalog(s, args.date)
        catf.write_text(json.dumps({"date": args.date, "entries": cat}, ensure_ascii=False,
                                   indent=1))
    cat = json.loads(catf.read_text())["entries"]
    print(f"{len(cat)} in-force entries in catalogue", file=sys.stderr)

    jobs = []
    for lang in args.langs.split(","):
        (raw / "files" / lang).mkdir(parents=True, exist_ok=True)
        for e in cat:
            if lang in e["files"]:
                jobs.append((e["files"][lang]["url"], local_path(raw, lang, e)))
    print(f"{len(jobs)} files to ensure", file=sys.stderr)
    done = fail = 0
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for ok in ex.map(lambda j: download(s, *j), jobs):
            done += 1
            fail += not ok
            if done % 500 == 0:
                print(f"  {done}/{len(jobs)} ({fail} failed)", file=sys.stderr)
    print(f"done: {done} files, {fail} failed", file=sys.stderr)


if __name__ == "__main__":
    main()
