from __future__ import annotations

from pathlib import Path

from archgen.detectors.python_ast import call_name, iter_calls, parse_python_file
from archgen.detection import Detection


API_CALLS = {
    "FastAPI": "FastAPI API",
    "Flask": "Flask API",
    "APIRouter": "API Router",
    "app.get": "Python API routes",
    "app.post": "Python API routes",
    "router.get": "Python API routes",
    "router.post": "Python API routes",
}


def detect_python_api_components(root: Path, files: list[Path]) -> list[Detection]:
    evidence_by_name: dict[str, set[Path]] = {}

    for relative_path in files:
        if relative_path.suffix.lower() != ".py":
            continue
        tree = parse_python_file(root / relative_path)
        if tree is None:
            continue
        for call in iter_calls(tree):
            name = API_CALLS.get(call_name(call.func))
            if name is not None:
                evidence_by_name.setdefault(name, set()).add(relative_path)

    return [
        Detection(
            kind="API",
            name=name,
            evidence=tuple(sorted(evidence)),
            confidence=0.8,
        )
        for name, evidence in evidence_by_name.items()
        if evidence
    ]
