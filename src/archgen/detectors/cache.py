from __future__ import annotations

from pathlib import Path
import re

from archgen.detectors.python_ast import (
    call_name,
    imported_module_roots,
    iter_calls,
    parse_python_file,
)
from archgen.detection import Detection


REDIS_IMPORTS = {"redis", "aioredis"}
DEPENDENCY_FILE_NAMES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.cfg",
}
REDIS_DEPENDENCY_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])(?:redis|aioredis)(?![A-Za-z0-9_-])")


def detect_cache_components(root: Path, files: list[Path]) -> list[Detection]:
    evidence: set[Path] = set()

    for relative_path in files:
        if relative_path.suffix.lower() == ".py":
            if has_python_redis_evidence(root / relative_path):
                evidence.add(relative_path)
        elif relative_path.name in DEPENDENCY_FILE_NAMES:
            if has_dependency_redis_evidence(root / relative_path):
                evidence.add(relative_path)

    if not evidence:
        return []

    return [
        Detection(
            kind="Cache",
            name="Redis Cache",
            evidence=tuple(sorted(evidence)),
            confidence=0.8,
        )
    ]


def has_python_redis_evidence(path: Path) -> bool:
    tree = parse_python_file(path)
    if tree is None:
        return False

    if imported_module_roots(tree) & REDIS_IMPORTS:
        return True

    return any(call_name(call.func) == "Redis.from_url" for call in iter_calls(tree))


def has_dependency_redis_evidence(path: Path) -> bool:
    content = read_text(path)
    if content is None:
        return False
    return REDIS_DEPENDENCY_PATTERN.search(content.lower()) is not None


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
