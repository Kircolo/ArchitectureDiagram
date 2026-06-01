# Milestone 1 and 2 Follow-Up Task

This document is a handoff for the next agent. It summarizes what still needs to be accomplished for Milestone 1 and Milestone 2, plus concerns about the current implementation and project structure.

## Current State

The project already has a working `archgen` CLI with a `src/` layout, pytest coverage, and a scanner-centered implementation.

Verified current commands:

```bash
uv run pytest
uv run archgen .
```

At the time of review, tests passed and the CLI produced a plain-text architecture summary.

The implementation has already gone beyond the narrow Milestone 2A task in `docs/miniSpec.md`. It includes:

- Recursive repository scanning.
- Default ignored directories.
- Language counting by file extension.
- Notable file detection.
- Explicit C/C++ source and header lists.
- C/C++ project-shape evidence.
- Quoted local include detection.
- Makefile, CMake, and `compile_commands.json` detection.
- Conservative Makefile and CMake target extraction.
- C/C++ systems-pattern text heuristics.

## Milestone 1 Remaining Work

Milestone 1 is mostly complete according to `docs/miniSpec.md`, but there are a few gaps if judged against `docs/fullSpec.md`.

### Required Follow-Up

- Add missing default ignored directories from the full spec:
  - `venv`
  - `coverage`
- Add missing file/language coverage from the full spec where appropriate:
  - `.env.example`
- Decide how `.env.example` should be represented in the summary. It is listed as an included input in the full spec, but it is not a normal extension-based language.
- Add tests for the missing ignore rules and input file types.

### Milestone 1 Definition of Done

- `uv run pytest` passes.
- `uv run archgen .` works.
- Scanner behavior matches the Milestone 1 requirements in both `miniSpec.md` and `fullSpec.md`, or the docs are updated to clearly explain the narrower baseline.

## Milestone 2 Remaining Work

Milestone 2 in `docs/fullSpec.md` is broader than the current implementation. The current code covers part of the C/C++ slice, but does not yet cover full basic component detection.

### C/C++ Work Still Needed

- Convert current C/C++ evidence into explicit component-style detections.
  - Current output is scanner evidence, not a real "Detected components" model.
- Add a source/header module detector.
  - Pair files such as `queue.c` and `queue.h`.
  - Recognize source/header families across `src/` and `include/`.
- Improve C/C++ project classification.
  - Distinguish C application, C++ application, mixed C/C++ project, library-like project, and executable-like project where possible.
- Improve Makefile and CMake detection.
  - Preserve current conservative behavior.
  - Avoid false positives from pattern rules, variable assignments, special targets, and generated targets.
  - Consider whether target extraction belongs in a build detector module instead of `scanner.py`.
- Add CLI binary or executable target detection.
  - CMake `add_executable(...)` is a good starting point.
  - Makefile targets may be evidence, but should be treated carefully.
- Expand systems-pattern detection to cover queues and CLI binaries if they are considered part of Milestone 2.
  - Current systems patterns cover sockets, pthreads, synchronization, file I/O, and memory/process hints.
  - Queue detection is not implemented as a distinct concept.
- Reduce false positives in systems-pattern scanning.
  - Current matching scans comments and string literals.
  - Prefix matching for patterns like `exec` may match unrelated words.

### Python/API Work Still Needed

- Add Python API/backend component detection.
  - `FastAPI(`
  - `Flask(`
  - `APIRouter(`
  - `app.get(`
  - `app.post(`
  - `router.get(`
  - `router.post(`
- Do not implement endpoint extraction unless the chosen scope explicitly includes it. Endpoint extraction is later in the full spec, but simple API component detection is part of Milestone 2.

### Database Work Still Needed

- Add database component detection from simple evidence:
  - `sqlalchemy`
  - `psycopg`
  - `asyncpg`
  - `sqlite3`
  - `models.py`
  - `migrations/`
  - `alembic/`
- Distinguish PostgreSQL and SQLite when there is clear evidence.

### Cache Work Still Needed

- Add Redis/cache detection from simple evidence:
  - `redis`
  - `aioredis`
  - `Redis.from_url`
  - related dependency or import references.

### Docker Work Still Needed

- Promote Docker from "notable file" evidence to component detection.
  - `Dockerfile`
  - `docker-compose.yml`
  - `docker-compose.yaml`
  - `compose.yml`
  - `compose.yaml`
- Keep service graph extraction out of scope unless explicitly requested.

### Test Work Still Needed

- Add test-suite component detection:
  - `tests/`
  - `test_*.py`
  - `*_test.py`
  - `pytest`
  - `unittest`
- Keep this as evidence-oriented detection for now.

## Suggested Implementation Direction

Before adding more features, split responsibilities out of `scanner.py`.

A reasonable next structure:

```text
src/archgen/
  scanner.py
  summary.py
  detectors/
    __init__.py
    c_cpp.py
    build.py
    systems.py
    python_api.py
    database.py
    cache.py
    docker.py
    tests.py
```

Keep the scanner responsible for walking files and collecting file metadata. Let detectors consume that metadata and return evidence or component records.

Suggested data model:

```python
@dataclass(frozen=True)
class Detection:
    kind: str
    name: str
    evidence: list[Path]
    confidence: float | None = None
```

This does not need to be the final graph model. It is enough to make Milestone 2 a real component-detection milestone without jumping ahead to Mermaid rendering.

## Code and Structure Concerns

### `scanner.py` Is Becoming Too Large

`scanner.py` currently handles:

- filesystem walking
- language detection
- notable file detection
- C/C++ file classification
- project-shape detection
- include scanning
- build target parsing
- systems-pattern scanning
- summary formatting

This is manageable now, but adding Python, database, cache, Docker, and test detection here will make the file harder to review and harder to test.

### Formatting Is Coupled to Scanning

`format_summary()` lives in `scanner.py` and knows about every scanner field. As output grows, this will make small detector changes create formatting churn.

Consider moving summary formatting to a separate module before expanding Milestone 2.

### Raw Text Heuristics Need Guardrails

The current text scans are intentionally simple, which is fine for the MVP. The risk is false confidence:

- comments can trigger systems-pattern matches
- strings can trigger systems-pattern matches
- words containing API names can trigger matches if boundaries are loose
- CMake detection only catches simple same-line target declarations
- Makefile target detection may report utility targets as executable-ish evidence

Keep the output evidence-oriented and avoid claiming runtime architecture too strongly.

### Frozen Dataclasses Contain Mutable Lists

Several dataclasses are `frozen=True` but contain `list[...]` fields. This prevents rebinding the attribute, but the list contents are still mutable. That is not a bug today, but it can surprise future code.

Consider using tuples for immutable summary fields if immutability matters.

### Tests Are Good but Mostly Scanner-Level

The current tests cover the existing scanner behavior well. As Milestone 2 expands, add detector-specific unit tests instead of only adding large CLI substring assertions.

Recommended test additions:

- missing Milestone 1 ignore directories
- `.env.example` handling
- Python API detection
- PostgreSQL/SQLite evidence detection
- Redis/cache evidence detection
- Docker component detection
- test-suite component detection
- no false positives from ignored directories
- no false positives from obvious comments or unrelated words where practical

## Recommended Task Order

1. Bring Milestone 1 into full-spec parity or explicitly document the narrower Milestone 1 baseline.
2. Split `scanner.py` enough to keep new detectors modular.
3. Add a small component/evidence model for Milestone 2 detections.
4. Move existing C/C++ evidence into detector modules without changing behavior.
5. Add missing C/C++ module, queue, and executable-target detection.
6. Add Python API, database, cache, Docker, and test detectors.
7. Update CLI summary output with a clear `Detected components:` section.
8. Add focused tests for each new detector.
9. Run `uv run pytest` and `uv run archgen .`.

## Out of Scope for This Task

- Graph model.
- Mermaid rendering.
- Markdown architecture document generation.
- Endpoint extraction tables.
- Config override support.
- Web UI.
- AI/LLM features.

Those belong to later milestones unless the project owner updates the spec.
