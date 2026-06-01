from __future__ import annotations

from pathlib import Path
import re

from archgen.detectors.python_ast import imported_module_roots, parse_python_file
from archgen.detection import Detection


TEST_FRAMEWORK_IMPORTS = {"pytest", "unittest"}
DEPENDENCY_FILE_NAMES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.cfg",
}
TEST_DEPENDENCY_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])(?:pytest|unittest)(?![A-Za-z0-9_-])")


def detect_test_components(root: Path, files: list[Path], dirs: list[Path]) -> list[Detection]:
    evidence: set[Path] = set()

    for relative_dir in dirs:
        if relative_dir.name == "tests":
            evidence.add(relative_dir)

    for relative_path in files:
        if is_test_file(relative_path):
            evidence.add(relative_path)

        if relative_path.suffix.lower() == ".py":
            if has_python_test_framework_evidence(root / relative_path):
                evidence.add(relative_path)
        elif relative_path.name in DEPENDENCY_FILE_NAMES:
            if has_dependency_test_framework_evidence(root / relative_path):
                evidence.add(relative_path)

    if not evidence:
        return []

    return [
        Detection(
            kind="Tests",
            name="Test Suite",
            evidence=tuple(sorted(evidence)),
            confidence=0.75,
        )
    ]


def is_test_file(path: Path) -> bool:
    return path.suffix.lower() == ".py" and (
        path.name.startswith("test_") or path.name.endswith("_test.py")
    )


def has_python_test_framework_evidence(path: Path) -> bool:
    tree = parse_python_file(path)
    if tree is None:
        return False
    return bool(imported_module_roots(tree) & TEST_FRAMEWORK_IMPORTS)


def has_dependency_test_framework_evidence(path: Path) -> bool:
    content = read_text(path)
    if content is None:
        return False
    return TEST_DEPENDENCY_PATTERN.search(content.lower()) is not None


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
