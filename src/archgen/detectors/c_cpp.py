from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from archgen.detection import Detection


C_EXTENSIONS = {".c"}
CXX_EXTENSIONS = {".cc", ".cpp", ".cxx"}


def detect_c_cpp_components(
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
    c_cpp_project_shape,
    c_cpp_build,
    c_cpp_systems_patterns,
) -> list[Detection]:
    detections: list[Detection] = []

    project_detection = detect_project_component(
        c_cpp_sources=c_cpp_sources,
        c_cpp_headers=c_cpp_headers,
        c_cpp_project_shape=c_cpp_project_shape,
        c_cpp_build=c_cpp_build,
    )
    if project_detection is not None:
        detections.append(project_detection)

    detections.extend(detect_source_header_modules(c_cpp_sources, c_cpp_headers))
    detections.extend(detect_build_components(c_cpp_build))
    detections.extend(detect_systems_components(c_cpp_systems_patterns))

    return detections


def detect_project_component(
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
    c_cpp_project_shape,
    c_cpp_build,
) -> Detection | None:
    if not c_cpp_project_shape.looks_like_project:
        return None

    c_sources = [path for path in c_cpp_sources if path.suffix.lower() in C_EXTENSIONS]
    cxx_sources = [
        path for path in c_cpp_sources if path.suffix.lower() in CXX_EXTENSIONS
    ]
    evidence = tuple(
        sorted(
            c_cpp_sources
            + c_cpp_headers
            + c_cpp_project_shape.build_files
            + c_cpp_project_shape.conventional_dirs
        )
    )
    has_executable_evidence = bool(c_cpp_build.cmake_executable_targets) or any(
        path.stem == "main" for path in c_cpp_sources
    )
    has_library_evidence = bool(c_cpp_build.cmake_library_targets)

    if c_sources and cxx_sources:
        name = "Mixed C/C++ project"
    elif cxx_sources and has_executable_evidence:
        name = "C++ application"
    elif c_sources and has_executable_evidence:
        name = "C application"
    elif has_library_evidence or (c_cpp_headers and not c_cpp_sources):
        name = "Library-like C/C++ project"
    else:
        name = "Generic C/C++ project"

    return Detection(
        kind="C/C++ Project",
        name=name,
        evidence=evidence,
        confidence=0.8,
    )


def detect_source_header_modules(
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
) -> list[Detection]:
    sources_by_stem = group_by_stem(c_cpp_sources)
    headers_by_stem = group_by_stem(c_cpp_headers)
    detections: list[Detection] = []

    for stem in sorted(sources_by_stem.keys() & headers_by_stem.keys()):
        evidence = tuple(sorted(sources_by_stem[stem] + headers_by_stem[stem]))
        detections.append(
            Detection(
                kind="C/C++ Module",
                name=f"{stem} module",
                evidence=evidence,
                confidence=0.85,
            )
        )

    return detections


def group_by_stem(paths: list[Path]) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in paths:
        grouped[path.stem].append(path)
    return grouped


def detect_build_components(c_cpp_build) -> list[Detection]:
    detections: list[Detection] = []

    for target in c_cpp_build.cmake_executable_targets:
        detections.append(
            Detection(
                kind="Executable Target",
                name=target.name,
                evidence=(target.source,),
                confidence=0.9,
            )
        )

    for target in c_cpp_build.make_targets:
        detections.append(
            Detection(
                kind="Build Target",
                name=target.name,
                evidence=(target.source,),
                confidence=0.5,
            )
        )

    return detections


def detect_systems_components(c_cpp_systems_patterns) -> list[Detection]:
    evidence_by_category: dict[str, set[Path]] = defaultdict(set)
    for match in c_cpp_systems_patterns:
        evidence_by_category[match.category].add(match.source)

    return [
        Detection(
            kind="C/C++ Systems Pattern",
            name=category,
            evidence=tuple(sorted(paths)),
            confidence=0.65,
        )
        for category, paths in sorted(evidence_by_category.items())
    ]
