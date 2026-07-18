#!/usr/bin/env python3
"""Real community detection (Louvain) on the co-citation graphs.

Replaces the unreliable label-propagation pass in cocitation.py: Louvain
maximizes modularity, so dense graphs no longer collapse into one giant
community. Run with python3.11 (needs networkx).

Outputs, per tradition:
  - modularity + community size distribution;
  - the largest communities, each summarized by its strongest verses
    (weighted degree inside the community) so the exegetical "neighborhood"
    is readable.
Then compares Talmud vs Midrash partitions on their shared verses with the
Adjusted Rand Index: ARI ~ 1 means both traditions carve Tanakh into the
same neighborhoods, ~ 0 means independent carvings.
"""
import collections, itertools, random
import networkx as nx
from cocitation import build, pos

random.seed(17)

def graph(category):
    G = nx.Graph()
    for (a, b), w in build(category).items():
        G.add_edge(a, b, weight=w)
    return G

def louvain(G):
    comms = nx.community.louvain_communities(G, weight="weight", seed=17)
    Q = nx.community.modularity(G, comms, weight="weight")
    return sorted(comms, key=len, reverse=True), Q

def describe(G, comm, k=6):
    """Top verses of a community by weighted degree within the community."""
    sub = G.subgraph(comm)
    deg = sub.degree(weight="weight")
    top = sorted(comm, key=lambda n: -deg[n])[:k]
    return ", ".join(top)

def ari(labels_a, labels_b, nodes):
    """Adjusted Rand Index between two partitions restricted to `nodes`."""
    from math import comb
    pairs = collections.Counter()
    ca, cb = collections.Counter(), collections.Counter()
    for n in nodes:
        pairs[(labels_a[n], labels_b[n])] += 1
        ca[labels_a[n]] += 1
        cb[labels_b[n]] += 1
    sum_ij = sum(comb(v, 2) for v in pairs.values())
    sum_a = sum(comb(v, 2) for v in ca.values())
    sum_b = sum(comb(v, 2) for v in cb.values())
    N = comb(len(nodes), 2)
    expected = sum_a * sum_b / N
    max_idx = (sum_a + sum_b) / 2
    return (sum_ij - expected) / (max_idx - expected)

def main():
    results = {}
    for cat in ("Talmud", "Midrash"):
        G = graph(cat)
        comms, Q = louvain(G)
        results[cat] = (G, comms)
        big = [c for c in comms if len(c) >= 10]
        print("\n" + "=" * 66)
        print("LOUVAIN COMMUNITIES:  %s" % cat)
        print("=" * 66)
        print("nodes %d | edges %d | modularity Q = %.3f" %
              (G.number_of_nodes(), G.number_of_edges(), Q))
        print("communities: %d total, %d with >=10 verses; sizes: %s" %
              (len(comms), len(big),
               ", ".join(str(len(c)) for c in comms[:10]) + " ..."))
        print("\nlargest neighborhoods (top verses by internal weight):")
        for i, c in enumerate(comms[:8]):
            print("  #%d [%4d verses]  %s" % (i + 1, len(c), describe(G, c)))

    # Do the two traditions carve the same text into the same neighborhoods?
    (Gt, ct), (Gm, cm) = results["Talmud"], results["Midrash"]
    lab_t = {n: i for i, c in enumerate(ct) for n in c}
    lab_m = {n: i for i, c in enumerate(cm) for n in c}
    shared = sorted(set(lab_t) & set(lab_m))
    score = ari(lab_t, lab_m, shared)
    print("\n" + "=" * 66)
    print("PARTITION AGREEMENT  (Talmud vs Midrash, %d shared verses)" % len(shared))
    print("=" * 66)
    print("Adjusted Rand Index = %.3f   (1 = same neighborhoods, 0 = independent)" % score)

if __name__ == "__main__":
    main()
