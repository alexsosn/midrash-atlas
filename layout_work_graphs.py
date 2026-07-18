#!/usr/bin/env python3
"""Precompute deterministic scalable layouts for complete individual-work graphs.

The browser retains a small force layout only for graphs of at most 120 nodes.
Larger graphs use Graphviz ``sfdp`` coordinates generated here and embedded in
the standalone atlas by ``export_atlas.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from export_atlas import HERE, write_outputs


DEFAULT_DATA = os.path.join(HERE, "atlas_data.json")
DEFAULT_OUTPUT = os.path.join(HERE, "work_layouts.json")
DEFAULT_THRESHOLD = 120
RAW_ONLY_LAYOUT_WEIGHT = 0.05


def evidence_digest(work_graphs: dict) -> str:
    payload = json.dumps(
        work_graphs, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def book_lookup(data: dict) -> list[str]:
    output = [""] * len(data["verse_index"])
    for book, start, end in data["book_ranges"]:
        output[start : end + 1] = [book] * (end - start + 1)
    return output


def merge_loci(verse_ids: list[int], books: list[str]) -> list[list[int]]:
    loci = []
    for verse_id in sorted(set(verse_ids)):
        if (
            loci
            and books[verse_id] == books[loci[-1][-1]]
            and verse_id - loci[-1][-1] <= 2
        ):
            loci[-1].append(verse_id)
        else:
            loci.append([verse_id])
    return loci


def work_edges(work: dict, books: list[str]) -> dict[tuple[int, int], float]:
    edges = defaultdict(float)
    for _source_id, verse_ids in work["sources"]:
        loci = merge_loci(verse_ids, books)
        if len(loci) < 2:
            continue
        pairs = [
            (left, right)
            for left_index, left in enumerate(loci)
            for right in loci[left_index + 1 :]
        ]
        locus_pair_weight = 1 / len(pairs)
        for left, right in pairs:
            verse_pair_weight = locus_pair_weight / (len(left) * len(right))
            for a in left:
                for b in right:
                    edges[(a, b) if a < b else (b, a)] += verse_pair_weight
    return edges


def raw_work_edges(work: dict) -> dict[tuple[int, int], float]:
    edges = defaultdict(float)
    for _source_id, verse_ids in work["sources"]:
        ordered = sorted(set(verse_ids))
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1 :]:
                edges[(left, right)] += 1
    return edges


def layout_edges(work: dict, books: list[str]) -> dict[tuple[int, int], float]:
    """Keep the locus geometry stable while positioning raw-only verses."""
    locus_edges = work_edges(work, books)
    locus_nodes = {node for edge in locus_edges for node in edge}
    combined = defaultdict(float, locus_edges)
    for edge, weight in raw_work_edges(work).items():
        if edge[0] not in locus_nodes or edge[1] not in locus_nodes:
            combined[edge] += RAW_ONLY_LAYOUT_WEIGHT * weight
    return combined


def normalize_positions(raw: dict[int, tuple[float, float]]):
    xs = [point[0] for point in raw.values()]
    ys = [point[1] for point in raw.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x or 1
    height = max_y - min_y or 1
    return [
        [node, round((x - min_x) / width, 5), round(1 - (y - min_y) / height, 5)]
        for node, (x, y) in sorted(raw.items())
    ]


def sfdp_layout(edges: dict[tuple[int, int], float]):
    nodes = sorted({node for edge in edges for node in edge})
    dot = [
        "strict graph G {",
        "graph [overlap=prism, start=17];",
        "node [shape=point];",
    ]
    dot.extend(f"{node};" for node in nodes)
    for (left, right), weight in sorted(edges.items()):
        dot.append(f'{left} -- {right} [weight="{max(.01, weight):.6g}"];')
    dot.append("}")
    result = subprocess.run(
        ["sfdp", "-Tplain"],
        input="\n".join(dot).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    raw = {}
    for line in result.stdout.decode().splitlines():
        fields = line.split()
        if fields and fields[0] == "node":
            raw[int(fields[1])] = (float(fields[2]), float(fields[3]))
    if len(raw) != len(nodes):
        raise RuntimeError(f"sfdp returned {len(raw)} of {len(nodes)} node positions")
    return normalize_positions(raw)


def generate_layouts(data: dict, threshold: int = DEFAULT_THRESHOLD, workers: int = 4):
    if not shutil.which("sfdp"):
        raise RuntimeError("Graphviz sfdp is required to refresh large-work layouts")
    books = book_lookup(data)
    tasks = []
    for category, works in data["work_graphs"].items():
        for work in works:
            edges = layout_edges(work, books)
            nodes = {node for edge in edges for node in edge}
            if len(nodes) > threshold:
                tasks.append((category, work["name"], edges, len(nodes)))

    layouts = defaultdict(dict)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(sfdp_layout, edges): (category, name, node_count, len(edges))
            for category, name, edges, node_count in tasks
        }
        completed = 0
        for future in as_completed(futures):
            category, name, node_count, edge_count = futures[future]
            layouts[category][name] = future.result()
            completed += 1
            print(
                f"layout {completed}/{len(tasks)}: {category} / {name} "
                f"({node_count} nodes, {edge_count} edges)",
                file=sys.stderr,
            )
    return {
        category: {name: layouts[category][name] for name in sorted(layouts[category])}
        for category in sorted(layouts)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    with open(args.data, encoding="utf-8") as handle:
        data = json.load(handle)
    digest = evidence_digest(data["work_graphs"])
    layouts = generate_layouts(data, args.threshold, args.workers)
    layout_count = sum(len(works) for works in layouts.values())
    position_count = sum(
        len(positions) for works in layouts.values() for positions in works.values()
    )
    bundle = {
        "format_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "atlas_method_version": data["meta"]["method_version"],
        "work_evidence_sha256": digest,
        "threshold": args.threshold,
        "layout_count": layout_count,
        "position_count": position_count,
        "layouts": layouts,
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")

    data["work_layouts"] = layouts
    data["meta"]["work_layouts"] = {
        key: bundle[key]
        for key in (
            "format_version", "generated_at", "work_evidence_sha256",
            "threshold", "layout_count", "position_count",
        )
    }
    write_outputs(data)
    print(
        f"wrote {args.output}: {layout_count} layouts / {position_count} positions",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
