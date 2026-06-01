from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re

from archgen.detectors.python_ast import imported_module_roots, parse_python_file
from archgen.detection import Detection


POSTGRESQL_IMPORTS = {"psycopg", "asyncpg"}
SQLITE_IMPORTS = {"sqlite3"}
DATABASE_IMPORTS = {"sqlalchemy"} | POSTGRESQL_IMPORTS | SQLITE_IMPORTS
DEPENDENCY_FILE_NAMES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.cfg",
}
DEPENDENCY_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])(?:sqlalchemy|psycopg|asyncpg|sqlite3)(?![A-Za-z0-9_-])")


def detect_database_components(
    root: Path,
    files: list[Path],
    dirs: list[Path],
) -> list[Detection]:
    evidence_by_name: dict[str, set[Path]] = defaultdict(set)

    for relative_path in files:
        lower_name = relative_path.name.lower()
        if lower_name == "models.py":
            evidence_by_name["Database"].add(relative_path)

        if relative_path.suffix.lower() == ".py":
            add_python_database_evidence(
                root=root,
                relative_path=relative_path,
                evidence_by_name=evidence_by_name,
            )
        elif relative_path.name in DEPENDENCY_FILE_NAMES:
            add_dependency_database_evidence(
                root=root,
                relative_path=relative_path,
                evidence_by_name=evidence_by_name,
            )

    for relative_dir in dirs:
        dir_parts = {part.lower() for part in relative_dir.parts}
        if "migrations" in dir_parts or "alembic" in dir_parts:
            evidence_by_name["Database"].add(relative_dir)

    return [
        Detection(
            kind="Database",
            name=name,
            evidence=tuple(sorted(evidence)),
            confidence=0.75,
        )
        for name, evidence in sorted(evidence_by_name.items())
        if evidence
    ]


def add_python_database_evidence(
    root: Path,
    relative_path: Path,
    evidence_by_name: dict[str, set[Path]],
) -> None:
    tree = parse_python_file(root / relative_path)
    if tree is None:
        return

    imports = imported_module_roots(tree)
    if imports & DATABASE_IMPORTS:
        evidence_by_name["Database"].add(relative_path)
    if imports & POSTGRESQL_IMPORTS:
        evidence_by_name["PostgreSQL"].add(relative_path)
    if imports & SQLITE_IMPORTS:
        evidence_by_name["SQLite"].add(relative_path)


def add_dependency_database_evidence(
    root: Path,
    relative_path: Path,
    evidence_by_name: dict[str, set[Path]],
) -> None:
    content = read_text(root / relative_path)
    if content is None:
        return
    lower_content = content.lower()
    if DEPENDENCY_PATTERN.search(lower_content):
        evidence_by_name["Database"].add(relative_path)
    if "psycopg" in lower_content or "asyncpg" in lower_content:
        evidence_by_name["PostgreSQL"].add(relative_path)
    if "sqlite3" in lower_content:
        evidence_by_name["SQLite"].add(relative_path)


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
