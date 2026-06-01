# Milestone 1-3 Audit Handoff

This is the consolidated handoff for Milestones 1 through 3 from
`docs/fullSpec.md`. It reflects the current audited state of the repo

## Current State

The project has a working `archgen` CLI with a `src/` layout, detector modules,
graph generation, Mermaid output, and pytest coverage.

Verified during the latest audits:

```bash
uv run pytest --basetemp=.tmp/pytest
uv run archgen . --output .tmp/audit-m3/architecture.mmd --verbose
```

Temporary output must stay inside the repo under `.tmp/`; do not use
`/private/tmp`.

The scanner now ignores `.tmp/`, so repo-local scratch output does not pollute
future `archgen .` runs.

## Milestone 1 Status

Milestone 1 is complete.

Covered behavior:

- CLI entry point exists.
- Repository scanning is recursive.
- Default ignore rules include `.git`, `.venv`, `venv`, `__pycache__`,
  `.pytest_cache`, `dist`, `build`, and `coverage`.
- Scanner counts supported languages and records notable files.
- `.env.example` is handled as a notable file, not as a language.
- Summary output is available through `--verbose`.
- Tests cover the scanner basics, ignore rules, language counting, and
  `.env.example`.

## Milestone 2 Status

Milestone 2 is almost complete, but should not be marked done until the CLI
binary gap below is fixed. This is the only known required Milestone 1-3 work
remaining after the audit.

Implemented detector coverage:

- C/C++ project detector.
- Source/header module detector for same-stem pairs such as `queue.c` and
  `queue.h`.
- Makefile, CMake, and `compile_commands.json` detection.
- Conservative Makefile target extraction.
- CMake executable and library target extraction.
- C/C++ systems-pattern detection for sockets, threads, synchronization,
  queues, file I/O, and memory/process hints.
- Python API detector for FastAPI, Flask, APIRouter, and simple route calls.
- Database detector for SQLAlchemy-style evidence, PostgreSQL, SQLite,
  `models.py`, `migrations/`, and `alembic/`.
- Redis/cache detector.
- Docker and Docker Compose detector.
- Test-suite detector.
- Detectors ignore files in default ignored directories.

Important files:

- `src/archgen/scanner.py`
- `src/archgen/detection.py`
- `src/archgen/detectors/c_cpp.py`
- `src/archgen/detectors/python_api.py`
- `src/archgen/detectors/database.py`
- `src/archgen/detectors/cache.py`
- `src/archgen/detectors/docker.py`
- `src/archgen/detectors/tests.py`
- `tests/test_scanner.py`
- `tests/test_cli.py`

## Milestone 2 Remaining Work

### Required: CLI Binary Detection

The full spec says Milestone 2 includes systems-pattern detection for sockets,
threads, synchronization, file I/O, and CLI binaries.

Current behavior only partially covers binaries:

- `main.c` or `main.cpp` helps classify a project as a C/C++ application.
- CMake `add_executable(...)` creates an `Executable Target` detection.
- Makefile targets create low-confidence `Build Target` detections.

Missing behavior:

- A plain C/C++ CLI project with `main(int argc, char **argv)` but no CMake
  executable does not get a clear CLI/binary component.
- There is no explicit `CLI Binary` or equivalent detection based on `main`,
  `argc`, `argv`, option parsing, or executable-target evidence.

Suggested implementation:

- Add a conservative CLI/binary detector in the C/C++ path.
- Evidence can include:
  - `main(...)` in a C/C++ source file.
  - `argc` / `argv` in the same source file.
  - common option parsing evidence such as `getopt`, `getopt_long`, or
    `--help`.
  - CMake executable targets.
- Keep the output evidence-oriented. Avoid claiming a CLI when evidence is only
  a generic helper function named `main` in comments or strings.
- Prefer a detection such as:

```python
Detection(
    kind="Executable Target",
    name="CLI Binary",
    evidence=(Path("src/main.c"),),
    confidence=0.75,
)
```

Exact naming can differ if it fits the existing graph output better. The
important requirement is that this is visibly distinct from a generic Makefile
`Build Target`.

Tests to add:

- Detects a CLI binary from `int main(int argc, char **argv)`.
- Detects CLI option parsing evidence such as `getopt(...)`.
- Ignores `main` inside comments and strings if practical.
- Does not mark every Makefile target as a CLI binary.
- Existing CMake `add_executable(...)` behavior still passes.

## Milestone 3 Status

Milestone 3 is complete after the `.tmp` scanner ignore fix.

Covered behavior:

- Graph model exists in `src/archgen/graph.py`.
- Graph builder exists in `src/archgen/graph_builder.py`.
- Mermaid renderer exists in `src/archgen/renderers/mermaid.py`.
- CLI writes Mermaid output to `docs/architecture.mmd` by default.
- CLI supports `--output`, `--dry-run`, and `--verbose`.
- Relative output paths are resolved from the scanned repository root.
- Mermaid output starts with `flowchart TD`, renders nodes before edges, escapes
  labels, uses cylinders for database/cache nodes, and has stable ordering.
- Tests cover graph building, Mermaid rendering, and CLI output behavior.

No Milestone 3 implementation work is currently required.

## Nice-To-Have Cleanup

These are not required to close Milestone 2, but are worth keeping in mind:

- Split build-target parsing out of `scanner.py` if it grows further.
- Add detector-specific tests in addition to scanner-level integration tests.
- Consider tuple fields for frozen dataclasses that currently contain mutable
  lists.
- Keep endpoint extraction, Markdown docs, and config overrides out of this
  milestone.

## Exact Remaining Work

To finish the audited Milestone 1-3 scope:

1. Implement explicit C/C++ CLI binary detection.
2. Add focused scanner/detector tests for that behavior.
3. Run `uv run pytest --basetemp=.tmp/pytest`.
4. Run `uv run archgen . --output .tmp/audit-m2/architecture.mmd --verbose`.
5. Confirm output still includes a clear `Detected components:` summary.

After those are done, Milestones 1, 2, and 3 can be considered complete.
