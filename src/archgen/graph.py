from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    kind: str
    source_files: tuple[str, ...]


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class ArchitectureGraph:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    warnings: tuple[str, ...] = ()
