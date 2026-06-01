from pathlib import Path

from typer.testing import CliRunner

from archgen import app


runner = CliRunner()


def touch(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_cli_writes_default_mermaid_output(tmp_path: Path) -> None:
    touch(
        tmp_path / "app" / "main.py",
        "from fastapi import FastAPI\napp = FastAPI()\n",
    )
    touch(tmp_path / "app" / "db.py", "import psycopg\n")
    touch(tmp_path / "app" / "cache.py", "import redis\n")
    touch(tmp_path / "tests" / "test_app.py", "import pytest\n")

    result = runner.invoke(app, [str(tmp_path)])

    assert result.exit_code == 0
    assert result.stdout == (
        "Generated docs/architecture.mmd\n"
        "Detected components: API, Database, Cache, Tests\n"
    )

    output = tmp_path / "docs" / "architecture.mmd"
    assert output.read_text(encoding="utf-8").startswith("flowchart TD\n")
    assert 'api_fastapi_api["FastAPI API"]' in output.read_text(encoding="utf-8")
    assert 'database_postgresql[("PostgreSQL")]' in output.read_text(encoding="utf-8")
    assert "api_fastapi_api --> database_postgresql" in output.read_text(
        encoding="utf-8"
    )


def test_cli_writes_custom_output_relative_to_repository_root(tmp_path: Path) -> None:
    touch(tmp_path / "app.py", "print('hello')\n")

    result = runner.invoke(
        app,
        [str(tmp_path), "--output", "artifacts/architecture.mmd"],
    )

    assert result.exit_code == 0
    assert result.stdout == (
        "Generated artifacts/architecture.mmd\n"
        "Detected components: None\n"
    )
    assert (tmp_path / "artifacts" / "architecture.mmd").read_text(
        encoding="utf-8"
    ) == "flowchart TD\n"


def test_cli_dry_run_prints_mermaid_without_writing_file(tmp_path: Path) -> None:
    touch(
        tmp_path / "app" / "main.py",
        "from fastapi import FastAPI\napp = FastAPI()\n",
    )

    result = runner.invoke(app, [str(tmp_path), "--dry-run"])

    assert result.exit_code == 0
    assert result.stdout.startswith("flowchart TD\n")
    assert 'api_fastapi_api["FastAPI API"]' in result.stdout
    assert "Generated" not in result.stdout
    assert not (tmp_path / "docs" / "architecture.mmd").exists()


def test_cli_verbose_prints_summary_after_success_message(tmp_path: Path) -> None:
    touch(tmp_path / "main.py")

    result = runner.invoke(app, [str(tmp_path), "--verbose"])

    assert result.exit_code == 0
    assert result.stdout.startswith(
        "Generated docs/architecture.mmd\n"
        "Detected components: None\n\n"
        "Architecture Summary\n"
    )
    assert f"Root: {tmp_path.resolve()}" in result.stdout
    assert "Scanned files: 1" in result.stdout


def test_cli_rejects_missing_path(tmp_path: Path) -> None:
    result = runner.invoke(app, [str(tmp_path / "missing")])

    assert result.exit_code != 0
    assert "does not exist" in result.stderr
