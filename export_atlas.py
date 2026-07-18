#!/usr/bin/env python3
"""Build the self-contained Sefaria Citation Atlas and its research data.

Outputs:
  * ``atlas_data.json`` — documented, reusable derived data;
  * ``report.html`` — a standalone interactive research instrument with the
    data embedded, so it also works when opened directly from disk.
"""

from __future__ import annotations

import itertools
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import networkx as nx

from analyze import js_divergence, load_bundle, normalize
from dataset import BOOK_SECTIONS, CACHE, SELECTIVE, VERSE_COUNTS

HERE = os.path.dirname(os.path.abspath(__file__))
WORK_LAYOUTS_PATH = os.path.join(HERE, "work_layouts.json")
COLLECTION_LAYOUTS_PATH = os.path.join(HERE, "collection_layouts.json")

UA = {
    "Talmud": "Талмуд",
    "Midrash": "Мідраш",
    "Halakhah": "Галаха",
    "Kabbalah": "Кабала",
    "Chasidut": "Хасидут",
    "Jewish Thought": "Юдейська думка",
    "Musar": "Мусар",
    "Mishnah": "Мішна",
}

LOCUS_GAP = 2
VERSE_ORDER = {}
VERSE_BOOK = {}
VERSE_CHAPTER = {}
_ordinal = 0
for _book, _chapters in VERSE_COUNTS.items():
    for _chapter, _verse_count in enumerate(_chapters, 1):
        for _verse in range(1, _verse_count + 1):
            _ref = f"{_book} {_chapter}:{_verse}"
            VERSE_ORDER[_ref] = _ordinal
            VERSE_BOOK[_ref] = _book
            VERSE_CHAPTER[_ref] = _chapter
            _ordinal += 1


def linkage(matrix, labels):
    """Average-linkage agglomerative clustering as a nested JSON tree."""
    clusters = {i: [i] for i in range(len(labels))}
    trees = {i: {"name": labels[i]} for i in range(len(labels))}
    next_id = len(labels)
    while len(clusters) > 1:
        best = None
        for a, b in itertools.combinations(sorted(clusters), 2):
            distance = sum(matrix[i][j] for i in clusters[a] for j in clusters[b])
            distance /= len(clusters[a]) * len(clusters[b])
            candidate = distance, a, b
            if best is None or candidate < best:
                best = candidate
        distance, a, b = best
        trees[next_id] = {
            "h": round(distance, 4),
            "n": len(clusters[a]) + len(clusters[b]),
            "c": [trees[a], trees[b]],
        }
        clusters[next_id] = clusters[a] + clusters[b]
        for old in (a, b):
            del clusters[old], trees[old]
        next_id += 1
    return trees[next_id - 1]


def merge_loci(verses, gap=LOCUS_GAP):
    """Merge targets separated by at most one uncited verse into loci."""
    ordered = sorted(set(verses), key=VERSE_ORDER.get)
    loci = []
    for verse in ordered:
        if (loci and VERSE_BOOK[verse] == VERSE_BOOK[loci[-1][-1]] and
                VERSE_ORDER[verse] - VERSE_ORDER[loci[-1][-1]] <= gap):
            loci[-1].append(verse)
        else:
            loci.append([verse])
    return loci


def edges_from_sources(source_verses, mode):
    """Return raw or normalized cross-locus edges and exact evidence refs."""
    edges = defaultdict(float)
    evidence = defaultdict(set)
    locus_total = 0
    eligible_sources = 0
    for source, verses in source_verses.items():
        if len(verses) < 2:
            continue
        if mode == "raw":
            pairs = [([a], [b]) for a, b in itertools.combinations(
                sorted(verses, key=VERSE_ORDER.get), 2
            )]
        else:
            loci = merge_loci(verses)
            locus_total += len(loci)
            if len(loci) < 2:
                continue
            pairs = list(itertools.combinations(loci, 2))
        if not pairs:
            continue
        eligible_sources += 1
        locus_pair_weight = 1.0 if mode == "raw" else 1.0 / len(pairs)
        for left, right in pairs:
            verse_pair_weight = locus_pair_weight / (len(left) * len(right))
            for a in left:
                for b in right:
                    key = (a, b) if VERSE_ORDER[a] < VERSE_ORDER[b] else (b, a)
                    edges[key] += verse_pair_weight
                    evidence[key].add(source)
    return edges, evidence, {
        "eligible_sources": eligible_sources,
        "loci": locus_total if mode == "loci" else None,
    }


def adaptive_threshold(graph, target_edges=1100, min_nodes=70):
    """Choose a readable threshold without erasing sparse collections."""
    supports = sorted({attrs["support"] for _u, _v, attrs in graph.edges(data=True)})
    if not supports:
        return 1
    chosen = supports[0]
    for threshold in supports:
        kept = [(u, v) for u, v, attrs in graph.edges(data=True)
                if attrs["support"] >= threshold]
        nodes = {node for edge in kept for node in edge}
        if len(kept) <= target_edges and len(nodes) >= min_nodes:
            chosen = threshold
            break
    return chosen


def distance_band(a, b):
    if VERSE_BOOK[a] != VERSE_BOOK[b]:
        return "cross-book"
    distance = abs(VERSE_ORDER[a] - VERSE_ORDER[b])
    if distance == 1:
        return "adjacent"
    if distance <= 3:
        return "2-3"
    if distance <= 10:
        return "4-10"
    if VERSE_CHAPTER[a] == VERSE_CHAPTER[b]:
        return "same-chapter"
    if distance <= 50:
        return "same-book-near"
    return "same-book-far"


def add_surprise_scores(graph, strengths):
    """Add shrunken observed/expected lift within textual-distance bands."""
    nodes = list(graph)
    denominators = Counter()
    for a, b in itertools.combinations(nodes, 2):
        denominators[distance_band(a, b)] += strengths[a] * strengths[b]
    observed = Counter()
    for a, b, attrs in graph.edges(data=True):
        observed[distance_band(a, b)] += attrs["weight"]
    alpha = 0.25
    for a, b, attrs in graph.edges(data=True):
        band = distance_band(a, b)
        denominator = denominators[band]
        expected = (observed[band] * strengths[a] * strengths[b] / denominator
                    if denominator else 0)
        attrs["surprise"] = math.log2(
            (attrs["weight"] + alpha) / (expected + alpha)
        )


def graph_preview(category, source_verses, intern_source, mode, top_n=240):
    edges, evidence, audit = edges_from_sources(source_verses, mode)
    graph = nx.Graph()
    for (a, b), weight in edges.items():
        graph.add_edge(
            a, b, weight=weight, support=len(evidence[(a, b)])
        )

    communities = nx.community.louvain_communities(
        graph, weight="weight", seed=17
    )
    communities = sorted(communities, key=len, reverse=True)
    node_community = {
        node: index for index, community in enumerate(communities)
        for node in community
    }
    weighted_degree = dict(graph.degree(weight="weight"))
    keep = sorted(weighted_degree, key=weighted_degree.get, reverse=True)[:top_n]
    visible = graph.subgraph(keep).copy()
    add_surprise_scores(visible, weighted_degree)
    recommended_support = adaptive_threshold(visible)
    visible.remove_nodes_from([
        node for node in list(visible) if visible.degree(node) == 0
    ])

    positions = nx.spring_layout(
        visible,
        weight="weight",
        seed=17,
        k=1.6 / max(len(visible), 1) ** 0.5,
        iterations=140,
    )
    xs = [point[0] for point in positions.values()]
    ys = [point[1] for point in positions.values()]

    def scale(value, values):
        low, high = min(values), max(values)
        return round(0.5 if high == low else (value - low) / (high - low), 5)

    order = sorted(visible, key=lambda node: -weighted_degree[node])
    index = {node: i for i, node in enumerate(order)}

    nodes = []
    for node in order:
        neighbor_items = list(visible[node].items())
        neighbors = []
        seen_neighbors = set()
        for neighbor, attrs in (
            sorted(neighbor_items, key=lambda item: -item[1]["weight"])[:10] +
            sorted(neighbor_items, key=lambda item: -item[1].get("surprise", 0))[:10]
        ):
            if neighbor not in seen_neighbors:
                neighbors.append((neighbor, attrs))
                seen_neighbors.add(neighbor)
        nodes.append({
            "id": node,
            "x": scale(positions[node][0], xs),
            "y": scale(positions[node][1], ys),
            "d": round(weighted_degree[node], 2),
            "c": node_community.get(node, -1),
            "nb": [
                [index[neighbor], round(attrs["weight"], 4), attrs["support"],
                 [intern_source(source) for source in
                  sorted(evidence.get(
                      (node, neighbor) if VERSE_ORDER[node] < VERSE_ORDER[neighbor]
                      else (neighbor, node),
                      []
                  ))], round(attrs.get("surprise", 0), 3)]
                for neighbor, attrs in neighbors
            ],
        })

    edge_list = []
    for u, v, attrs in visible.edges(data=True):
        edge_list.append([
            index[u], index[v], round(attrs["weight"], 4), attrs["support"],
            round(attrs.get("surprise", 0), 3)
        ])
    edge_list.sort(key=lambda edge: -edge[2])
    surprise_values = [edge[4] for edge in edge_list]
    min_surprise = (0.5 if any(value >= 0.5 for value in surprise_values)
                    else max(surprise_values, default=0))

    community_meta = []
    for community_index, community in enumerate(communities):
        if len(community) < 10:
            continue
        subgraph = graph.subgraph(community)
        internal_degree = dict(subgraph.degree(weight="weight"))
        top = sorted(community, key=lambda node: -internal_degree[node])[:6]
        community_meta.append({
            "i": community_index,
            "size": len(community),
            "top": top,
        })

    modularity = nx.community.modularity(graph, communities, weight="weight")
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    density = nx.density(graph)
    print(
        f"{category}/{mode}: visible {len(nodes)} nodes / {len(edge_list)} edges "
        f"(full {node_count}/{edge_count}), Q={modularity:.3f}",
        file=sys.stderr,
    )
    return {
        "title": category,
        "category": category,
        "view_mode": mode,
        "method": "louvain",
        "nodes": nodes,
        "edges": edge_list,
        "Q": round(modularity, 3),
        "comms": community_meta,
        "community_count": len(communities),
        "substantial_community_count": len(community_meta),
        "min_support": 1,
        "recommended_support": recommended_support,
        "min_surprise": min_surprise,
        "full": {
            "nodes": node_count,
            "edges": edge_count,
            "total_weight": round(sum(edges.values()), 2),
            "support_sum": sum(len(refs) for refs in evidence.values()),
            "supporting_sources": audit["eligible_sources"],
            "loci": audit["loci"],
            "avg_degree": round(2 * edge_count / node_count, 2),
            "density": round(density, 5),
        },
    }


def collection_drilldowns(works, traditions, limit=18, min_weight=30, min_verses=15):
    """Build within-category work dendrograms with explicit coverage metadata."""
    output = {}
    for category in traditions:
        candidates = []
        for name, counter in works[category].items():
            total = sum(counter.values())
            if total >= min_weight and len(counter) >= min_verses:
                candidates.append((total, name, counter))
        candidates.sort(reverse=True)
        candidates = candidates[:limit]
        labels = [name for _total, name, _counter in candidates]
        distributions = [normalize(counter)[0] for _total, _name, counter in candidates]
        matrix = [
            [round(js_divergence(a, b), 4) for b in distributions]
            for a in distributions
        ]
        output[category] = {
            "works": [
                {
                    "name": name,
                    "total": round(total, 1),
                    "distinct": len(counter),
                    "top": [[verse, round(weight, 2)]
                            for verse, weight in counter.most_common(5)],
                }
                for total, name, counter in candidates
            ],
            "matrix": matrix,
            "dendro": linkage(matrix, labels) if len(labels) >= 2 else None,
            "included": len(candidates),
            "eligible": sum(
                1 for counter in works[category].values()
                if sum(counter.values()) >= min_weight and len(counter) >= min_verses
            ),
            "total_works": len(works[category]),
            "threshold": {"weight": min_weight, "verses": min_verses},
        }
    return output


def cache_metadata():
    paths = [
        os.path.join(CACHE, name) for name in os.listdir(CACHE)
        if name.endswith(".json")
    ]
    newest = max(os.path.getmtime(path) for path in paths)
    return {
        "files": len(paths),
        "bytes": sum(os.path.getsize(path) for path in paths),
        "newest": datetime.fromtimestamp(newest, timezone.utc).isoformat(),
    }


def build_data():
    counts, works, sources, graph_sources = load_bundle()
    traditions = [tradition for tradition in SELECTIVE if tradition in counts]
    distributions = {
        tradition: normalize(counts[tradition])[0] for tradition in traditions
    }
    matrix = [
        [round(js_divergence(distributions[a], distributions[b]), 4)
         for b in traditions]
        for a in traditions
    ]
    pairs = [
        (matrix[i][j], traditions[i], traditions[j])
        for i in range(len(traditions)) for j in range(i + 1, len(traditions))
    ]
    cache = cache_metadata()
    cited_union = set().union(*(counts[tradition] for tradition in traditions))
    tanakh_verses = sum(sum(chapters) for chapters in VERSE_COUNTS.values())
    verse_index = [
        f"{book} {chapter}:{verse}"
        for book, chapters in VERSE_COUNTS.items()
        for chapter, verse_count in enumerate(chapters, 1)
        for verse in range(1, verse_count + 1)
    ]
    verse_id = {verse: index for index, verse in enumerate(verse_index)}
    data = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cache": cache,
            "source": "https://www.sefaria.org/api/links/{tref}?with_text=0",
            "shape_source": "https://www.sefaria.org/api/shape/{title}",
            "method_version": "8.0-full-collection-graphs",
            "notes": [
                "Canonical Tanakh refs are validated against the full Sefaria Tanakh Shape API response.",
                "A range link has total citation weight 1, divided over its canonical verses.",
                "Duplicate source/verse/category triples use the shortest, most specific anchor span regardless of record order.",
                "Co-citation excludes single anchors spanning more than 10 verses.",
                "The exact Sefaria source ref is the co-citation discourse unit.",
                "Default graphs merge targets separated by at most one uncited verse into source-specific loci.",
                "Within-locus pairs are suppressed and each eligible source contributes total graph weight one.",
                "Unexpected association is shrunken observed/expected lift conditioned on verse popularity and textual-distance band.",
                "Compact collection previews retain support-one edges but are never used as the interactive analytical graph.",
                "Individual-work graphs retain every vertex and edge in the selected edge model; no centrality top-N selection is applied.",
                "Interactive collection graphs are reconstructed from all exact source evidence and use precomputed full-graph layouts; the retained collection_previews field is explicitly non-analytical.",
            ],
        },
        "traditions": traditions,
        "ua": UA,
        "summary": {
            "tanakh_verses": tanakh_verses,
            "tanakh_books": len(VERSE_COUNTS),
            "tanakh_chapters": sum(len(chapters) for chapters in VERSE_COUNTS.values()),
            "union_distinct": len(cited_union),
            "source_refs": sum(len(sources[tradition]) for tradition in traditions),
            "works": sum(len(works[tradition]) for tradition in traditions),
        },
        "totals": {
            tradition: round(sum(counts[tradition].values()), 1)
            for tradition in traditions
        },
        "distinct": {
            tradition: len(counts[tradition]) for tradition in traditions
        },
        "matrix": matrix,
        "dendro": linkage(matrix, traditions),
        "extremes": {
            "nearest": list(min(pairs)),
            "farthest": list(max(pairs)),
        },
        "top_cited": {
            tradition: [[verse, round(weight, 2)]
                        for verse, weight in counts[tradition].most_common(12)]
            for tradition in traditions
        },
        "profiles": {
            tradition: [[verse, round(weight, 3)]
                        for verse, weight in counts[tradition].items()]
            for tradition in traditions
        },
        "source_counts": {
            tradition: len(sources[tradition]) for tradition in traditions
        },
        "collections": collection_drilldowns(works, traditions),
        "verse_index": verse_index,
        "book_sections": BOOK_SECTIONS,
        "book_ranges": [],
        "source_index": [],
        "collection_previews": {},
        "work_graphs": {},
        "work_layouts": {},
        "collection_layouts": {},
    }
    range_start = 0
    for book, chapters in VERSE_COUNTS.items():
        range_end = range_start + sum(chapters) - 1
        data["book_ranges"].append([book, range_start, range_end])
        range_start = range_end + 1
    source_id = {}

    def intern_source(source):
        if source not in source_id:
            source_id[source] = len(data["source_index"])
            data["source_index"].append(source)
        return source_id[source]

    for category in traditions:
        category_sources = defaultdict(set)
        compact_works = []
        for work, source_map in graph_sources[category].items():
            compact_sources = []
            for source, verses in source_map.items():
                if len(verses) < 2:
                    continue
                category_sources[source].update(verses)
                compact_sources.append([
                    intern_source(source),
                    sorted(verse_id[verse] for verse in verses)
                ])
            if compact_sources:
                compact_works.append({
                    "name": work,
                    "sources": compact_sources,
                })
        data["collection_previews"][category] = {
            mode: graph_preview(
                category, category_sources, intern_source, mode
            )
            for mode in ("loci", "raw")
        }
        data["work_graphs"][category] = sorted(
            compact_works, key=lambda item: item["name"].casefold()
        )
    work_payload = json.dumps(
        data["work_graphs"], ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode()
    work_digest = hashlib.sha256(work_payload).hexdigest()
    data["meta"]["work_evidence_sha256"] = work_digest
    if os.path.exists(WORK_LAYOUTS_PATH):
        with open(WORK_LAYOUTS_PATH, encoding="utf-8") as handle:
            layout_bundle = json.load(handle)
        if (
            layout_bundle.get("format_version") == 2
            and layout_bundle.get("work_evidence_sha256") == work_digest
        ):
            data["work_layouts"] = layout_bundle["layouts"]
            data["meta"]["work_layouts"] = {
                key: layout_bundle[key]
                for key in (
                    "format_version", "generated_at", "work_evidence_sha256",
                    "threshold", "layout_count", "position_count",
                )
            }
    if os.path.exists(COLLECTION_LAYOUTS_PATH):
        with open(COLLECTION_LAYOUTS_PATH, encoding="utf-8") as handle:
            collection_bundle = json.load(handle)
        if (
            collection_bundle.get("format_version") == 1
            and collection_bundle.get("work_evidence_sha256") == work_digest
        ):
            data["collection_layouts"] = collection_bundle["layouts"]
            data["meta"]["collection_layouts"] = {
                key: collection_bundle[key]
                for key in (
                    "format_version", "generated_at", "work_evidence_sha256",
                    "layout_count", "position_count",
                )
            }
    return data


def write_outputs(data):
    data_path = os.path.join(HERE, "atlas_data.json")
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))

    template_path = os.path.join(HERE, "atlas_template.html")
    report_path = os.path.join(HERE, "report.html")
    with open(template_path, encoding="utf-8") as handle:
        template = handle.read()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c")
    marker = "/*__ATLAS_DATA__*/"
    if marker not in template:
        raise RuntimeError(f"missing data marker in {template_path}")
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(template.replace(marker, payload))

    print(f"wrote {data_path} ({os.path.getsize(data_path) / 1024:.0f} KB)", file=sys.stderr)
    print(f"wrote {report_path} ({os.path.getsize(report_path) / 1024:.0f} KB)", file=sys.stderr)


def main():
    write_outputs(build_data())


if __name__ == "__main__":
    main()
