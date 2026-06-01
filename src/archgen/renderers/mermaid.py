from __future__ import annotations

import re

from archgen.graph import ArchitectureGraph, Edge, Node


CYLINDER_NODE_KINDS = {"Cache", "Database"}


def render_mermaid(graph: ArchitectureGraph) -> str:
    mermaid_ids = mermaid_node_ids(graph.nodes)
    lines = ["flowchart TD"]

    for node in sorted(graph.nodes, key=lambda item: mermaid_ids[item.id]):
        lines.append(f"    {render_node(node, mermaid_ids[node.id])}")

    for edge in sorted(graph.edges, key=edge_sort_key):
        lines.append(f"    {render_edge(edge, mermaid_ids)}")

    return "\n".join(lines) + "\n"


def render_node(node: Node, mermaid_id: str) -> str:
    label = escape_label(node.label)
    if node.kind in CYLINDER_NODE_KINDS:
        return f'{mermaid_id}[("{label}")]'
    return f'{mermaid_id}["{label}"]'


def render_edge(edge: Edge, mermaid_ids: dict[str, str]) -> str:
    source = mermaid_ids.get(edge.source, sanitize_mermaid_id(edge.source))
    target = mermaid_ids.get(edge.target, sanitize_mermaid_id(edge.target))
    if edge.label is not None:
        return f"{source} -->|{escape_label(edge.label)}| {target}"
    return f"{source} --> {target}"


def mermaid_node_ids(nodes: tuple[Node, ...]) -> dict[str, str]:
    ids: dict[str, str] = {}
    id_counts: dict[str, int] = {}

    for node in sorted(nodes, key=lambda item: item.id):
        base_id = sanitize_mermaid_id(node.id)
        id_counts[base_id] = id_counts.get(base_id, 0) + 1
        if id_counts[base_id] == 1:
            ids[node.id] = base_id
        else:
            ids[node.id] = f"{base_id}_{id_counts[base_id]}"

    return ids


def sanitize_mermaid_id(value: str) -> str:
    mermaid_id = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    mermaid_id = re.sub(r"_+", "_", mermaid_id)
    if not mermaid_id:
        return "node"
    if mermaid_id[0].isdigit():
        return f"n_{mermaid_id}"
    return mermaid_id


def escape_label(value: str) -> str:
    return value.replace('"', r"\"")


def edge_sort_key(edge: Edge) -> tuple[str, str, str, float]:
    return edge.source, edge.target, edge.label or "", edge.confidence
