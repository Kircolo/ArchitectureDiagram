from __future__ import annotations

from collections import Counter
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
CMAKE_TARGET_PATTERN = re.compile(
    r"^\s*add_(executable|library)\s*\(\s*([A-Za-z0-9_.:-]+)",
    re.IGNORECASE | re.MULTILINE,
)
C_CPP_COMMENT_OR_STRING_PATTERN = re.compile(
    r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'",
    re.MULTILINE | re.DOTALL,
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
class CCppBuildTarget:
    source: Path
    name: str


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
class RepositorySummary:
    root: Path
    scanned_files: int
    languages: dict[str, int]
    notable_files: list[Path]
    c_cpp_sources: list[Path]
    c_cpp_headers: list[Path]
    c_cpp_project_shape: CCppProjectShape
    c_cpp_local_includes: list[CCppLocalInclude]
    c_cpp_build: CCppBuildSummary
    c_cpp_systems_patterns: list[CCppSystemsPattern]
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
    c_cpp_systems_patterns: list[CCppSystemsPattern] = []
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

    c_cpp_project_shape = detect_c_cpp_project_shape(
        c_cpp_sources=c_cpp_sources,
        c_cpp_headers=c_cpp_headers,
        build_files=c_cpp_build_files,
        conventional_dirs=conventional_dirs,
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
    c_cpp_systems_patterns = sorted(
        c_cpp_systems_patterns,
        key=lambda match: (match.category, match.source, match.pattern),
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
        c_cpp_build=c_cpp_build,
        c_cpp_systems_patterns=c_cpp_systems_patterns,
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
) -> list[Detection]:
    detections: list[Detection] = []
    detections.extend(
        detect_c_cpp_components(
            c_cpp_sources=c_cpp_sources,
            c_cpp_headers=c_cpp_headers,
            c_cpp_project_shape=c_cpp_project_shape,
            c_cpp_build=c_cpp_build,
            c_cpp_systems_patterns=c_cpp_systems_patterns,
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


def detect_make_targets(file_path: Path, relative_path: Path) -> list[CCppBuildTarget]:
    try:
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    targets: list[CCppBuildTarget] = []
    for line in lines:
        target_names = parse_make_target_names(line)
        targets.extend(
            CCppBuildTarget(source=relative_path, name=target_name)
            for target_name in target_names
        )

    return targets


def parse_make_target_names(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("."):
        return []

    target_part, separator, remainder = stripped.partition(":")
    if not separator or "=" in target_part or remainder.startswith("="):
        return []

    target_names = target_part.split()
    return [
        target_name
        for target_name in target_names
        if is_obvious_make_target_name(target_name)
    ]


def is_obvious_make_target_name(target_name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", target_name))


def detect_cmake_targets(file_path: Path, relative_path: Path) -> list[CCppBuildTarget]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    return [
        CCppBuildTarget(source=relative_path, name=target_name)
        for _target_type, target_name in CMAKE_TARGET_PATTERN.findall(content)
        if "$" not in target_name
    ]


def detect_cmake_executable_targets(
    file_path: Path,
    relative_path: Path,
) -> list[CCppBuildTarget]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    return [
        CCppBuildTarget(source=relative_path, name=target_name)
        for target_type, target_name in CMAKE_TARGET_PATTERN.findall(content)
        if target_type.lower() == "executable" and "$" not in target_name
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
        CCppBuildTarget(source=relative_path, name=target_name)
        for target_type, target_name in CMAKE_TARGET_PATTERN.findall(content)
        if target_type.lower() == "library" and "$" not in target_name
    ]


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


def strip_c_cpp_comments_and_strings(content: str) -> str:
    return C_CPP_COMMENT_OR_STRING_PATTERN.sub(
        lambda match: " " * len(match.group(0)),
        content,
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
