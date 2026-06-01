from pathlib import Path
from typing import Annotated

import typer

from archgen.scanner import scan_repository
from archgen.summary import format_summary


app = typer.Typer(add_completion=False, no_args_is_help=False)


@app.callback(invoke_without_command=True)
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
) -> None:
    summary = scan_repository(path)
    typer.echo(format_summary(summary))


def main() -> None:
    app()
