#!/usr/bin/env python3
"""Build per-tradition citation profiles over all Tanakh verses and compare them.

Idea 1 from the project: each religious/exegetical tradition is a distribution
over which verses it cites. We compare those distributions two ways:
  - distinctiveness: verses a tradition cites far more than the pooled baseline
    (a TF-IDF-like lens, so ubiquitous verses don't dominate);
  - Jensen-Shannon divergence: a single number for "how differently do two
    traditions distribute their citations across Tanakh".
"""
import collections
import math

from dataset import SELECTIVE, iter_records

# "Selective" traditions cite a verse only when it matters to them, so their
# profiles are informative. Structural verse-by-verse commentary is excluded.
def load_bundle():
    """Return profiles, source sets, and per-work co-citation source units.

    A link to a range has total weight one, spread evenly over the canonical
    verses in that range. The same source/verse/category triple is counted only
    once even if Sefaria returned it in more than one cached response.
    """
    counts = collections.defaultdict(collections.Counter)
    works = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    sources = collections.defaultdict(set)
    graph_sources = collections.defaultdict(
        lambda: collections.defaultdict(lambda: collections.defaultdict(set))
    )
    seen = set()
    for record in iter_records():
        category = record["category"]
        source = record["sourceRef"]
        work = record["index_title"]
        if category not in SELECTIVE or not source:
            continue
        sources[category].add(source)
        if work and record["anchor_span"] <= 10:
            graph_sources[category][work][source].update(record["verses"])
        weight = 1.0 / record["anchor_span"]
        for verse in record["verses"]:
            key = category, source, verse
            if key not in seen:
                counts[category][verse] += weight
                if work:
                    works[category][work][verse] += weight
                seen.add(key)
    return counts, works, sources, graph_sources


def load():
    """Return range-normalized citation weight per category and verse."""
    return load_bundle()[0]

def normalize(counter):
    tot = sum(counter.values()) or 1
    return {k: v / tot for k, v in counter.items()}, tot

def js_divergence(p, q):
    """Jensen-Shannon divergence (base 2), in [0,1]."""
    keys = set(p) | set(q)
    m = {k: 0.5 * (p.get(k, 0) + q.get(k, 0)) for k in keys}
    def kl(a, b):
        s = 0.0
        for k in keys:
            ak = a.get(k, 0)
            if ak > 0:
                s += ak * math.log2(ak / b[k])
        return s
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)

def main():
    counts = load()
    trads = [t for t in SELECTIVE if t in counts]

    print("=" * 64)
    print("CITATION PROFILES OVER TANAKH  (selective traditions)")
    print("=" * 64)
    dists = {}
    for t in trads:
        dist, tot = normalize(counts[t])
        dists[t] = dist
        print("\n%-16s %8.1f citation weight across %4d distinct verses"
              % (t, tot, len(counts[t])))
        top = counts[t].most_common(6)
        print("   most-cited:", ", ".join("%s (%.1f)" % (v, n) for v, n in top))

    # Distinctiveness: pooled baseline across the selective traditions.
    pooled = collections.Counter()
    for t in trads:
        pooled.update(counts[t])
    pooled_dist, _ = normalize(pooled)

    print("\n" + "=" * 64)
    print("MOST DISTINCTIVE VERSES  (cited far above pooled baseline)")
    print("=" * 64)
    for t in trads:
        scored = []
        for v, p in dists[t].items():
            if counts[t][v] >= 3:  # ignore singletons as noise
                scored.append((p / pooled_dist[v], counts[t][v], v))
        scored.sort(reverse=True)
        picks = ", ".join("%s (w=%.1f, %.1f%%)" % (v, n, r * 100 / len(trads))
                          for r, n, v in scored[:4])
        print("\n%-16s %s" % (t, picks))

    print("\n" + "=" * 64)
    print("JENSEN-SHANNON DIVERGENCE  (0 = identical, 1 = disjoint)")
    print("=" * 64)
    hdr = "".join("%8s" % t[:7] for t in trads)
    print("%-16s%s" % ("", hdr))
    for a in trads:
        row = "".join("%8.3f" % js_divergence(dists[a], dists[b]) for b in trads)
        print("%-16s%s" % (a, row))

if __name__ == "__main__":
    main()
