#!/usr/bin/env python3
"""Export citable graph evidence bundles from ``atlas_data.json``.

The interactive atlas intentionally shows bounded graph slices. This command
uses the compact exact-source evidence embedded in the dataset to reconstruct
the selected collection or work before writing researcher-friendly tables.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

import networkx as nx

from dataset import parse_verse, sefaria_url
from export_atlas import add_surprise_scores, distance_band, edges_from_sources


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(HERE, "atlas_data.json")


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned or "graph"


def source_map_for(data: dict, category: str, work_name: str | None = None):
    if category not in data.get("work_graphs", {}):
        available = ", ".join(data.get("traditions", []))
        raise ValueError(f"unknown category {category!r}; choose one of: {available}")

    works = data["work_graphs"][category]
    if work_name is not None:
        works = [work for work in works if work["name"] == work_name]
        if not works:
            raise ValueError(f"unknown work {work_name!r} in {category}")

    source_verses = defaultdict(set)
    for work in works:
        for source_id, verse_ids in work["sources"]:
            source = data["source_index"][source_id]
            source_verses[source].update(data["verse_index"][verse_id] for verse_id in verse_ids)
    return source_verses


def build_export_graph(
    data: dict,
    category: str,
    work_name: str | None,
    mode: str,
    min_support: int,
    min_surprise: float | None,
):
    if min_support < 1:
        raise ValueError("min_support must be at least 1")
    if mode not in {"loci", "raw", "unexpected"}:
        raise ValueError("mode must be loci, raw, or unexpected")

    source_verses = source_map_for(data, category, work_name)
    base_mode = "loci" if mode == "unexpected" else mode
    weights, evidence, audit = edges_from_sources(source_verses, base_mode)

    graph = nx.Graph()
    for (left, right), weight in weights.items():
        graph.add_edge(
            left,
            right,
            weight=weight,
            support=len(evidence[(left, right)]),
            sources=sorted(evidence[(left, right)]),
        )
    strengths = dict(graph.degree(weight="weight"))
    add_surprise_scores(graph, strengths)

    remove = [
        (left, right)
        for left, right, attrs in graph.edges(data=True)
        if attrs["support"] < min_support
        or (min_surprise is not None and attrs["surprise"] < min_surprise)
    ]
    graph.remove_edges_from(remove)
    graph.remove_nodes_from(list(nx.isolates(graph)))
    if not graph.number_of_edges():
        raise ValueError("the selected filters leave no evidence edges")

    if work_name is None:
        communities = nx.community.louvain_communities(graph, weight="weight", seed=17)
        community_method = "Louvain (seed 17)"
    else:
        communities = list(nx.connected_components(graph))
        community_method = "connected components"
    communities = sorted(communities, key=lambda members: (-len(members), sorted(members)[0]))
    community_for = {
        verse: index + 1
        for index, members in enumerate(communities)
        for verse in members
    }
    return graph, community_for, community_method, audit


def write_csv(path: str, fields: list[str], rows: list[dict]):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def export_bundle(
    data_path: str,
    output_dir: str,
    category: str,
    work_name: str | None = None,
    mode: str = "loci",
    min_support: int = 1,
    min_surprise: float | None = None,
):
    with open(data_path, encoding="utf-8") as handle:
        data = json.load(handle)

    graph, community_for, community_method, audit = build_export_graph(
        data, category, work_name, mode, min_support, min_surprise
    )
    os.makedirs(output_dir, exist_ok=True)
    node_path = os.path.join(output_dir, "nodes.csv")
    edge_path = os.path.join(output_dir, "edge-evidence.csv")
    manifest_path = os.path.join(output_dir, "manifest.json")

    weighted_degree = dict(graph.degree(weight="weight"))
    node_rows = []
    for ref in sorted(graph, key=lambda item: (-weighted_degree[item], item)):
        book, chapter, verse = parse_verse(ref)
        node_rows.append({
            "ref": ref,
            "sefaria_url": sefaria_url(ref),
            "book": book,
            "chapter": chapter,
            "verse": verse,
            "community": community_for[ref],
            "degree": graph.degree(ref),
            "weighted_degree": round(weighted_degree[ref], 8),
        })

    edge_rows = []
    ordered_edges = sorted(
        graph.edges(data=True),
        key=lambda item: (-item[2]["weight"], item[0], item[1]),
    )
    for edge_number, (left, right, attrs) in enumerate(ordered_edges, 1):
        edge_id = f"E{edge_number:06d}"
        for source_ref in attrs["sources"]:
            edge_rows.append({
                "edge_id": edge_id,
                "verse_a": left,
                "verse_b": right,
                "verse_a_url": sefaria_url(left),
                "verse_b_url": sefaria_url(right),
                "distance_band": distance_band(left, right),
                "weight": round(attrs["weight"], 8),
                "source_support": attrs["support"],
                "surprise_bits": round(attrs["surprise"], 6),
                "community_a": community_for[left],
                "community_b": community_for[right],
                "source_ref": source_ref,
                "source_url": sefaria_url(source_ref),
            })

    write_csv(node_path, [
        "ref", "sefaria_url", "book", "chapter", "verse", "community",
        "degree", "weighted_degree",
    ], node_rows)
    write_csv(edge_path, [
        "edge_id", "verse_a", "verse_b", "verse_a_url", "verse_b_url",
        "distance_band", "weight", "source_support", "surprise_bits",
        "community_a", "community_b", "source_ref", "source_url",
    ], edge_rows)

    manifest = {
        "format_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "atlas": {
            "path": os.path.abspath(data_path),
            "sha256": file_sha256(data_path),
            "generated_at": data["meta"]["generated_at"],
            "method_version": data["meta"]["method_version"],
            "cache": data["meta"]["cache"],
        },
        "selection": {
            "category": category,
            "work": work_name,
            "mode": mode,
            "base_edge_model": "loci" if mode == "unexpected" else mode,
            "min_support": min_support,
            "min_surprise_bits": min_surprise,
        },
        "scope": (
            "Full graph reconstructed from compact exact-source evidence; "
            "not limited to the interactive display's top-node slice."
        ),
        "community_method": community_method,
        "counts": {
            "nodes": len(node_rows),
            "edges": graph.number_of_edges(),
            "evidence_rows": len(edge_rows),
            "unique_source_refs": len({row["source_ref"] for row in edge_rows}),
            "eligible_source_refs_before_filters": audit["eligible_sources"],
        },
        "method_notes": data["meta"]["notes"],
        "files": {
            "nodes.csv": file_sha256(node_path),
            "edge-evidence.csv": file_sha256(edge_path),
        },
    }
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return manifest


def parser():
    argument_parser = argparse.ArgumentParser(
        description="Export an auditable graph evidence bundle from the atlas."
    )
    argument_parser.add_argument("--data", default=DEFAULT_DATA, help="atlas_data.json path")
    argument_parser.add_argument("--category", required=True, help="Sefaria category")
    argument_parser.add_argument("--work", help="exact work name; omit for the full category")
    argument_parser.add_argument(
        "--list-works", action="store_true", help="print exact work names in the category"
    )
    argument_parser.add_argument(
        "--mode", choices=("loci", "unexpected", "raw"), default="loci"
    )
    argument_parser.add_argument("--min-support", type=int, default=1)
    argument_parser.add_argument("--min-surprise", type=float)
    argument_parser.add_argument("--output", help="bundle directory")
    return argument_parser


def main():
    args = parser().parse_args()
    if args.list_works:
        with open(args.data, encoding="utf-8") as handle:
            data = json.load(handle)
        if args.category not in data.get("work_graphs", {}):
            available = ", ".join(data.get("traditions", []))
            raise SystemExit(
                f"unknown category {args.category!r}; choose one of: {available}"
            )
        for work in data["work_graphs"][args.category]:
            print(work["name"])
        return
    label = args.category + ("-" + args.work if args.work else "") + "-" + args.mode
    output = args.output or os.path.join(HERE, "exports", slug(label))
    try:
        manifest = export_bundle(
            args.data,
            output,
            args.category,
            args.work,
            args.mode,
            args.min_support,
            args.min_surprise,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    counts = manifest["counts"]
    print(
        f"wrote {output}: {counts['nodes']} nodes, {counts['edges']} edges, "
        f"{counts['evidence_rows']} evidence rows"
    )


if __name__ == "__main__":
    main()
