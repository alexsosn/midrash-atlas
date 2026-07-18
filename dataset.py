#!/usr/bin/env python3
"""Shared, reproducible extraction of Tanakh citation links from the cache.

The cache contains one response from ``GET /api/links/{book}.{chapter}`` per
Tanakh chapter. A returned link may anchor a range spanning several chapters,
so simply taking ``anchorRefExpanded[0]`` both misplaces range citations and
counts the same long range once for every cached chapter.  This module clips
each expanded anchor to the chapter that was actually requested and gives each
verse ``1 / range_length`` weight.  Thus one Sefaria link contributes a total
weight of one, regardless of the size of its anchor range.
"""

from __future__ import annotations

import glob
import json
import os
import re
from collections.abc import Iterator

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("SEFARIA_CACHE", os.path.join(HERE, "cache"))
SHAPE_PATH = os.path.join(HERE, "tanakh_shape.json")

# Canonical chapter shapes returned by Sefaria's Shape API on 2026-07-17.
# https://www.sefaria.org/api/shape/Tanakh
with open(SHAPE_PATH, encoding="utf-8") as _shape_handle:
    TANAKH_SHAPE = json.load(_shape_handle)

VERSE_COUNTS = {entry["title"]: entry["chapters"] for entry in TANAKH_SHAPE}
BOOK_SECTIONS = {entry["title"]: entry["section"] for entry in TANAKH_SHAPE}
_BOOK_PATTERN = "|".join(
    re.escape(book) for book in sorted(VERSE_COUNTS, key=len, reverse=True)
)
VERSE_RE = re.compile(rf"^({_BOOK_PATTERN}) (\d+):(\d+)$")
CACHE_RE = re.compile(rf"^({_BOOK_PATTERN})\.(\d+)\.json$")

SELECTIVE = [
    "Talmud", "Midrash", "Halakhah", "Kabbalah", "Chasidut",
    "Jewish Thought", "Musar", "Mishnah",
]


def parse_verse(ref: str | None):
    """Return ``(book, chapter, verse)`` for a canonical Tanakh verse."""
    match = VERSE_RE.fullmatch(ref or "")
    if not match:
        return None
    book, chapter, verse = match.group(1), int(match.group(2)), int(match.group(3))
    shape = VERSE_COUNTS[book]
    if not (1 <= chapter <= len(shape) and 1 <= verse <= shape[chapter - 1]):
        return None
    return book, chapter, verse


def valid_verse(ref: str | None) -> bool:
    return parse_verse(ref) is not None


def _expanded_refs(link: dict) -> list[str]:
    expanded = link.get("anchorRefExpanded")
    if isinstance(expanded, list) and expanded:
        return expanded
    anchor = link.get("anchorRef")
    return [anchor] if valid_verse(anchor) else []


def iter_records(cache_dir: str | None = None) -> Iterator[dict]:
    """Yield normalized cached links with anchors clipped to the cache chapter.

    ``verses`` are canonical refs belonging to the requested chapter;
    ``anchor_span`` is the number of canonical verses in the full expanded
    anchor. Records with no canonical verse in that chapter are skipped.
    """
    cache_dir = cache_dir or CACHE
    for path in sorted(glob.glob(os.path.join(cache_dir, "*.json"))):
        cache_match = CACHE_RE.fullmatch(os.path.basename(path))
        if not cache_match:
            continue
        requested_book, requested_chapter = cache_match.group(1), int(cache_match.group(2))
        with open(path, encoding="utf-8") as handle:
            links = json.load(handle)
        for link in links:
            canonical = []
            for ref in _expanded_refs(link):
                parsed = parse_verse(ref)
                if parsed:
                    canonical.append((ref, parsed))
            if not canonical:
                continue
            verses = sorted({
                ref for ref, (book, chapter, _verse) in canonical
                if book == requested_book and chapter == requested_chapter
            })
            if not verses:
                continue
            yield {
                "category": link.get("category"),
                "index_title": link.get("index_title"),
                "sourceRef": link.get("sourceRef"),
                "type": link.get("type"),
                "anchorRef": link.get("anchorRef"),
                "anchor_span": len({ref for ref, _parsed in canonical}),
                "verses": verses,
            }


def sefaria_url(ref: str) -> str:
    """Build the documented public URL form of a Sefaria textual reference."""
    return "https://www.sefaria.org/" + ref.replace(" ", "_").replace(":", ".")
