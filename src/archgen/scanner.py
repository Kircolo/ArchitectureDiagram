from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import os
from pathlib import Path
import re


IGNORED_DIRS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "target",
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
    r"^\s*add_(?:executable|library)\s*\(\s*([A-Za-z0-9_.:-]+)",
    re.IGNORECASE | re.MULTILINE,
)
SYSTEMS_PATTERNS = {
    "Sockets": ["socket", "bind", "listen", "accept", "connect", "send", "recv"],
    "Threads": ["pthread_create", "pthread_join"],
    "Synchronization": ["pthread_mutex", "pthread_cond", "sem_wait", "sem_post"],
    "File I/O": ["open", "read", "write", "fopen", "fread", "fwrite"],
    "Memory/process": ["malloc", "free", "fork", "exec", "pipe"],
}
SYSTEMS_PREFIX_PATTERNS = {"exec", "pthread_cond", "pthread_mutex"}

NOTABLE_FILE_NAMES = {
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
    c_cpp_local_includes: list[CCppLocalInclude] = []
    c_cpp_systems_patterns: list[CCppSystemsPattern] = []
    conventional_dirs: set[Path] = set()
    scanned_files = 0

    for current_root, dirs, files in os.walk(root):
        dirs[:] = sorted(dir_name for dir_name in dirs if dir_name not in IGNORED_DIRS)

        current_path = Path(current_root)
        for dir_name in dirs:
            dir_path = current_path / dir_name
            relative_dir = dir_path.relative_to(root)
            if len(relative_dir.parts) == 1 and dir_name in CONVENTIONAL_C_CPP_DIRS:
                conventional_dirs.add(relative_dir)

        for file_name in sorted(files):
            scanned_files += 1
            file_path = current_path / file_name
            relative_path = file_path.relative_to(root)

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
    )

    return RepositorySummary(
        root=root,
        scanned_files=scanned_files,
        languages=dict(sorted(language_counts.items())),
        notable_files=sorted(notable_files),
        c_cpp_sources=sorted(c_cpp_sources),
        c_cpp_headers=sorted(c_cpp_headers),
        c_cpp_project_shape=c_cpp_project_shape,
        c_cpp_local_includes=sorted(
            c_cpp_local_includes,
            key=lambda include: (include.source, include.included_path),
        ),
        c_cpp_build=c_cpp_build,
        c_cpp_systems_patterns=sorted(
            c_cpp_systems_patterns,
            key=lambda match: (match.category, match.source, match.pattern),
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
        for target_name in CMAKE_TARGET_PATTERN.findall(content)
        if "$" not in target_name
    ]


def detect_systems_patterns(
    file_path: Path,
    relative_path: Path,
) -> list[CCppSystemsPattern]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

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


def contains_systems_pattern(content: str, pattern: str) -> bool:
    if pattern in SYSTEMS_PREFIX_PATTERNS:
        return re.search(rf"(?<![A-Za-z0-9_]){re.escape(pattern)}", content) is not None

    return (
        re.search(rf"(?<![A-Za-z0-9_]){re.escape(pattern)}(?![A-Za-z0-9_])", content)
        is not None
    )


def format_summary(summary: RepositorySummary) -> str:
    lines = [
        "Architecture Summary",
        f"Root: {summary.root}",
        f"Scanned files: {summary.scanned_files}",
        "Languages:",
    ]

    if summary.languages:
        lines.extend(
            f"  {language}: {count}"
            for language, count in sorted(summary.languages.items())
        )
    else:
        lines.append("  None")

    lines.append("Notable files:")
    if summary.notable_files:
        lines.extend(f"  {path.as_posix()}" for path in summary.notable_files)
    else:
        lines.append("  None")

    lines.append("C/C++ files:")
    lines.append(f"  Sources: {len(summary.c_cpp_sources)}")
    if summary.c_cpp_sources:
        lines.extend(f"    {path.as_posix()}" for path in summary.c_cpp_sources)
    else:
        lines.append("    None")

    lines.append(f"  Headers: {len(summary.c_cpp_headers)}")
    if summary.c_cpp_headers:
        lines.extend(f"    {path.as_posix()}" for path in summary.c_cpp_headers)
    else:
        lines.append("    None")

    lines.append("C/C++ build files:")
    lines.append("  Makefiles:")
    if summary.c_cpp_build.makefiles:
        lines.extend(f"    {path.as_posix()}" for path in summary.c_cpp_build.makefiles)
    else:
        lines.append("    None")
    lines.append("  CMake files:")
    if summary.c_cpp_build.cmake_files:
        lines.extend(f"    {path.as_posix()}" for path in summary.c_cpp_build.cmake_files)
    else:
        lines.append("    None")
    lines.append("  Compile commands:")
    if summary.c_cpp_build.compile_commands_files:
        lines.extend(
            f"    {path.as_posix()}"
            for path in summary.c_cpp_build.compile_commands_files
        )
    else:
        lines.append("    None")
    lines.append("  Make targets:")
    if summary.c_cpp_build.make_targets:
        lines.extend(
            f"    {target.source.as_posix()} -> {target.name}"
            for target in summary.c_cpp_build.make_targets
        )
    else:
        lines.append("    None")
    lines.append("  CMake targets:")
    if summary.c_cpp_build.cmake_targets:
        lines.extend(
            f"    {target.source.as_posix()} -> {target.name}"
            for target in summary.c_cpp_build.cmake_targets
        )
    else:
        lines.append("    None")

    lines.append("C/C++ project shape:")
    looks_like_project = "Yes" if summary.c_cpp_project_shape.looks_like_project else "No"
    lines.append(f"  Looks like C/C++ project: {looks_like_project}")
    lines.append("  Evidence:")
    lines.append(f"    Source files: {len(summary.c_cpp_sources)}")
    lines.append(f"    Header files: {len(summary.c_cpp_headers)}")
    lines.append("    Build files:")
    if summary.c_cpp_project_shape.build_files:
        lines.extend(
            f"      {path.as_posix()}"
            for path in summary.c_cpp_project_shape.build_files
        )
    else:
        lines.append("      None")
    lines.append("    Conventional directories:")
    if summary.c_cpp_project_shape.conventional_dirs:
        lines.extend(
            f"      {path.as_posix()}/"
            for path in summary.c_cpp_project_shape.conventional_dirs
        )
    else:
        lines.append("      None")

    lines.append("C/C++ local includes:")
    lines.append(f"  Relationships: {len(summary.c_cpp_local_includes)}")
    if summary.c_cpp_local_includes:
        lines.extend(
            f"    {include.source.as_posix()} -> {include.included_path}"
            for include in summary.c_cpp_local_includes
        )
    else:
        lines.append("    None")

    lines.append("C/C++ systems patterns:")
    if summary.c_cpp_systems_patterns:
        for category in SYSTEMS_PATTERNS:
            category_matches = [
                match
                for match in summary.c_cpp_systems_patterns
                if match.category == category
            ]
            if not category_matches:
                continue
            lines.append(f"  {category}:")
            lines.extend(
                f"    {match.source.as_posix()} -> {match.pattern}"
                for match in category_matches
            )
    else:
        lines.append("  None")

    return "\n".join(lines)
