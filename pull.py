#!/usr/bin/env python3
"""Pull Sefaria links for all Tanakh books, chapter by chapter.

Sefaria's Links API returns, for every anchor ref (a Tanakh verse here), all
sources that link to it -- each with `category` (Talmud, Midrash, Kabbalah...),
`index_title`, and the source ref. That is exactly a citation graph keyed by
verse, so we just cache it per chapter.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from dataset import VERSE_COUNTS

CACHE = os.environ.get(
    "SEFARIA_CACHE", os.path.join(os.path.dirname(__file__), "cache")
)

def fetch(ref, retries=3):
    url_ref = urllib.parse.quote(ref.replace(" ", "_"), safe="._-")
    url = "https://www.sefaria.org/api/links/%s?with_text=0" % url_ref
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "citation-graph-proto"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("books", nargs="*", help="optional exact Sefaria book titles")
    parser.add_argument("--delay", type=float, default=0.3, help="seconds between requests")
    args = parser.parse_args()
    books = args.books or list(VERSE_COUNTS)
    unknown = sorted(set(books) - set(VERSE_COUNTS))
    if unknown:
        parser.error("unknown Tanakh book(s): " + ", ".join(unknown))
    os.makedirs(CACHE, exist_ok=True)
    for book in books:
        nchap = len(VERSE_COUNTS[book])
        for ch in range(1, nchap + 1):
            path = os.path.join(CACHE, "%s.%d.json" % (book, ch))
            if os.path.exists(path):
                continue
            ref = "%s.%d" % (book, ch)
            data = fetch(ref)
            # keep only the fields we need, to shrink cache
            slim = [{
                "anchorRef": x.get("anchorRef"),
                "anchorRefExpanded": x.get("anchorRefExpanded"),
                "category": x.get("category"),
                "index_title": x.get("index_title"),
                "sourceRef": x.get("sourceRef"),
                "type": x.get("type"),
            } for x in data]
            temporary = path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as f:
                json.dump(slim, f, ensure_ascii=False)
            os.replace(temporary, path)
            print("cached %s: %d links" % (ref, len(slim)), file=sys.stderr)
            time.sleep(args.delay)

if __name__ == "__main__":
    main()
