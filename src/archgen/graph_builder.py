from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Protocol

from archgen.detection import Detection
from archgen.graph import ArchitectureGraph, Edge, Node


class SummaryWithDetections(Protocol):
    detections: list[Detection]


def build_architecture_graph(summary: SummaryWithDetections) -> ArchitectureGraph:
    nodes, warnings = build_nodes(summary.detections)
    edges = build_edges(nodes, summary)
    return ArchitectureGraph(
        nodes=tuple(sorted(nodes, key=lambda node: node.id)),
        edges=tuple(sorted(set(edges), key=edge_sort_key)),
        warnings=tuple(warnings),
    )


def build_nodes(detections: list[Detection]) -> tuple[list[Node], list[str]]:
    nodes: list[Node] = []
    warnings: list[str] = []
    id_counts: dict[str, int] = defaultdict(int)

    for detection in sorted(detections, key=detection_sort_key):
        base_id = stable_node_id(detection)
        id_counts[base_id] += 1
        node_id = base_id
        if id_counts[base_id] > 1:
            node_id = f"{base_id}_{id_counts[base_id]}"
            warnings.append(
                f'Resolved node ID collision for "{base_id}" as "{node_id}".'
            )

        nodes.append(
            Node(
                id=node_id,
                label=detection.name,
                kind=detection.kind,
                source_files=source_files(detection.evidence),
            )
        )

    return nodes, warnings


def build_edges(nodes: list[Node], summary: SummaryWithDetections) -> list[Edge]:
    edges: list[Edge] = []
    nodes_by_kind = group_nodes_by_kind(nodes)
    target_nodes = (
        nodes_by_kind["Executable Target"]
        + nodes_by_kind["Library Target"]
        + nodes_by_kind["Build Target"]
    )

    add_edges_between(edges, nodes_by_kind["API"], nodes_by_kind["Database"])
    add_edges_between(edges, nodes_by_kind["API"], nodes_by_kind["Cache"])
    add_edges_between(
        edges,
        nodes_by_kind["Tests"],
        nodes_by_kind["API"]
        + nodes_by_kind["Database"]
        + nodes_by_kind["Cache"]
        + nodes_by_kind["C/C++ Project"],
    )
    add_edges_between(
        edges,
        nodes_by_kind["C/C++ Project"],
        nodes_by_kind["C/C++ Module"],
    )
    add_edges_between(
        edges,
        nodes_by_kind["C/C++ Project"],
        nodes_by_kind["Executable Target"] + nodes_by_kind["Library Target"],
    )
    add_edges_for_shared_evidence(
        edges,
        target_nodes,
        nodes_by_kind["C/C++ Module"],
    )
    add_include_derived_module_edges(
        edges,
        nodes_by_kind["C/C++ Module"],
        c_cpp_resolved_includes(summary),
    )
    add_edges_for_shared_evidence(
        edges,
        nodes_by_kind["C/C++ Module"],
        nodes_by_kind["C/C++ Systems Pattern"],
        label="uses",
    )
    add_target_system_edges(
        edges,
        target_nodes,
        nodes_by_kind["C/C++ Module"],
        nodes_by_kind["C/C++ Systems Pattern"],
    )

    return edges


def add_edges_between(edges: list[Edge], sources: list[Node], targets: list[Node]) -> None:
    for source in sorted(sources, key=lambda node: node.id):
        for target in sorted(targets, key=lambda node: node.id):
            if source.id != target.id:
                edges.append(Edge(source=source.id, target=target.id))


def add_edges_for_shared_evidence(
    edges: list[Edge],
    sources: list[Node],
    targets: list[Node],
    label: str | None = None,
) -> None:
    for source in sorted(sources, key=lambda node: node.id):
        source_files = set(source.source_files)
        if not source_files:
            continue
        for target in sorted(targets, key=lambda node: node.id):
            if source.id != target.id and source_files & set(target.source_files):
                edges.append(Edge(source=source.id, target=target.id, label=label))


def add_include_derived_module_edges(
    edges: list[Edge],
    modules: list[Node],
    resolved_includes,
) -> None:
    modules_by_file = nodes_by_source_file(modules)

    for include in sorted(
        resolved_includes,
        key=lambda item: (
            item.source.as_posix(),
            item.included_path,
            "" if item.resolved_path is None else item.resolved_path.as_posix(),
            item.status,
        ),
    ):
        if include.status != "resolved" or include.resolved_path is None:
            continue

        source_modules = modules_by_file.get(include.source.as_posix(), [])
        target_modules = modules_by_file.get(include.resolved_path.as_posix(), [])
        for source in sorted(source_modules, key=lambda node: node.id):
            for target in sorted(target_modules, key=lambda node: node.id):
                if source.id != target.id:
                    edges.append(
                        Edge(
                            source=source.id,
                            target=target.id,
                            label="includes",
                        )
                    )


def add_target_system_edges(
    edges: list[Edge],
    targets: list[Node],
    modules: list[Node],
    systems: list[Node],
) -> None:
    for target in sorted(targets, key=lambda node: node.id):
        target_files = set(target.source_files)
        if not target_files:
            continue

        owned_module_files = {
            source_file
            for module in modules
            if target_files & set(module.source_files)
            for source_file in module.source_files
        }
        if not owned_module_files:
            continue

        for system in sorted(systems, key=lambda node: node.id):
            if target.id != system.id and owned_module_files & set(system.source_files):
                edges.append(
                    Edge(
                        source=target.id,
                        target=system.id,
                        label="uses",
                    )
                )


def nodes_by_source_file(nodes: list[Node]) -> defaultdict[str, list[Node]]:
    nodes_by_file: defaultdict[str, list[Node]] = defaultdict(list)
    for node in sorted(nodes, key=lambda item: item.id):
        for source_file in node.source_files:
            nodes_by_file[source_file].append(node)
    return nodes_by_file


def c_cpp_resolved_includes(summary: SummaryWithDetections):
    return getattr(summary, "c_cpp_resolved_includes", ())


def group_nodes_by_kind(nodes: list[Node]) -> defaultdict[str, list[Node]]:
    nodes_by_kind: defaultdict[str, list[Node]] = defaultdict(list)
    for node in nodes:
        nodes_by_kind[node.kind].append(node)
    return nodes_by_kind


def stable_node_id(detection: Detection) -> str:
    return sanitize_node_id(f"{detection.kind}_{detection.name}")


def sanitize_node_id(value: str) -> str:
    node_id = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    node_id = re.sub(r"_+", "_", node_id)
    if not node_id:
        return "node"
    if node_id[0].isdigit():
        return f"n_{node_id}"
    return node_id


def source_files(evidence: tuple[Path, ...]) -> tuple[str, ...]:
    return tuple(sorted(path.as_posix() for path in evidence))


def detection_sort_key(detection: Detection) -> tuple[str, str, tuple[str, ...]]:
    return detection.kind, detection.name, source_files(detection.evidence)


def edge_sort_key(edge: Edge) -> tuple[str, str, str, float]:
    return edge.source, edge.target, edge.label or "", edge.confidence
