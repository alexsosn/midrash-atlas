#!/usr/bin/env python3
"""Precompute deterministic layouts and Louvain membership for full collections."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import networkx as nx

from export_atlas import HERE, write_outputs
from layout_work_graphs import (
    book_lookup,
    evidence_digest,
    raw_work_edges,
    sfdp_layout,
    work_edges,
)


DEFAULT_DATA = os.path.join(HERE, "atlas_data.json")
DEFAULT_OUTPUT = os.path.join(HERE, "collection_layouts.json")


def collection_edges(works: list[dict], books: list[str], mode: str):
    sources = defaultdict(set)
    for work in works:
        for source_id, verse_ids in work["sources"]:
            sources[source_id].update(verse_ids)
    combined = {
        "sources": [
            [source_id, sorted(verse_ids)]
            for source_id, verse_ids in sources.items()
        ]
    }
    return (
        raw_work_edges(combined)
        if mode == "raw"
        else work_edges(combined, books)
    )


def layout_collection(edges: dict[tuple[int, int], float]):
    graph = nx.Graph()
    for (left, right), weight in edges.items():
        graph.add_edge(left, right, weight=weight)
    communities = sorted(
        nx.community.louvain_communities(graph, weight="weight", seed=17),
        key=len,
        reverse=True,
    )
    community_for = {
        node: index
        for index, community in enumerate(communities)
        for node in community
    }
    positions = sfdp_layout(edges)
    rows = [
        [node, x, y, community_for[node]]
        for node, x, y in positions
    ]
    return {
        "nodes": rows,
        "Q": round(
            nx.community.modularity(graph, communities, weight="weight"), 5
        ),
        "community_count": len(communities),
        "edge_count": len(edges),
    }


def generate_layouts(data: dict, workers: int = 2):
    books = book_lookup(data)
    tasks = []
    for category, works in data["work_graphs"].items():
        for mode in ("loci", "raw"):
            edges = collection_edges(works, books, mode)
            tasks.append((category, mode, edges))

    layouts = defaultdict(dict)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(layout_collection, edges): (category, mode)
            for category, mode, edges in tasks
        }
        completed = 0
        for future in as_completed(futures):
            category, mode = futures[future]
            layouts[category][mode] = future.result()
            completed += 1
            result = layouts[category][mode]
            print(
                f"layout {completed}/{len(tasks)}: {category} / {mode} "
                f"({len(result['nodes'])} nodes, {result['edge_count']} edges, "
                f"Q={result['Q']:.3f})",
                file=sys.stderr,
            )
    return {
        category: {
            mode: layouts[category][mode]
            for mode in ("loci", "raw")
        }
        for category in sorted(layouts)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    with open(args.data, encoding="utf-8") as handle:
        data = json.load(handle)
    digest = evidence_digest(data["work_graphs"])
    layouts = generate_layouts(data, args.workers)
    layout_count = sum(len(modes) for modes in layouts.values())
    position_count = sum(
        len(layout["nodes"])
        for modes in layouts.values()
        for layout in modes.values()
    )
    bundle = {
        "format_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "atlas_method_version": data["meta"]["method_version"],
        "work_evidence_sha256": digest,
        "layout_count": layout_count,
        "position_count": position_count,
        "layouts": layouts,
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")

    data["collection_layouts"] = layouts
    data["meta"]["collection_layouts"] = {
        key: bundle[key]
        for key in (
            "format_version",
            "generated_at",
            "work_evidence_sha256",
            "layout_count",
            "position_count",
        )
    }
    write_outputs(data)
    print(
        f"wrote {args.output}: {layout_count} layouts / "
        f"{position_count} positions",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
