from pathlib import Path

from typer.testing import CliRunner

from archgen import app


runner = CliRunner()


def test_cli_prints_repository_summary(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.cpp").write_text(
        '#include "platform.h"\n'
        "socket(); read(); pthread_create();\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "platform.c").write_text("malloc();\n", encoding="utf-8")
    (tmp_path / "include").mkdir()
    (tmp_path / "include" / "platform.h").write_text("", encoding="utf-8")
    (tmp_path / "Makefile").write_text("app: main.o\n", encoding="utf-8")
    (tmp_path / "src" / "CMakeLists.txt").write_text(
        "add_executable(app main.cpp)\n",
        encoding="utf-8",
    )
    (tmp_path / "Dockerfile").write_text("", encoding="utf-8")

    result = runner.invoke(app, [str(tmp_path)])

    assert result.exit_code == 0
    assert "Architecture Summary" in result.stdout
    assert f"Root: {tmp_path.resolve()}" in result.stdout
    assert "Scanned files: 7" in result.stdout
    assert "Python: 1" in result.stdout
    assert "Dockerfile" in result.stdout
    assert (
        "C/C++ files:\n"
        "  Sources: 2\n"
        "    src/main.cpp\n"
        "    src/platform.c\n"
        "  Headers: 1\n"
        "    include/platform.h"
    ) in result.stdout
    assert (
        "C/C++ project shape:\n"
        "  Looks like C/C++ project: Yes\n"
        "  Evidence:\n"
        "    Source files: 2\n"
        "    Header files: 1\n"
        "    Build files:\n"
        "      Makefile\n"
        "      src/CMakeLists.txt\n"
        "    Conventional directories:\n"
        "      include/\n"
        "      src/"
    ) in result.stdout
    assert (
        "C/C++ build files:\n"
        "  Makefiles:\n"
        "    Makefile\n"
        "  CMake files:\n"
        "    src/CMakeLists.txt\n"
        "  Compile commands:\n"
        "    None\n"
        "  Make targets:\n"
        "    Makefile -> app\n"
        "  CMake targets:\n"
        "    src/CMakeLists.txt -> app"
    ) in result.stdout
    assert (
        "C/C++ local includes:\n"
        "  Relationships: 1\n"
        "    src/main.cpp -> platform.h"
    ) in result.stdout
    assert (
        "C/C++ systems patterns:\n"
        "  Sockets:\n"
        "    src/main.cpp -> socket\n"
        "  Threads:\n"
        "    src/main.cpp -> pthread_create\n"
        "  File I/O:\n"
        "    src/main.cpp -> read\n"
        "  Memory/process:\n"
        "    src/platform.c -> malloc"
    ) in result.stdout


def test_cli_rejects_missing_path(tmp_path: Path) -> None:
    result = runner.invoke(app, [str(tmp_path / "missing")])

    assert result.exit_code != 0
    assert "does not exist" in result.stderr
