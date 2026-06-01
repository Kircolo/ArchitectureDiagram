from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SYSTEMS_CATEGORY_ORDER = (
    "Sockets",
    "Threads",
    "Synchronization",
    "Queues",
    "File I/O",
    "Memory/process",
)


@dataclass(frozen=True)
class Detection:
    kind: str
    name: str
    evidence: tuple[Path, ...]
    confidence: float | None = None
