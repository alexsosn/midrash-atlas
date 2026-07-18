#!/usr/bin/env python3
"""Idea 2: co-citation graphs of Tanakh verses, per tradition.

Two verses are joined by an edge when the SAME source passage cites both of
them (weight = how many passages do so). We build this graph separately for
each tradition from the already-cached verse-side links -- grouping by source
recovers co-citation without new API calls -- then compare Talmud vs Midrash:

  - graph size / density / clustering (how tightly knit the intertext is);
  - edge "span": distance between co-cited verses along canonical Tanakh order,
    a direct test of the associativity hypothesis (does Midrash stitch
    together verses that sit far apart, more than the Talmud does?);
  - communities (label propagation) -- the exegetical neighborhoods.
"""
import collections
import itertools
import random

from dataset import VERSE_COUNTS, iter_records, parse_verse
random.seed(17)

# Linear position of a verse: cumulative chapter offset so distances are
# comparable across books (chapter counts in canonical Tanakh order).
BOOK_CHAPTERS = [(book, len(chapters)) for book, chapters in VERSE_COUNTS.items()]
OFFSET, _acc = {}, 0
for _b, _n in BOOK_CHAPTERS:
    OFFSET[_b] = _acc
    _acc += _n
def pos(verse):
    """Coarse linear position in chapters along Tanakh, or ``None`` if the
    ref is not a canonical single Tanakh verse."""
    parsed = parse_verse(verse)
    if not parsed:
        return None
    book, ch, vs = parsed
    return OFFSET[book] + ch + vs / 100.0

def norm_source(ref):
    """Use the exact Sefaria source ref as the reproducible discourse unit.

    Texts in Sefaria have different structural depths, so removing a final
    numeric segment would merge a Talmud page, a midrash section, and a
    commentary comment in inconsistent ways. Exact refs preserve the editor's
    asserted source granularity and keep every evidence link auditable.
    """
    return ref

def build(category, with_sources=False, max_anchor_span=10):
    """Build weighted co-citation edges for one Sefaria category.

    A co-citation means that two canonical Tanakh verses are linked from the
    same normalized source discourse unit. Extremely broad single anchors are
    excluded: a link covering more than ``max_anchor_span`` verses is a range
    annotation, not evidence that the source explicitly co-cites every pair in
    that range.

    When ``with_sources`` is true, also return every exact, linkable Sefaria
    source ref supporting each edge for inspection in the atlas.
    """
    src_verses = collections.defaultdict(set)
    for record in iter_records():
        if (record["category"] != category
                or record["anchor_span"] > max_anchor_span
                or not record["sourceRef"]):
            continue
        unit = norm_source(record["sourceRef"])
        src_verses[unit].update(record["verses"])
    edges = collections.Counter()      # (v1,v2) sorted -> weight
    sources = collections.defaultdict(list)
    for source, verses in src_verses.items():
        if len(verses) < 2:
            continue
        for a, b in itertools.combinations(sorted(verses), 2):
            edges[(a, b)] += 1
            if with_sources:
                sources[(a, b)].append(source)
    return (edges, sources) if with_sources else edges

def adjacency(edges):
    adj = collections.defaultdict(dict)
    for (a, b), w in edges.items():
        adj[a][b] = w
        adj[b][a] = w
    return adj

def clustering(adj):
    """Global clustering coefficient (transitivity)."""
    triangles = triples = 0
    for node, nbrs in adj.items():
        ns = list(nbrs)
        k = len(ns)
        triples += k * (k - 1)
        for i in range(k):
            for j in range(i + 1, k):
                if ns[j] in adj[ns[i]]:
                    triangles += 2
    return triangles / triples if triples else 0.0

def label_propagation(adj, rounds=25):
    labels = {n: n for n in adj}
    nodes = list(adj)
    for _ in range(rounds):
        random.shuffle(nodes)
        changed = False
        for n in nodes:
            if not adj[n]:
                continue
            tally = collections.Counter()
            for nb, w in adj[n].items():
                tally[labels[nb]] += w
            best = max(tally.values())
            winners = [lab for lab, c in tally.items() if c == best]
            new = random.choice(winners)
            if new != labels[n]:
                labels[n] = new
                changed = True
        if not changed:
            break
    comms = collections.defaultdict(list)
    for n, lab in labels.items():
        comms[lab].append(n)
    return sorted(comms.values(), key=len, reverse=True)

def span_stats(edges):
    spans = [abs(pos(a) - pos(b)) for (a, b) in edges]
    cross_book = sum(1 for (a, b) in edges
                     if parse_verse(a)[0] != parse_verse(b)[0])
    spans.sort()
    n = len(spans)
    mean = sum(spans) / n if n else 0
    median = spans[n // 2] if n else 0
    return mean, median, cross_book / n if n else 0

def report(category):
    edges = build(category)
    adj = adjacency(edges)
    nodes = len(adj)
    n_edges = len(edges)
    total_w = sum(edges.values())
    avg_deg = 2 * n_edges / nodes if nodes else 0
    density = 2 * n_edges / (nodes * (nodes - 1)) if nodes > 1 else 0
    cc = clustering(adj)
    mean_span, median_span, cross = span_stats(edges)
    comms = [c for c in label_propagation(adj) if len(c) >= 4]

    print("\n" + "=" * 64)
    print("CO-CITATION GRAPH:  %s" % category)
    print("=" * 64)
    print("verses (nodes)        : %d" % nodes)
    print("co-cited pairs (edges): %d   (total weight %d)" % (n_edges, total_w))
    print("avg degree            : %.1f" % avg_deg)
    print("density               : %.4f" % density)
    print("clustering coeff      : %.3f" % cc)
    print("edge span  mean/median: %.1f / %.1f chapters" % (mean_span, median_span))
    print("cross-book edges      : %.1f%%" % (cross * 100))
    print("communities (>=4)     : %d" % len(comms))
    print("top co-cited pairs    :")
    for (a, b), w in edges.most_common(6):
        print("   %-22s + %-22s  x%d" % (a, b, w))
    print("largest communities   :")
    for c in comms[:3]:
        sample = ", ".join(sorted(c, key=pos)[:8])
        print("   [%d verses] %s%s" % (len(c), sample, " ..." if len(c) > 8 else ""))

if __name__ == "__main__":
    for cat in ("Talmud", "Midrash"):
        report(cat)
