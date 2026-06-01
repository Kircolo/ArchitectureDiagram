from pathlib import Path
from typing import Annotated

import typer

from archgen.graph_builder import build_architecture_graph
from archgen.renderers.mermaid import render_mermaid
from archgen.scanner import scan_repository
from archgen.summary import format_summary


app = typer.Typer(add_completion=False, no_args_is_help=False)
DEFAULT_OUTPUT_PATH = Path("docs/architecture.mmd")
DETECTION_KIND_ORDER = (
    "API",
    "Database",
    "Cache",
    "Tests",
    "C/C++ Project",
    "C/C++ Module",
    "Executable Target",
    "Build Target",
    "C/C++ Systems Pattern",
    "Docker",
)


@app.command()
def cli(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
            help="Repository path to scan.",
        ),
    ] = Path("."),
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Mermaid output path. Relative paths are resolved from the scanned repository root.",
        ),
    ] = DEFAULT_OUTPUT_PATH,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print Mermaid output without writing a file.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Print detailed detection evidence after the normal output.",
        ),
    ] = False,
) -> None:
    summary = scan_repository(path)
    graph = build_architecture_graph(summary)
    mermaid = render_mermaid(graph)

    if dry_run:
        typer.echo(mermaid, nl=False)
        return

    output_path = resolve_output_path(summary.root, output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(mermaid, encoding="utf-8")

    typer.echo(f"Generated {display_output_path(summary.root, output_path)}")
    typer.echo(f"Detected components: {detected_component_kinds(summary)}")

    if verbose:
        typer.echo()
        typer.echo(format_summary(summary))


def main() -> None:
    app()


def resolve_output_path(root: Path, output: Path) -> Path:
    if output.is_absolute():
        return output
    return root / output


def display_output_path(root: Path, output: Path) -> str:
    try:
        return output.relative_to(root).as_posix()
    except ValueError:
        return output.as_posix()


def detected_component_kinds(summary) -> str:
    kinds = {detection.kind for detection in summary.detections}
    if not kinds:
        return "None"

    ordered = [kind for kind in DETECTION_KIND_ORDER if kind in kinds]
    ordered.extend(sorted(kinds - set(ordered)))
    return ", ".join(ordered)
