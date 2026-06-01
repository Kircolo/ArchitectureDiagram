from __future__ import annotations

from pathlib import Path

from archgen.detection import Detection


COMPOSE_FILE_NAMES = {
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
}


def detect_docker_components(files: list[Path]) -> list[Detection]:
    dockerfiles = [path for path in files if path.name == "Dockerfile"]
    compose_files = [path for path in files if path.name in COMPOSE_FILE_NAMES]
    detections: list[Detection] = []

    if dockerfiles:
        detections.append(
            Detection(
                kind="Docker",
                name="Docker",
                evidence=tuple(sorted(dockerfiles)),
                confidence=0.9,
            )
        )
    if compose_files:
        detections.append(
            Detection(
                kind="Docker",
                name="Docker Compose",
                evidence=tuple(sorted(compose_files)),
                confidence=0.9,
            )
        )

    return detections
