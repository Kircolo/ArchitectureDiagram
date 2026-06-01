from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import os
from pathlib import Path
import re

from archgen.detectors import (
    detect_c_cpp_components,
    detect_cache_components,
    detect_database_components,
    detect_docker_components,
    detect_python_api_components,
    detect_test_components,
)
from archgen.detection import Detection
from archgen.summary import format_summary


IGNORED_DIRS = {
    ".git",
    ".pytest_cache",
    ".tmp",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "target",
    "venv",
    "vendor",
}

LANGUAGE_EXTENSIONS = {
    ".c": "C/C++",
    ".cc": "C/C++",
    ".cpp": "C/C++",
    ".cxx": "C/C++",
    ".h": "C/C++",
    ".hh": "C/C++",
    ".hpp": "C/C++",
    ".hxx": "C/C++",
    ".go": "Go",
    ".java": "Java",
    ".json": "JSON",
    ".md": "Markdown",
    ".py": "Python",
    ".rs": "Rust",
    ".sh": "Shell",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
}

C_CPP_SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx"}
C_CPP_HEADER_EXTENSIONS = {".h", ".hh", ".hpp", ".hxx"}
C_CPP_BUILD_FILE_NAMES = {"CMakeLists.txt", "Makefile", "compile_commands.json"}
CONVENTIONAL_C_CPP_DIRS = {"include", "lib", "src", "tests"}
LOCAL_INCLUDE_PATTERN = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)
CMAKE_TARGET_CALL_PATTERN = re.compile(
    r"add_(executable|library)\s*\((?P<body>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
CMAKE_TOKEN_PATTERN = re.compile(r'"(?:\\.|[^"\\])*"|[^\s()]+')
CMAKE_LIBRARY_TYPE_TOKENS = {"STATIC", "SHARED", "MODULE", "OBJECT", "INTERFACE"}
CMAKE_OPTION_TOKENS = {"EXCLUDE_FROM_ALL", "MACOSX_BUNDLE", "WIN32"}
C_CPP_COMMENT_OR_STRING_PATTERN = re.compile(
    r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'",
    re.MULTILINE | re.DOTALL,
)
C_CPP_MAIN_FUNCTION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])main\s*\((?P<params>[^)]*)\)\s*(?:noexcept\s*)?\{",
    re.MULTILINE | re.DOTALL,
)
C_CPP_OPTION_PARSER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])getopt(?:_long(?:_only)?)?\s*\(",
)
C_CPP_HELP_OPTION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])--help(?![A-Za-z0-9_-])",
)
SYSTEMS_PATTERNS = {
    "Sockets": ["socket", "bind", "listen", "accept", "connect", "send", "recv"],
    "Threads": ["pthread_create", "pthread_join"],
    "Synchronization": ["pthread_mutex", "pthread_cond", "sem_wait", "sem_post"],
    "Queues": ["queue", "enqueue", "dequeue"],
    "File I/O": ["open", "read", "write", "fopen", "fread", "fwrite"],
    "Memory/process": ["malloc", "free", "fork", "exec", "pipe"],
}

NOTABLE_FILE_NAMES = {
    ".env.example",
    "CMakeLists.txt",
    "Dockerfile",
    "Makefile",
    "compile_commands.json",
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
}


@dataclass(frozen=True)
class CCppProjectShape:
    looks_like_project: bool
    build_files: list[Path]
    conventional_dirs: list[Path]


@dataclass(frozen=True)
class CCppLocalInclude:
    source: Path
    included_path: str


@dataclass(frozen=True)
class CCppResolvedInclude:
    source: Path
    included_path: str
    resolved_path: Path | None
    status: str


@dataclass(frozen=True)
class CCppBuildTarget:
    source: Path
    name: str
    kind: str = "build target"
    source_files: tuple[Path, ...] = ()
    object_prerequisites: tuple[str, ...] = ()


@dataclass(frozen=True)
class CCppBuildSummary:
    makefiles: list[Path]
    cmake_files: list[Path]
    compile_commands_files: list[Path]
    make_targets: list[CCppBuildTarget]
    cmake_targets: list[CCppBuildTarget]
    cmake_executable_targets: list[CCppBuildTarget] = field(default_factory=list)
    cmake_library_targets: list[CCppBuildTarget] = field(default_factory=list)


@dataclass(frozen=True)
class CCppSystemsPattern:
    category: str
    source: Path
    pattern: str


@dataclass(frozen=True)
class CCppCliBinaryEvidence:
    source: Path
    signals: tuple[str, ...]


@dataclass(frozen=True)
class RepositorySummary:
    root: Path
    scanned_files: int
    languages: dict[str, int]
    notable_files: list[Path]
    c_cpp_sources: list[Path]
    c_cpp_headers: list[Path]
    c_cpp_project_shape: CCppProjectShape
    c_cpp_local_includes: list[CCppLocalInclude]
    c_cpp_resolved_includes: list[CCppResolvedInclude]
    c_cpp_build: CCppBuildSummary
    c_cpp_systems_patterns: list[CCppSystemsPattern]
    c_cpp_cli_binary_evidence: list[CCppCliBinaryEvidence]
    detections: list[Detection]


def scan_repository(root: Path) -> RepositorySummary:
    root = root.resolve()
    language_counts: Counter[str] = Counter()
    notable_files: list[Path] = []
    c_cpp_sources: list[Path] = []
    c_cpp_headers: list[Path] = []
    c_cpp_build_files: list[Path] = []
    c_cpp_makefiles: list[Path] = []
    c_cpp_cmake_files: list[Path] = []
    c_cpp_compile_commands_files: list[Path] = []
    c_cpp_make_targets: list[CCppBuildTarget] = []
    c_cpp_cmake_targets: list[CCppBuildTarget] = []
    c_cpp_cmake_executable_targets: list[CCppBuildTarget] = []
    c_cpp_cmake_library_targets: list[CCppBuildTarget] = []
    c_cpp_local_includes: list[CCppLocalInclude] = []
    c_cpp_resolved_includes: list[CCppResolvedInclude] = []
    c_cpp_systems_patterns: list[CCppSystemsPattern] = []
    c_cpp_cli_binary_evidence: list[CCppCliBinaryEvidence] = []
    conventional_dirs: set[Path] = set()
    scanned_paths: list[Path] = []
    scanned_dirs: set[Path] = set()
    scanned_files = 0

    for current_root, dirs, files in os.walk(root):
        dirs[:] = sorted(dir_name for dir_name in dirs if dir_name not in IGNORED_DIRS)

        current_path = Path(current_root)
        for dir_name in dirs:
            dir_path = current_path / dir_name
            relative_dir = dir_path.relative_to(root)
            scanned_dirs.add(relative_dir)
            if len(relative_dir.parts) == 1 and dir_name in CONVENTIONAL_C_CPP_DIRS:
                conventional_dirs.add(relative_dir)

        for file_name in sorted(files):
            scanned_files += 1
            file_path = current_path / file_name
            relative_path = file_path.relative_to(root)
            scanned_paths.append(relative_path)

            language = detect_language(file_path)
            if language is not None:
                language_counts[language] += 1

            if is_notable_file(file_name):
                notable_files.append(relative_path)

            if is_c_cpp_build_file(file_name):
                c_cpp_build_files.append(relative_path)

            if file_name == "Makefile":
                c_cpp_makefiles.append(relative_path)
                c_cpp_make_targets.extend(
                    detect_make_targets(file_path=file_path, relative_path=relative_path)
                )
            elif file_name == "CMakeLists.txt":
                c_cpp_cmake_files.append(relative_path)
                c_cpp_cmake_targets.extend(
                    detect_cmake_targets(file_path=file_path, relative_path=relative_path)
                )
                c_cpp_cmake_executable_targets.extend(
                    detect_cmake_executable_targets(
                        file_path=file_path,
                        relative_path=relative_path,
                    )
                )
                c_cpp_cmake_library_targets.extend(
                    detect_cmake_library_targets(
                        file_path=file_path,
                        relative_path=relative_path,
                    )
                )
            elif file_name == "compile_commands.json":
                c_cpp_compile_commands_files.append(relative_path)

            is_source = is_c_cpp_source(file_path)
            is_header = is_c_cpp_header(file_path)

            if is_source:
                c_cpp_sources.append(relative_path)
            elif is_header:
                c_cpp_headers.append(relative_path)

            if is_source or is_header:
                c_cpp_local_includes.extend(
                    detect_local_includes(file_path=file_path, relative_path=relative_path)
                )
                c_cpp_systems_patterns.extend(
                    detect_systems_patterns(
                        file_path=file_path,
                        relative_path=relative_path,
                    )
                )

            if is_source:
                c_cpp_cli_binary_evidence.extend(
                    detect_cli_binary_evidence(
                        file_path=file_path,
                        relative_path=relative_path,
                    )
                )

    c_cpp_project_shape = detect_c_cpp_project_shape(
        c_cpp_sources=c_cpp_sources,
        c_cpp_headers=c_cpp_headers,
        build_files=c_cpp_build_files,
        conventional_dirs=conventional_dirs,
    )
    c_cpp_make_targets = map_make_target_sources(
        targets=c_cpp_make_targets,
        c_cpp_sources=sorted(c_cpp_sources),
    )
    c_cpp_build = CCppBuildSummary(
        makefiles=sorted(c_cpp_makefiles),
        cmake_files=sorted(c_cpp_cmake_files),
        compile_commands_files=sorted(c_cpp_compile_commands_files),
        make_targets=sorted(
            c_cpp_make_targets,
            key=lambda target: (target.source, target.name),
        ),
        cmake_targets=sorted(
            c_cpp_cmake_targets,
            key=lambda target: (target.source, target.name),
        ),
        cmake_executable_targets=sorted(
            c_cpp_cmake_executable_targets,
            key=lambda target: (target.source, target.name),
        ),
        cmake_library_targets=sorted(
            c_cpp_cmake_library_targets,
            key=lambda target: (target.source, target.name),
        ),
    )
    c_cpp_local_includes = sorted(
        c_cpp_local_includes,
        key=lambda include: (include.source, include.included_path),
    )
    c_cpp_resolved_includes = resolve_local_includes(
        local_includes=c_cpp_local_includes,
        c_cpp_headers=sorted(c_cpp_headers),
    )
    c_cpp_systems_patterns = sorted(
        c_cpp_systems_patterns,
        key=lambda match: (match.category, match.source, match.pattern),
    )
    c_cpp_cli_binary_evidence = sorted(
        c_cpp_cli_binary_evidence,
        key=lambda item: (item.source, item.signals),
    )
    detections = detect_repository_components(
        root=root,
        scanned_paths=sorted(scanned_paths),
        scanned_dirs=sorted(scanned_dirs),
        c_cpp_sources=sorted(c_cpp_sources),
        c_cpp_headers=sorted(c_cpp_headers),
        c_cpp_project_shape=c_cpp_project_shape,
        c_cpp_build=c_cpp_build,
        c_cpp_systems_patterns=c_cpp_systems_patterns,
        c_cpp_cli_binary_evidence=c_cpp_cli_binary_evidence,
    )

    return RepositorySummary(
        root=root,
        scanned_files=scanned_files,
        languages=dict(sorted(language_counts.items())),
        notable_files=sorted(notable_files),
        c_cpp_sources=sorted(c_cpp_sources),
        c_cpp_headers=sorted(c_cpp_headers),
        c_cpp_project_shape=c_cpp_project_shape,
        c_cpp_local_includes=c_cpp_local_includes,
        c_cpp_resolved_includes=c_cpp_resolved_includes,
        c_cpp_build=c_cpp_build,
        c_cpp_systems_patterns=c_cpp_systems_patterns,
        c_cpp_cli_binary_evidence=c_cpp_cli_binary_evidence,
        detections=detections,
    )


def detect_repository_components(
    root: Path,
    scanned_paths: list[Path],
    scanned_dirs: list[Path],
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
    c_cpp_project_shape: CCppProjectShape,
    c_cpp_build: CCppBuildSummary,
    c_cpp_systems_patterns: list[CCppSystemsPattern],
    c_cpp_cli_binary_evidence: list[CCppCliBinaryEvidence],
) -> list[Detection]:
    detections: list[Detection] = []
    detections.extend(
        detect_c_cpp_components(
            c_cpp_sources=c_cpp_sources,
            c_cpp_headers=c_cpp_headers,
            c_cpp_project_shape=c_cpp_project_shape,
            c_cpp_build=c_cpp_build,
            c_cpp_systems_patterns=c_cpp_systems_patterns,
            c_cpp_cli_binary_evidence=c_cpp_cli_binary_evidence,
        )
    )
    detections.extend(detect_python_api_components(root=root, files=scanned_paths))
    detections.extend(
        detect_database_components(root=root, files=scanned_paths, dirs=scanned_dirs)
    )
    detections.extend(detect_cache_components(root=root, files=scanned_paths))
    detections.extend(detect_docker_components(files=scanned_paths))
    detections.extend(
        detect_test_components(root=root, files=scanned_paths, dirs=scanned_dirs)
    )

    return sorted(
        set(detections),
        key=lambda detection: (
            detection.kind,
            detection.name,
            detection.evidence,
            detection.confidence is None,
            detection.confidence or 0,
        ),
    )


def detect_language(path: Path) -> str | None:
    return LANGUAGE_EXTENSIONS.get(path.suffix.lower())


def is_notable_file(file_name: str) -> bool:
    return file_name in NOTABLE_FILE_NAMES


def is_c_cpp_build_file(file_name: str) -> bool:
    return file_name in C_CPP_BUILD_FILE_NAMES


def is_c_cpp_source(path: Path) -> bool:
    return path.suffix.lower() in C_CPP_SOURCE_EXTENSIONS


def is_c_cpp_header(path: Path) -> bool:
    return path.suffix.lower() in C_CPP_HEADER_EXTENSIONS


def detect_c_cpp_project_shape(
    c_cpp_sources: list[Path],
    c_cpp_headers: list[Path],
    build_files: list[Path],
    conventional_dirs: set[Path],
) -> CCppProjectShape:
    looks_like_project = bool(c_cpp_sources or c_cpp_headers or build_files)
    return CCppProjectShape(
        looks_like_project=looks_like_project,
        build_files=sorted(build_files),
        conventional_dirs=sorted(conventional_dirs),
    )


def detect_local_includes(file_path: Path, relative_path: Path) -> list[CCppLocalInclude]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    return [
        CCppLocalInclude(source=relative_path, included_path=match)
        for match in LOCAL_INCLUDE_PATTERN.findall(content)
    ]


def resolve_local_includes(
    local_includes: list[CCppLocalInclude],
    c_cpp_headers: list[Path],
) -> list[CCppResolvedInclude]:
    header_paths = set(c_cpp_headers)
    headers_by_basename: defaultdict[str, list[Path]] = defaultdict(list)
    for header in sorted(c_cpp_headers):
        headers_by_basename[header.name].append(header)

    resolved = [
        resolve_local_include(
            local_include=local_include,
            header_paths=header_paths,
            headers_by_basename=headers_by_basename,
        )
        for local_include in local_includes
    ]
    return sorted(resolved, key=resolved_include_sort_key)


def resolve_local_include(
    local_include: CCppLocalInclude,
    header_paths: set[Path],
    headers_by_basename: dict[str, list[Path]],
) -> CCppResolvedInclude:
    include_path = Path(local_include.included_path)
    if include_path.is_absolute() or not include_path.name:
        return CCppResolvedInclude(
            source=local_include.source,
            included_path=local_include.included_path,
            resolved_path=None,
            status="unresolved",
        )

    exact_matches = sorted(
        {
            candidate
            for candidate in local_include_candidates(local_include)
            if candidate in header_paths
        }
    )
    if len(exact_matches) == 1:
        return CCppResolvedInclude(
            source=local_include.source,
            included_path=local_include.included_path,
            resolved_path=exact_matches[0],
            status="resolved",
        )
    if len(exact_matches) > 1:
        return CCppResolvedInclude(
            source=local_include.source,
            included_path=local_include.included_path,
            resolved_path=None,
            status="ambiguous",
        )

    basename_matches = sorted(set(headers_by_basename.get(include_path.name, [])))
    if len(basename_matches) == 1:
        return CCppResolvedInclude(
            source=local_include.source,
            included_path=local_include.included_path,
            resolved_path=basename_matches[0],
            status="resolved",
        )
    if len(basename_matches) > 1:
        return CCppResolvedInclude(
            source=local_include.source,
            included_path=local_include.included_path,
            resolved_path=None,
            status="ambiguous",
        )

    return CCppResolvedInclude(
        source=local_include.source,
        included_path=local_include.included_path,
        resolved_path=None,
        status="unresolved",
    )


def local_include_candidates(local_include: CCppLocalInclude) -> list[Path]:
    include_path = Path(local_include.included_path)
    candidates = [
        local_include.source.parent / include_path,
        include_path,
        Path("include") / include_path,
        Path("src") / include_path,
        Path("lib") / include_path,
    ]
    normalized_candidates = [
        normalized
        for candidate in candidates
        if (normalized := normalize_relative_path(candidate)) is not None
    ]
    return sorted(set(normalized_candidates))


def normalize_relative_path(path: Path) -> Path | None:
    if path.is_absolute():
        return None

    normalized = Path()
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not normalized.parts:
                return None
            normalized = normalized.parent
            continue
        normalized = normalized / part

    if not normalized.parts:
        return None
    return normalized


def resolved_include_sort_key(
    resolved_include: CCppResolvedInclude,
) -> tuple[Path, str, str, str]:
    resolved_path = (
        ""
        if resolved_include.resolved_path is None
        else resolved_include.resolved_path.as_posix()
    )
    return (
        resolved_include.source,
        resolved_include.included_path,
        resolved_include.status,
        resolved_path,
    )


def detect_make_targets(file_path: Path, relative_path: Path) -> list[CCppBuildTarget]:
    try:
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    targets: list[CCppBuildTarget] = []
    for line in lines:
        parsed_targets = parse_make_target_line(line)
        for target_name, object_prerequisites in parsed_targets:
            targets.append(
                CCppBuildTarget(
                    source=relative_path,
                    name=target_name,
                    kind="make target",
                    object_prerequisites=object_prerequisites,
                )
            )

    return targets


def parse_make_target_names(line: str) -> list[str]:
    return [target_name for target_name, _objects in parse_make_target_line(line)]


def parse_make_target_line(line: str) -> list[tuple[str, tuple[str, ...]]]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("."):
        return []

    target_part, separator, remainder = stripped.partition(":")
    if not separator or "=" in target_part or remainder.startswith("="):
        return []

    target_names = target_part.split()
    obvious_target_names = [
        target_name
        for target_name in target_names
        if is_obvious_make_target_name(target_name)
    ]
    object_prerequisites = parse_make_object_prerequisites(remainder)
    return [
        (target_name, object_prerequisites)
        for target_name in obvious_target_names
    ]


def parse_make_object_prerequisites(remainder: str) -> tuple[str, ...]:
    prerequisites = remainder.split("#", 1)[0].split()
    return tuple(
        sorted(
            prerequisite
            for prerequisite in prerequisites
            if is_object_prerequisite(prerequisite)
        )
    )


def is_obvious_make_target_name(target_name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", target_name))


def is_object_prerequisite(value: str) -> bool:
    return (
        "$" not in value
        and Path(value).suffix == ".o"
        and re.fullmatch(r"[A-Za-z0-9_./-]+\.o", value) is not None
    )


def map_make_target_sources(
    targets: list[CCppBuildTarget],
    c_cpp_sources: list[Path],
) -> list[CCppBuildTarget]:
    source_index = make_object_source_index(c_cpp_sources)
    mapped_targets: list[CCppBuildTarget] = []

    for target in targets:
        source_files: set[Path] = set(target.source_files)
        for object_prerequisite in target.object_prerequisites:
            source_file = resolve_object_prerequisite(
                object_prerequisite=object_prerequisite,
                source_index=source_index,
            )
            if source_file is not None:
                source_files.add(source_file)

        mapped_targets.append(
            CCppBuildTarget(
                source=target.source,
                name=target.name,
                kind=target.kind,
                source_files=tuple(sorted(source_files)),
                object_prerequisites=target.object_prerequisites,
            )
        )

    return mapped_targets


def make_object_source_index(
    c_cpp_sources: list[Path],
) -> dict[str, dict[str, list[Path]]]:
    by_path: dict[str, list[Path]] = defaultdict(list)
    by_name: dict[str, list[Path]] = defaultdict(list)
    for source in c_cpp_sources:
        object_path = source.with_suffix(".o")
        by_path[object_path.as_posix()].append(source)
        by_name[object_path.name].append(source)

    return {"path": by_path, "name": by_name}


def resolve_object_prerequisite(
    object_prerequisite: str,
    source_index: dict[str, dict[str, list[Path]]],
) -> Path | None:
    path_matches = sorted(source_index["path"].get(object_prerequisite, []))
    if len(path_matches) == 1:
        return path_matches[0]
    if len(path_matches) > 1:
        return None

    name_matches = sorted(source_index["name"].get(Path(object_prerequisite).name, []))
    if len(name_matches) == 1:
        return name_matches[0]
    return None


def detect_cmake_targets(file_path: Path, relative_path: Path) -> list[CCppBuildTarget]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    return parse_cmake_targets(content=content, relative_path=relative_path)


def detect_cmake_executable_targets(
    file_path: Path,
    relative_path: Path,
) -> list[CCppBuildTarget]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    return [
        target
        for target in parse_cmake_targets(content=content, relative_path=relative_path)
        if target.kind == "executable"
    ]


def detect_cmake_library_targets(
    file_path: Path,
    relative_path: Path,
) -> list[CCppBuildTarget]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    return [
        target
        for target in parse_cmake_targets(content=content, relative_path=relative_path)
        if target.kind == "library"
    ]


def parse_cmake_targets(content: str, relative_path: Path) -> list[CCppBuildTarget]:
    targets: list[CCppBuildTarget] = []
    for match in CMAKE_TARGET_CALL_PATTERN.finditer(content):
        target_type = match.group(1).lower()
        tokens = tokenize_cmake_call(match.group("body"))
        if not tokens:
            continue

        target_name = tokens[0]
        if "$" in target_name:
            continue

        source_files = tuple(
            sorted(
                source_file
                for token in tokens[1:]
                if (source_file := cmake_source_argument(token, relative_path)) is not None
            )
        )
        targets.append(
            CCppBuildTarget(
                source=relative_path,
                name=target_name,
                kind=target_type,
                source_files=source_files,
            )
        )

    return targets


def tokenize_cmake_call(body: str) -> list[str]:
    tokens: list[str] = []
    for match in CMAKE_TOKEN_PATTERN.findall(body):
        token = match.strip()
        if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
            token = token[1:-1]
        tokens.append(token)
    return tokens


def cmake_source_argument(token: str, relative_path: Path) -> Path | None:
    if (
        not token
        or "$" in token
        or token.startswith("<")
        or token.upper() in CMAKE_LIBRARY_TYPE_TOKENS
        or token.upper() in CMAKE_OPTION_TOKENS
    ):
        return None

    token_path = Path(token)
    if token_path.is_absolute() or not is_c_cpp_file_path(token_path):
        return None

    candidate = relative_path.parent / token_path
    return normalize_relative_path(candidate)


def is_c_cpp_file_path(path: Path) -> bool:
    return path.suffix.lower() in C_CPP_SOURCE_EXTENSIONS | C_CPP_HEADER_EXTENSIONS


def detect_systems_patterns(
    file_path: Path,
    relative_path: Path,
) -> list[CCppSystemsPattern]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    content = strip_c_cpp_comments_and_strings(content)
    matches: list[CCppSystemsPattern] = []
    for category, patterns in SYSTEMS_PATTERNS.items():
        for pattern in patterns:
            if contains_systems_pattern(content, pattern):
                matches.append(
                    CCppSystemsPattern(
                        category=category,
                        source=relative_path,
                        pattern=pattern,
                    )
                )

    return matches


def detect_cli_binary_evidence(
    file_path: Path,
    relative_path: Path,
) -> list[CCppCliBinaryEvidence]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    code = strip_c_cpp_comments_and_strings(content)
    comments_removed = strip_c_cpp_comments(content)
    signals: set[str] = set()

    main_params = C_CPP_MAIN_FUNCTION_PATTERN.findall(code)
    if main_params:
        signals.add("main")
        if any(contains_argc_argv(params) for params in main_params):
            signals.add("argc/argv")

    if C_CPP_OPTION_PARSER_PATTERN.search(code) is not None:
        signals.add("getopt")

    if C_CPP_HELP_OPTION_PATTERN.search(comments_removed) is not None:
        signals.add("--help")

    if not signals:
        return []

    return [
        CCppCliBinaryEvidence(
            source=relative_path,
            signals=tuple(sorted(signals)),
        )
    ]


def strip_c_cpp_comments_and_strings(content: str) -> str:
    return C_CPP_COMMENT_OR_STRING_PATTERN.sub(
        lambda match: " " * len(match.group(0)),
        content,
    )


def strip_c_cpp_comments(content: str) -> str:
    return C_CPP_COMMENT_OR_STRING_PATTERN.sub(
        lambda match: " " * len(match.group(0))
        if is_c_cpp_comment(match.group(0))
        else match.group(0),
        content,
    )


def is_c_cpp_comment(value: str) -> bool:
    return value.startswith("//") or value.startswith("/*")


def contains_argc_argv(params: str) -> bool:
    return (
        re.search(r"(?<![A-Za-z0-9_])argc(?![A-Za-z0-9_])", params) is not None
        and re.search(r"(?<![A-Za-z0-9_])argv(?![A-Za-z0-9_])", params) is not None
    )


def contains_systems_pattern(content: str, pattern: str) -> bool:
    if pattern == "exec":
        return (
            re.search(
                r"(?<![A-Za-z0-9_])exec(?:l|le|lp|lpe|v|ve|vp|vpe)?\s*\(",
                content,
            )
            is not None
        )

    if pattern in {"pthread_cond", "pthread_mutex"}:
        return (
            re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(pattern)}(?:_[A-Za-z0-9_]+)?\s*\(",
                content,
            )
            is not None
        )

    if pattern in {"queue", "enqueue", "dequeue"}:
        return (
            re.search(rf"(?<![A-Za-z0-9_]){re.escape(pattern)}(?![A-Za-z0-9_])", content)
            is not None
        )

    return (
        re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(pattern)}\s*\(",
            content,
        )
        is not None
    )
