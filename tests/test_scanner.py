from pathlib import Path

from archgen.detection import Detection
from archgen.scanner import (
    CCppBuildTarget,
    CCppCliBinaryEvidence,
    CCppLocalInclude,
    format_summary,
    scan_repository,
)


def touch(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def find_detection(
    detections: list[Detection],
    kind: str,
    name: str,
) -> Detection:
    for detection in detections:
        if detection.kind == kind and detection.name == name:
            return detection
    raise AssertionError(f"Missing detection: {kind} / {name}")


def test_scan_repository_counts_nested_files(tmp_path: Path) -> None:
    touch(tmp_path / "main.py")
    touch(tmp_path / "src" / "app.cpp")
    touch(tmp_path / "src" / "include" / "app.h")

    summary = scan_repository(tmp_path)

    assert summary.scanned_files == 3


def test_scan_repository_ignores_default_directories(tmp_path: Path) -> None:
    touch(tmp_path / "main.py")
    touch(tmp_path / ".git" / "ignored.py")
    touch(tmp_path / ".tmp" / "ignored.py")
    touch(tmp_path / ".venv" / "ignored.py")
    touch(tmp_path / "venv" / "ignored.py")
    touch(tmp_path / "__pycache__" / "ignored.pyc")
    touch(tmp_path / "build" / "ignored.cpp")
    touch(tmp_path / "coverage" / "ignored.py")
    touch(tmp_path / "vendor" / "ignored.py")

    summary = scan_repository(tmp_path)

    assert summary.scanned_files == 1
    assert summary.languages == {"Python": 1}


def test_scan_repository_detects_languages(tmp_path: Path) -> None:
    for file_name in [
        "main.c",
        "lib.hpp",
        "server.py",
        "config.json",
        "config.yaml",
        "pyproject.toml",
        "README.md",
    ]:
        touch(tmp_path / file_name)

    summary = scan_repository(tmp_path)

    assert summary.languages == {
        "C/C++": 2,
        "JSON": 1,
        "Markdown": 1,
        "Python": 1,
        "TOML": 1,
        "YAML": 1,
    }


def test_env_example_is_notable_but_not_a_language(tmp_path: Path) -> None:
    touch(tmp_path / ".env.example", "DATABASE_URL=postgresql://example\n")

    summary = scan_repository(tmp_path)

    assert summary.scanned_files == 1
    assert summary.notable_files == [Path(".env.example")]
    assert summary.languages == {}


def test_scan_repository_detects_c_cpp_sources_and_headers(tmp_path: Path) -> None:
    for file_name in [
        "src/main.cpp",
        "src/platform.c",
        "src/module.cc",
        "src/detail.cxx",
        "include/platform.h",
        "include/module.hh",
        "include/detail.hpp",
        "include/config.hxx",
    ]:
        touch(tmp_path / file_name)

    summary = scan_repository(tmp_path)

    assert summary.c_cpp_sources == [
        Path("src/detail.cxx"),
        Path("src/main.cpp"),
        Path("src/module.cc"),
        Path("src/platform.c"),
    ]
    assert summary.c_cpp_headers == [
        Path("include/config.hxx"),
        Path("include/detail.hpp"),
        Path("include/module.hh"),
        Path("include/platform.h"),
    ]


def test_scan_repository_excludes_ignored_c_cpp_files(tmp_path: Path) -> None:
    touch(tmp_path / "src" / "main.cpp")
    touch(tmp_path / "include" / "main.h")
    touch(tmp_path / "build" / "generated.cpp")
    touch(tmp_path / "vendor" / "external.h")

    summary = scan_repository(tmp_path)

    assert summary.c_cpp_sources == [Path("src/main.cpp")]
    assert summary.c_cpp_headers == [Path("include/main.h")]


def test_scan_repository_detects_c_cpp_project_shape_evidence(tmp_path: Path) -> None:
    touch(tmp_path / "src" / "main.cpp")
    touch(tmp_path / "include" / "platform.h")
    touch(tmp_path / "lib" / "support.py")
    touch(tmp_path / "tests" / "test_main.py")
    touch(tmp_path / "Makefile")
    touch(tmp_path / "src" / "CMakeLists.txt")
    touch(tmp_path / "compile_commands.json")

    summary = scan_repository(tmp_path)

    assert summary.c_cpp_project_shape.looks_like_project is True
    assert summary.c_cpp_project_shape.build_files == [
        Path("Makefile"),
        Path("compile_commands.json"),
        Path("src/CMakeLists.txt"),
    ]
    assert summary.c_cpp_project_shape.conventional_dirs == [
        Path("include"),
        Path("lib"),
        Path("src"),
        Path("tests"),
    ]


def test_conventional_dirs_alone_do_not_make_c_cpp_project(tmp_path: Path) -> None:
    touch(tmp_path / "src" / "main.py")
    touch(tmp_path / "tests" / "test_main.py")

    summary = scan_repository(tmp_path)

    assert summary.c_cpp_project_shape.looks_like_project is False
    assert summary.c_cpp_project_shape.build_files == []
    assert summary.c_cpp_project_shape.conventional_dirs == [
        Path("src"),
        Path("tests"),
    ]


def test_scan_repository_detects_local_c_cpp_includes(tmp_path: Path) -> None:
    touch(
        tmp_path / "src" / "main.cpp",
        '#include "platform.h"\n'
        '# include "http/parser.hpp"\n'
        "#include <vector>\n",
    )
    touch(tmp_path / "include" / "platform.h", '#include "config.h"\n')
    touch(tmp_path / "scripts" / "fake.py", '#include "ignored.h"\n')
    touch(tmp_path / "build" / "generated.cpp", '#include "generated.h"\n')

    summary = scan_repository(tmp_path)

    assert summary.c_cpp_local_includes == [
        CCppLocalInclude(Path("include/platform.h"), "config.h"),
        CCppLocalInclude(Path("src/main.cpp"), "http/parser.hpp"),
        CCppLocalInclude(Path("src/main.cpp"), "platform.h"),
    ]


def test_empty_local_include_summary_prints_none(tmp_path: Path) -> None:
    touch(tmp_path / "src" / "main.cpp", "#include <stdio.h>\n")

    summary = scan_repository(tmp_path)
    output = format_summary(summary)

    assert summary.c_cpp_local_includes == []
    assert "C/C++ local includes:\n  Relationships: 0\n    None" in output


def test_scan_repository_detects_c_cpp_build_files_and_targets(tmp_path: Path) -> None:
    touch(
        tmp_path / "Makefile",
        "all: app test\n"
        "app test: main.o\n"
        "CC := clang\n"
        ".PHONY: clean\n"
        "clean:\n",
    )
    touch(
        tmp_path / "src" / "CMakeLists.txt",
        "add_executable(app main.cpp)\n"
        "add_library(platform STATIC platform.cpp)\n"
        "add_executable(${dynamic_name} ignored.cpp)\n",
    )
    touch(tmp_path / "compile_commands.json")

    summary = scan_repository(tmp_path)

    assert summary.c_cpp_build.makefiles == [Path("Makefile")]
    assert summary.c_cpp_build.cmake_files == [Path("src/CMakeLists.txt")]
    assert summary.c_cpp_build.compile_commands_files == [Path("compile_commands.json")]
    assert summary.c_cpp_build.make_targets == [
        CCppBuildTarget(Path("Makefile"), "all"),
        CCppBuildTarget(Path("Makefile"), "app"),
        CCppBuildTarget(Path("Makefile"), "clean"),
        CCppBuildTarget(Path("Makefile"), "test"),
    ]
    assert summary.c_cpp_build.cmake_targets == [
        CCppBuildTarget(Path("src/CMakeLists.txt"), "app"),
        CCppBuildTarget(Path("src/CMakeLists.txt"), "platform"),
    ]
    assert summary.c_cpp_build.cmake_executable_targets == [
        CCppBuildTarget(Path("src/CMakeLists.txt"), "app"),
    ]
    assert summary.c_cpp_build.cmake_library_targets == [
        CCppBuildTarget(Path("src/CMakeLists.txt"), "platform"),
    ]


def test_scan_repository_excludes_ignored_c_cpp_build_files(tmp_path: Path) -> None:
    touch(tmp_path / "build" / "Makefile", "ignored:\n")
    touch(tmp_path / "vendor" / "CMakeLists.txt", "add_library(ignored ignored.cpp)\n")

    summary = scan_repository(tmp_path)

    assert summary.c_cpp_build.makefiles == []
    assert summary.c_cpp_build.cmake_files == []
    assert summary.c_cpp_build.make_targets == []
    assert summary.c_cpp_build.cmake_targets == []


def test_scan_repository_detects_c_cpp_systems_patterns(tmp_path: Path) -> None:
    touch(
        tmp_path / "src" / "server.c",
        "socket(); bind(); listen(); accept(); connect(); send(); recv();\n"
        "open(); read(); write(); malloc(); free(); fork(); execl(); pipe();\n",
    )
    touch(
        tmp_path / "src" / "worker.cpp",
        "pthread_create(); pthread_join(); pthread_mutex_lock(); pthread_cond_wait();\n"
        "sem_wait(); sem_post(); fopen(); fread(); fwrite();\n",
    )
    touch(tmp_path / "scripts" / "fake.py", "socket(); pthread_create();\n")
    touch(tmp_path / "build" / "generated.c", "socket(); read();\n")

    summary = scan_repository(tmp_path)
    matches = {
        (match.category, match.source, match.pattern)
        for match in summary.c_cpp_systems_patterns
    }

    assert matches == {
        ("Sockets", Path("src/server.c"), "accept"),
        ("Sockets", Path("src/server.c"), "bind"),
        ("Sockets", Path("src/server.c"), "connect"),
        ("Sockets", Path("src/server.c"), "listen"),
        ("Sockets", Path("src/server.c"), "recv"),
        ("Sockets", Path("src/server.c"), "send"),
        ("Sockets", Path("src/server.c"), "socket"),
        ("Threads", Path("src/worker.cpp"), "pthread_create"),
        ("Threads", Path("src/worker.cpp"), "pthread_join"),
        ("Synchronization", Path("src/worker.cpp"), "pthread_cond"),
        ("Synchronization", Path("src/worker.cpp"), "pthread_mutex"),
        ("Synchronization", Path("src/worker.cpp"), "sem_post"),
        ("Synchronization", Path("src/worker.cpp"), "sem_wait"),
        ("File I/O", Path("src/server.c"), "open"),
        ("File I/O", Path("src/server.c"), "read"),
        ("File I/O", Path("src/server.c"), "write"),
        ("File I/O", Path("src/worker.cpp"), "fopen"),
        ("File I/O", Path("src/worker.cpp"), "fread"),
        ("File I/O", Path("src/worker.cpp"), "fwrite"),
        ("Memory/process", Path("src/server.c"), "exec"),
        ("Memory/process", Path("src/server.c"), "fork"),
        ("Memory/process", Path("src/server.c"), "free"),
        ("Memory/process", Path("src/server.c"), "malloc"),
        ("Memory/process", Path("src/server.c"), "pipe"),
    }


def test_empty_systems_patterns_summary_prints_none(tmp_path: Path) -> None:
    touch(tmp_path / "src" / "main.cpp", "int already_readable = 0;\n")

    summary = scan_repository(tmp_path)
    output = format_summary(summary)

    assert summary.c_cpp_systems_patterns == []
    assert "C/C++ systems patterns:\n  None" in output


def test_c_cpp_systems_patterns_ignore_comments_strings_and_unrelated_prefixes(
    tmp_path: Path,
) -> None:
    touch(
        tmp_path / "src" / "main.c",
        "// socket(); read();\n"
        'const char *example = "pthread_create(); malloc();";\n'
        "execute();\n"
        "int already_readable = 0;\n",
    )

    summary = scan_repository(tmp_path)

    assert summary.c_cpp_systems_patterns == []


def test_c_cpp_components_detect_modules_executables_build_targets_and_queues(
    tmp_path: Path,
) -> None:
    touch(tmp_path / "src" / "queue.c", "queue_t q; enqueue(&q); dequeue(&q);\n")
    touch(tmp_path / "include" / "queue.h")
    touch(tmp_path / "src" / "main.c", "int main(void) { return 0; }\n")
    touch(tmp_path / "Makefile", "app: queue.o main.o\n")
    touch(tmp_path / "CMakeLists.txt", "add_executable(app main.c queue.c)\n")

    summary = scan_repository(tmp_path)

    project = find_detection(summary.detections, "C/C++ Project", "C application")
    module = find_detection(summary.detections, "C/C++ Module", "queue module")
    executable = find_detection(summary.detections, "Executable Target", "app")
    build_target = find_detection(summary.detections, "Build Target", "app")
    queue = find_detection(summary.detections, "C/C++ Systems Pattern", "Queues")

    assert Path("src/main.c") in project.evidence
    assert module.evidence == (Path("include/queue.h"), Path("src/queue.c"))
    assert executable.evidence == (Path("CMakeLists.txt"),)
    assert build_target.evidence == (Path("Makefile"),)
    assert queue.evidence == (Path("src/queue.c"),)


def test_c_cpp_cli_binary_detected_from_main_argc_argv(tmp_path: Path) -> None:
    touch(
        tmp_path / "src" / "main.c",
        "int main(int argc, char **argv) {\n"
        "    return argc > 1 && argv[0] != 0;\n"
        "}\n",
    )

    summary = scan_repository(tmp_path)

    cli_binary = find_detection(summary.detections, "Executable Target", "CLI Binary")

    assert summary.c_cpp_cli_binary_evidence == [
        CCppCliBinaryEvidence(Path("src/main.c"), ("argc/argv", "main"))
    ]
    assert cli_binary.evidence == (Path("src/main.c"),)
    assert cli_binary.confidence == 0.75


def test_c_cpp_cli_binary_detects_getopt_evidence(tmp_path: Path) -> None:
    touch(
        tmp_path / "src" / "tool.c",
        "#include <unistd.h>\n"
        "int main(void) {\n"
        '    return getopt(0, 0, "h") == -1;\n'
        "}\n",
    )

    summary = scan_repository(tmp_path)

    cli_binary = find_detection(summary.detections, "Executable Target", "CLI Binary")

    assert summary.c_cpp_cli_binary_evidence == [
        CCppCliBinaryEvidence(Path("src/tool.c"), ("getopt", "main"))
    ]
    assert cli_binary.evidence == (Path("src/tool.c"),)
    assert cli_binary.confidence == 0.8


def test_c_cpp_cli_binary_ignores_main_inside_comments_and_strings(
    tmp_path: Path,
) -> None:
    touch(
        tmp_path / "src" / "helper.c",
        "// int main(int argc, char **argv) { return 0; }\n"
        'const char *example = "int main(int argc, char **argv) { return 0; }";\n'
        "int helper(void) { return 0; }\n",
    )

    summary = scan_repository(tmp_path)

    assert summary.c_cpp_cli_binary_evidence == []
    assert not any(
        detection.kind == "Executable Target" and detection.name == "CLI Binary"
        for detection in summary.detections
    )


def test_makefile_targets_are_not_cli_binaries(tmp_path: Path) -> None:
    touch(tmp_path / "Makefile", "app: main.o\nclean:\n")

    summary = scan_repository(tmp_path)

    find_detection(summary.detections, "Build Target", "app")
    assert not any(
        detection.kind == "Executable Target" and detection.name == "CLI Binary"
        for detection in summary.detections
    )


def test_c_cpp_project_classification_detects_mixed_projects(tmp_path: Path) -> None:
    touch(tmp_path / "src" / "main.c")
    touch(tmp_path / "src" / "engine.cpp")

    summary = scan_repository(tmp_path)

    find_detection(summary.detections, "C/C++ Project", "Mixed C/C++ project")


def test_c_cpp_project_classification_detects_library_like_projects(
    tmp_path: Path,
) -> None:
    touch(tmp_path / "src" / "platform.cpp")
    touch(tmp_path / "include" / "platform.hpp")
    touch(tmp_path / "CMakeLists.txt", "add_library(platform STATIC platform.cpp)\n")

    summary = scan_repository(tmp_path)

    find_detection(summary.detections, "C/C++ Project", "Library-like C/C++ project")


def test_python_api_components_are_detected_from_framework_patterns(
    tmp_path: Path,
) -> None:
    touch(
        tmp_path / "app" / "main.py",
        "from fastapi import FastAPI, APIRouter\n"
        "app = FastAPI()\n"
        "router = APIRouter()\n"
        '@app.get("/health")\n'
        "def health(): pass\n"
        "# Flask()\n",
    )

    summary = scan_repository(tmp_path)

    fastapi = find_detection(summary.detections, "API", "FastAPI API")
    routes = find_detection(summary.detections, "API", "Python API routes")
    router = find_detection(summary.detections, "API", "API Router")

    assert fastapi.evidence == (Path("app/main.py"),)
    assert routes.evidence == (Path("app/main.py"),)
    assert router.evidence == (Path("app/main.py"),)
    assert not any(
        detection.kind == "API" and detection.name == "Flask API"
        for detection in summary.detections
    )


def test_database_cache_docker_and_test_components_are_detected(
    tmp_path: Path,
) -> None:
    touch(tmp_path / "app" / "db.py", "import sqlalchemy\nimport psycopg\n")
    touch(tmp_path / "app" / "sqlite_store.py", "import sqlite3\n")
    touch(tmp_path / "app" / "cache.py", "from redis import Redis\nRedis.from_url(url)\n")
    touch(tmp_path / "app" / "models.py")
    touch(tmp_path / "migrations" / "001_init.sql")
    touch(tmp_path / "alembic" / "env.py")
    touch(tmp_path / "Dockerfile")
    touch(tmp_path / "docker-compose.yml")
    touch(tmp_path / "tests" / "test_app.py", "import pytest\n")

    summary = scan_repository(tmp_path)

    database = find_detection(summary.detections, "Database", "Database")
    postgres = find_detection(summary.detections, "Database", "PostgreSQL")
    sqlite = find_detection(summary.detections, "Database", "SQLite")
    cache = find_detection(summary.detections, "Cache", "Redis Cache")
    docker = find_detection(summary.detections, "Docker", "Docker")
    compose = find_detection(summary.detections, "Docker", "Docker Compose")
    tests = find_detection(summary.detections, "Tests", "Test Suite")

    assert Path("app/models.py") in database.evidence
    assert Path("migrations") in database.evidence
    assert Path("alembic") in database.evidence
    assert postgres.evidence == (Path("app/db.py"),)
    assert sqlite.evidence == (Path("app/sqlite_store.py"),)
    assert cache.evidence == (Path("app/cache.py"),)
    assert docker.evidence == (Path("Dockerfile"),)
    assert compose.evidence == (Path("docker-compose.yml"),)
    assert Path("tests") in tests.evidence
    assert Path("tests/test_app.py") in tests.evidence


def test_component_detectors_ignore_default_ignored_directories(tmp_path: Path) -> None:
    touch(tmp_path / "venv" / "api.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    touch(tmp_path / "coverage" / "Dockerfile")
    touch(tmp_path / "build" / "cache.py", "import redis\n")

    summary = scan_repository(tmp_path)

    assert summary.scanned_files == 0
    assert summary.detections == []


def test_scan_repository_detects_notable_files(tmp_path: Path) -> None:
    touch(tmp_path / "Makefile")
    touch(tmp_path / "src" / "CMakeLists.txt")
    touch(tmp_path / "deploy" / "Dockerfile")
    touch(tmp_path / "docker-compose.yml")
    touch(tmp_path / "compile_commands.json")

    summary = scan_repository(tmp_path)

    assert summary.notable_files == [
        Path("Makefile"),
        Path("compile_commands.json"),
        Path("deploy/Dockerfile"),
        Path("docker-compose.yml"),
        Path("src/CMakeLists.txt"),
    ]


def test_empty_repository_summary_has_empty_states(tmp_path: Path) -> None:
    summary = scan_repository(tmp_path)
    output = format_summary(summary)

    assert summary.scanned_files == 0
    assert summary.languages == {}
    assert summary.notable_files == []
    assert summary.c_cpp_sources == []
    assert summary.c_cpp_headers == []
    assert summary.c_cpp_project_shape.looks_like_project is False
    assert summary.c_cpp_project_shape.build_files == []
    assert summary.c_cpp_project_shape.conventional_dirs == []
    assert summary.c_cpp_local_includes == []
    assert summary.c_cpp_build.makefiles == []
    assert summary.c_cpp_build.cmake_files == []
    assert summary.c_cpp_build.compile_commands_files == []
    assert summary.c_cpp_build.make_targets == []
    assert summary.c_cpp_build.cmake_targets == []
    assert summary.c_cpp_build.cmake_executable_targets == []
    assert summary.c_cpp_build.cmake_library_targets == []
    assert summary.c_cpp_systems_patterns == []
    assert summary.c_cpp_cli_binary_evidence == []
    assert summary.detections == []
    assert "Languages:\n  None" in output
    assert "Notable files:\n  None" in output
    assert "C/C++ files:\n  Sources: 0\n    None\n  Headers: 0\n    None" in output
    assert (
        "C/C++ build files:\n"
        "  Makefiles:\n"
        "    None\n"
        "  CMake files:\n"
        "    None\n"
        "  Compile commands:\n"
        "    None\n"
        "  Make targets:\n"
        "    None\n"
        "  CMake targets:\n"
        "    None"
    ) in output
    assert (
        "C/C++ project shape:\n"
        "  Looks like C/C++ project: No\n"
        "  Evidence:\n"
        "    Source files: 0\n"
        "    Header files: 0\n"
        "    Build files:\n"
        "      None\n"
        "    Conventional directories:\n"
        "      None"
    ) in output
    assert "C/C++ local includes:\n  Relationships: 0\n    None" in output
    assert "C/C++ systems patterns:\n  None" in output
    assert "Detected components:\n  None" in output
