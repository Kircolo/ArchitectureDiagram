from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from archgen.detection import Detection


C_EXTENSIONS = {".c"}
CXX_EXTENSIONS = {".cc", ".cpp", ".cxx"}
C_CPP_MODULE_ROOTS = {"include", "lib", "src"}
SHARED_UTILITY_STEMS = {
    "audit",
    "common",
    "error",
    "errors",
    "log",
    "logger",
    "util",
    "utils",
}
SOURCE_ONLY_EXCLUDED_STEMS = {"main"}
TEST_PATH_PARTS = {"test", "tests"}
MODULE_TOKEN_LABELS = {
    "api": "API",
    "cli": "CLI",
    "http": "HTTP",
    "io": "I/O",
    "json": "JSON",
    "ssl": "SSL",
    "tcp": "TCP",
    "tls": "TLS",
    "udp": "UDP",
    "xml": "XML",
}
SOCKET_LISTENER_PATTERNS = {"accept", "bind", "listen"}
CLIENT_SOCKET_TOKENS = {"client", "connector", "upstream"}
WORKER_THREAD_TOKENS = {"pool", "thread", "threads", "threadpool", "worker", "workers"}
QUEUE_TOKENS = {"dispatcher", "queue", "queues"}
QUEUE_API_PATTERNS = {"dequeue", "enqueue"}
FILE_STORAGE_TOKENS = {
    "audit",
    "disk",
    "file",
    "files",
    "fs",
    "log",
    "logger",
    "persistence",
    "persist",
    "storage",
    "store",
}
PROCESS_MANAGER_PATTERNS = {"exec", "fork", "pipe"}
ENCODER_TOKENS = {"compress", "compressor", "encode", "encoder"}
DECODER_TOKENS = {"decode", "decoder", "decompress", "decompressor"}
BIT_IO_TOKENS = {"bitio", "bitreader", "bitstream", "bitwriter"}
BIT_IO_PART_TOKENS = {"io", "reader", "stream", "writer"}


@dataclass(frozen=True)
class ModuleCandidate:
    name: str
    evidence: tuple[Path, ...]
    confidence: float


@dataclass(frozen=True)
class SystemComponentCandidate:
    name: str
    evidence: tuple[Path, ...]
    confidence: float


def detect_c_cpp_components(
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
    c_cpp_project_shape,
    c_cpp_build,
    c_cpp_systems_patterns,
    c_cpp_cli_binary_evidence=None,
) -> list[Detection]:
    detections: list[Detection] = []
    if c_cpp_cli_binary_evidence is None:
        c_cpp_cli_binary_evidence = []

    project_detection = detect_project_component(
        c_cpp_sources=c_cpp_sources,
        c_cpp_headers=c_cpp_headers,
        c_cpp_project_shape=c_cpp_project_shape,
        c_cpp_build=c_cpp_build,
    )
    if project_detection is not None:
        detections.append(project_detection)

    detections.extend(
        detect_c_cpp_modules(
            c_cpp_sources=c_cpp_sources,
            c_cpp_headers=c_cpp_headers,
            c_cpp_systems_patterns=c_cpp_systems_patterns,
        )
    )
    detections.extend(detect_build_components(c_cpp_build))
    detections.extend(
        detect_cli_binary_components(
            c_cpp_cli_binary_evidence=c_cpp_cli_binary_evidence,
            c_cpp_build=c_cpp_build,
        )
    )
    detections.extend(
        detect_systems_components(
            c_cpp_sources=c_cpp_sources,
            c_cpp_headers=c_cpp_headers,
            c_cpp_systems_patterns=c_cpp_systems_patterns,
        )
    )

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


def detect_c_cpp_modules(
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
    c_cpp_systems_patterns,
) -> list[Detection]:
    all_paths = sorted(c_cpp_sources + c_cpp_headers)
    folder_candidates = detect_folder_modules(all_paths)
    absorbed_paths = {
        evidence_path
        for candidate in folder_candidates
        for evidence_path in candidate.evidence
    }
    sources_by_key = group_by_module_key(c_cpp_sources)
    headers_by_key = group_by_module_key(c_cpp_headers)
    source_keys = set(sources_by_key)
    header_keys = set(headers_by_key)
    paired_keys = source_keys & header_keys
    systems_sources = {match.source for match in c_cpp_systems_patterns}

    candidates = list(folder_candidates)
    candidates.extend(
        detect_paired_modules(
            sources_by_key=sources_by_key,
            headers_by_key=headers_by_key,
            absorbed_paths=absorbed_paths,
        )
    )
    candidates.extend(
        detect_source_only_modules(
            c_cpp_sources=c_cpp_sources,
            paired_keys=paired_keys,
            systems_sources=systems_sources,
            absorbed_paths=absorbed_paths,
        )
    )
    candidates.extend(
        detect_header_only_modules(
            c_cpp_headers=c_cpp_headers,
            source_keys=source_keys,
            absorbed_paths=absorbed_paths,
        )
    )

    return module_detections(candidates)


def detect_source_header_modules(
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
) -> list[Detection]:
    return detect_c_cpp_modules(c_cpp_sources, c_cpp_headers, [])


def detect_folder_modules(paths: list[Path]) -> list[ModuleCandidate]:
    paths_by_folder: dict[Path, set[Path]] = defaultdict(set)
    stems_by_folder: dict[Path, set[str]] = defaultdict(set)

    for path in sorted(paths):
        folder = module_folder(path)
        if folder is None:
            continue
        paths_by_folder[folder].add(path)
        stems_by_folder[folder].add(path.stem)

    return [
        ModuleCandidate(
            name=module_label(folder),
            evidence=tuple(sorted(paths_by_folder[folder])),
            confidence=0.8,
        )
        for folder in sorted(paths_by_folder)
        if len(stems_by_folder[folder]) >= 2
    ]


def detect_paired_modules(
    sources_by_key: dict[Path, list[Path]],
    headers_by_key: dict[Path, list[Path]],
    absorbed_paths: set[Path],
) -> list[ModuleCandidate]:
    candidates: list[ModuleCandidate] = []
    for key in sorted(set(sources_by_key) & set(headers_by_key)):
        evidence = tuple(sorted(sources_by_key[key] + headers_by_key[key]))
        if set(evidence) <= absorbed_paths:
            continue
        candidates.append(
            ModuleCandidate(
                name=module_label(key),
                evidence=evidence,
                confidence=0.85,
            )
        )

    return candidates


def detect_source_only_modules(
    c_cpp_sources: list[Path],
    paired_keys: set[Path],
    systems_sources: set[Path],
    absorbed_paths: set[Path],
) -> list[ModuleCandidate]:
    candidates: list[ModuleCandidate] = []
    for source in sorted(c_cpp_sources):
        key = module_key(source)
        if (
            source in absorbed_paths
            or key in paired_keys
            or is_test_path(source)
            or source.stem.lower() in SOURCE_ONLY_EXCLUDED_STEMS
        ):
            continue

        has_source_only_evidence = (
            source in systems_sources or source.stem.lower() in SHARED_UTILITY_STEMS
        )
        if not has_source_only_evidence:
            continue

        candidates.append(
            ModuleCandidate(
                name=module_label(key),
                evidence=(source,),
                confidence=0.7,
            )
        )

    return candidates


def detect_header_only_modules(
    c_cpp_headers: list[Path],
    source_keys: set[Path],
    absorbed_paths: set[Path],
) -> list[ModuleCandidate]:
    candidates: list[ModuleCandidate] = []
    for header in sorted(c_cpp_headers):
        key = module_key(header)
        if header in absorbed_paths or key in source_keys or not is_public_header(header):
            continue

        candidates.append(
            ModuleCandidate(
                name=module_label(key),
                evidence=(header,),
                confidence=0.6,
            )
        )

    return candidates


def module_detections(candidates: list[ModuleCandidate]) -> list[Detection]:
    candidates_by_key: dict[tuple[str, tuple[Path, ...]], ModuleCandidate] = {}
    for candidate in candidates:
        key = (candidate.name, candidate.evidence)
        existing = candidates_by_key.get(key)
        if existing is None or candidate.confidence > existing.confidence:
            candidates_by_key[key] = candidate

    return [
        Detection(
            kind="C/C++ Module",
            name=candidate.name,
            evidence=candidate.evidence,
            confidence=candidate.confidence,
        )
        for candidate in sorted(candidates_by_key.values(), key=module_candidate_sort_key)
    ]


def group_by_module_key(paths: list[Path]) -> dict[Path, list[Path]]:
    grouped: dict[Path, list[Path]] = defaultdict(list)
    for path in paths:
        grouped[module_key(path)].append(path)
    return {
        key: sorted(grouped_paths)
        for key, grouped_paths in sorted(grouped.items())
    }


def module_key(path: Path) -> Path:
    return strip_module_root(path).with_suffix("")


def module_folder(path: Path) -> Path | None:
    stripped = strip_module_root(path)
    if len(stripped.parts) <= 1:
        return None
    return Path(*stripped.parts[:-1])


def strip_module_root(path: Path) -> Path:
    parts = path.parts
    if len(parts) > 1 and parts[0] in C_CPP_MODULE_ROOTS:
        return Path(*parts[1:])
    return path


def module_label(key: Path) -> str:
    label_parts: list[str] = []
    for part in key.parts:
        label_parts.extend(module_label_token(token) for token in split_module_part(part))
    return f"{' '.join(label_parts)} module"


def split_module_part(part: str) -> list[str]:
    return [
        token
        for underscore_part in part.split("_")
        for token in underscore_part.split("-")
        if token
    ]


def module_label_token(token: str) -> str:
    return MODULE_TOKEN_LABELS.get(token.lower(), token.lower())


def is_test_path(path: Path) -> bool:
    return bool(set(path.parts) & TEST_PATH_PARTS)


def is_public_header(path: Path) -> bool:
    return bool(path.parts) and path.parts[0] == "include"


def module_candidate_sort_key(
    candidate: ModuleCandidate,
) -> tuple[str, tuple[Path, ...], float]:
    return candidate.name, candidate.evidence, candidate.confidence


def detect_build_components(c_cpp_build) -> list[Detection]:
    detections: list[Detection] = []

    for target in c_cpp_build.cmake_executable_targets:
        detections.append(
            Detection(
                kind="Executable Target",
                name=target.name,
                evidence=target_evidence(target),
                confidence=0.9,
            )
        )

    for target in c_cpp_build.cmake_library_targets:
        detections.append(
            Detection(
                kind="Library Target",
                name=target.name,
                evidence=target_evidence(target),
                confidence=0.85,
            )
        )

    for target in c_cpp_build.make_targets:
        detections.append(
            Detection(
                kind="Build Target",
                name=target.name,
                evidence=target_evidence(target),
                confidence=0.65 if target.source_files else 0.5,
            )
        )

    return detections


def target_evidence(target) -> tuple[Path, ...]:
    return tuple(sorted((target.source, *target.source_files)))


def detect_cli_binary_components(
    c_cpp_cli_binary_evidence,
    c_cpp_build,
) -> list[Detection]:
    evidence_paths: set[Path] = set()
    has_option_parser = False

    for item in c_cpp_cli_binary_evidence:
        signals = set(item.signals)
        has_main = "main" in signals
        has_cli_args = "argc/argv" in signals
        has_cli_options = bool(signals & {"getopt", "--help"})

        if has_main and (has_cli_args or has_cli_options):
            evidence_paths.add(item.source)
            has_option_parser = has_option_parser or has_cli_options
        elif has_cli_options and c_cpp_build.cmake_executable_targets:
            evidence_paths.add(item.source)
            has_option_parser = True

    if not evidence_paths:
        return []

    evidence_paths.update(target.source for target in c_cpp_build.cmake_executable_targets)
    confidence = 0.8 if has_option_parser else 0.75

    return [
        Detection(
            kind="Executable Target",
            name="CLI Binary",
            evidence=tuple(sorted(evidence_paths)),
            confidence=confidence,
        )
    ]


def detect_systems_components(
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
    c_cpp_systems_patterns,
) -> list[Detection]:
    evidence_by_key = module_evidence_by_key(
        c_cpp_sources=c_cpp_sources,
        c_cpp_headers=c_cpp_headers,
    )
    patterns_by_key = systems_patterns_by_key(c_cpp_systems_patterns)
    sources_by_key_category = systems_sources_by_key_category(c_cpp_systems_patterns)
    consumed_sources_by_category: defaultdict[str, set[Path]] = defaultdict(set)
    candidates: list[SystemComponentCandidate] = []

    for key in sorted(evidence_by_key):
        category_patterns = patterns_by_key.get(key, {})
        tokens = system_component_tokens(key)
        socket_patterns = category_patterns.get("Sockets", set())
        queue_patterns = category_patterns.get("Queues", set())
        thread_patterns = category_patterns.get("Threads", set())
        sync_patterns = category_patterns.get("Synchronization", set())
        file_patterns = category_patterns.get("File I/O", set())
        memory_process_patterns = category_patterns.get("Memory/process", set())

        if is_socket_listener(socket_patterns):
            add_system_candidate(
                candidates=candidates,
                consumed_sources_by_category=consumed_sources_by_category,
                sources_by_key_category=sources_by_key_category,
                evidence=tuple(evidence_by_key[key]),
                key=key,
                name="Socket Listener",
                confidence=0.85,
                consumed_categories=("Sockets",),
            )

        if is_client_socket(socket_patterns, tokens):
            confidence = 0.8 if "socket" in socket_patterns else 0.7
            add_system_candidate(
                candidates=candidates,
                consumed_sources_by_category=consumed_sources_by_category,
                sources_by_key_category=sources_by_key_category,
                evidence=tuple(evidence_by_key[key]),
                key=key,
                name="Client Socket",
                confidence=confidence,
                consumed_categories=("Sockets",),
            )

        if is_worker_thread_pool(thread_patterns, queue_patterns, tokens):
            add_system_candidate(
                candidates=candidates,
                consumed_sources_by_category=consumed_sources_by_category,
                sources_by_key_category=sources_by_key_category,
                evidence=tuple(evidence_by_key[key]),
                key=key,
                name="Worker Thread Pool",
                confidence=0.8,
                consumed_categories=("Threads",),
            )

        if is_shared_queue(queue_patterns, tokens):
            confidence = shared_queue_confidence(queue_patterns)
            add_system_candidate(
                candidates=candidates,
                consumed_sources_by_category=consumed_sources_by_category,
                sources_by_key_category=sources_by_key_category,
                evidence=tuple(evidence_by_key[key]),
                key=key,
                name="Shared Queue",
                confidence=confidence,
                consumed_categories=("Queues",),
            )

        if sync_patterns:
            add_system_candidate(
                candidates=candidates,
                consumed_sources_by_category=consumed_sources_by_category,
                sources_by_key_category=sources_by_key_category,
                evidence=tuple(evidence_by_key[key]),
                key=key,
                name="Synchronization Layer",
                confidence=0.75,
                consumed_categories=("Synchronization",),
            )

        if file_patterns and FILE_STORAGE_TOKENS & tokens:
            add_system_candidate(
                candidates=candidates,
                consumed_sources_by_category=consumed_sources_by_category,
                sources_by_key_category=sources_by_key_category,
                evidence=tuple(evidence_by_key[key]),
                key=key,
                name="File Storage",
                confidence=0.75,
                consumed_categories=("File I/O",),
            )

        if memory_process_patterns & PROCESS_MANAGER_PATTERNS:
            add_system_candidate(
                candidates=candidates,
                consumed_sources_by_category=consumed_sources_by_category,
                sources_by_key_category=sources_by_key_category,
                evidence=tuple(evidence_by_key[key]),
                key=key,
                name="Process Manager",
                confidence=0.75,
                consumed_categories=("Memory/process",),
            )

        if ENCODER_TOKENS & tokens:
            candidates.append(
                SystemComponentCandidate(
                    name="Encoder",
                    evidence=tuple(evidence_by_key[key]),
                    confidence=0.65,
                )
            )

        if DECODER_TOKENS & tokens:
            candidates.append(
                SystemComponentCandidate(
                    name="Decoder",
                    evidence=tuple(evidence_by_key[key]),
                    confidence=0.65,
                )
            )

        if is_bit_io(tokens):
            candidates.append(
                SystemComponentCandidate(
                    name="Bit I/O",
                    evidence=tuple(evidence_by_key[key]),
                    confidence=0.65,
                )
            )

    detections = system_component_detections(candidates)
    detections.extend(
        broad_systems_fallback_detections(
            c_cpp_systems_patterns=c_cpp_systems_patterns,
            consumed_sources_by_category=consumed_sources_by_category,
        )
    )
    return sorted(detections, key=lambda item: (item.name, item.evidence))


def module_evidence_by_key(
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
) -> dict[Path, tuple[Path, ...]]:
    grouped: dict[Path, set[Path]] = defaultdict(set)
    for path in sorted(c_cpp_sources + c_cpp_headers):
        grouped[module_key(path)].add(path)

    return {
        key: tuple(sorted(paths))
        for key, paths in sorted(grouped.items())
    }


def systems_patterns_by_key(c_cpp_systems_patterns) -> dict[Path, dict[str, set[str]]]:
    grouped: defaultdict[Path, defaultdict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for match in c_cpp_systems_patterns:
        grouped[module_key(match.source)][match.category].add(match.pattern)

    return {
        key: {category: set(patterns) for category, patterns in categories.items()}
        for key, categories in sorted(grouped.items())
    }


def systems_sources_by_key_category(
    c_cpp_systems_patterns,
) -> dict[Path, dict[str, set[Path]]]:
    grouped: defaultdict[Path, defaultdict[str, set[Path]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for match in c_cpp_systems_patterns:
        grouped[module_key(match.source)][match.category].add(match.source)

    return {
        key: {category: set(paths) for category, paths in categories.items()}
        for key, categories in sorted(grouped.items())
    }


def add_system_candidate(
    candidates: list[SystemComponentCandidate],
    consumed_sources_by_category: defaultdict[str, set[Path]],
    sources_by_key_category: dict[Path, dict[str, set[Path]]],
    evidence: tuple[Path, ...],
    key: Path,
    name: str,
    confidence: float,
    consumed_categories: tuple[str, ...],
) -> None:
    candidates.append(
        SystemComponentCandidate(
            name=name,
            evidence=evidence,
            confidence=confidence,
        )
    )
    for category in consumed_categories:
        consumed_sources_by_category[category].update(
            sources_by_key_category.get(key, {}).get(category, set())
        )


def system_component_detections(
    candidates: list[SystemComponentCandidate],
) -> list[Detection]:
    evidence_by_name: defaultdict[str, set[Path]] = defaultdict(set)
    confidence_by_name: dict[str, float] = {}

    for candidate in candidates:
        evidence_by_name[candidate.name].update(candidate.evidence)
        confidence_by_name[candidate.name] = max(
            confidence_by_name.get(candidate.name, 0.0),
            candidate.confidence,
        )

    return [
        Detection(
            kind="C/C++ Systems Pattern",
            name=name,
            evidence=tuple(sorted(evidence_by_name[name])),
            confidence=confidence_by_name[name],
        )
        for name in sorted(evidence_by_name)
    ]


def broad_systems_fallback_detections(
    c_cpp_systems_patterns,
    consumed_sources_by_category: defaultdict[str, set[Path]],
) -> list[Detection]:
    evidence_by_category: dict[str, set[Path]] = defaultdict(set)
    for match in c_cpp_systems_patterns:
        if match.source not in consumed_sources_by_category[match.category]:
            evidence_by_category[match.category].add(match.source)

    return [
        Detection(
            kind="C/C++ Systems Pattern",
            name=category,
            evidence=tuple(sorted(paths)),
            confidence=0.65,
        )
        for category, paths in sorted(evidence_by_category.items())
        if paths
    ]


def is_socket_listener(socket_patterns: set[str]) -> bool:
    return "socket" in socket_patterns and bool(socket_patterns & SOCKET_LISTENER_PATTERNS)


def is_client_socket(socket_patterns: set[str], tokens: set[str]) -> bool:
    has_server_socket = bool(socket_patterns & SOCKET_LISTENER_PATTERNS)
    has_client_name = bool(CLIENT_SOCKET_TOKENS & tokens)
    return (
        "connect" in socket_patterns
        and ("socket" in socket_patterns or has_client_name)
        and (not has_server_socket or has_client_name)
    )


def is_worker_thread_pool(
    thread_patterns: set[str],
    queue_patterns: set[str],
    tokens: set[str],
) -> bool:
    return (
        "pthread_create" in thread_patterns
        and (bool(queue_patterns) or bool(WORKER_THREAD_TOKENS & tokens))
    )


def is_shared_queue(queue_patterns: set[str], tokens: set[str]) -> bool:
    return bool(queue_patterns & QUEUE_API_PATTERNS) or bool(QUEUE_TOKENS & tokens)


def shared_queue_confidence(queue_patterns: set[str]) -> float:
    if queue_patterns & QUEUE_API_PATTERNS:
        return 0.8
    if queue_patterns:
        return 0.7
    return 0.65


def is_bit_io(tokens: set[str]) -> bool:
    return bool(BIT_IO_TOKENS & tokens) or (
        "bit" in tokens and bool(BIT_IO_PART_TOKENS & tokens)
    )


def system_component_tokens(key: Path) -> set[str]:
    tokens: set[str] = set()
    for part in key.parts:
        lower_part = part.lower()
        tokens.add(lower_part)
        tokens.update(token.lower() for token in split_module_part(lower_part))
    return tokens
