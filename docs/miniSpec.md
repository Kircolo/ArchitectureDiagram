# Architecture Diagram Generator Spec

Repo name: archdia
CLI/package name: archgen

Goal:
Build a Python CLI tool that scans a local repository and generates Mermaid architecture diagrams.

MVP order:
1. Scanner and file/language summary.
2. C/C++ file detection.
3. Local include detection.
4. Makefile/CMake detection.
5. Systems-pattern detection: sockets, pthreads, queues, synchronization, file I/O.
6. Graph model.
7. Mermaid renderer.
8. Markdown output.
9. Python/FastAPI detection.
10. Database/cache/test/Docker detection.

Initial command:
archgen PATH

## Current Baseline: Milestone 1 Complete

The project already has a working `archgen` CLI using `uv` and a `src/` layout.

Current behavior:
- `uv run archgen .` scans a repository recursively.
- Common default directories are ignored:
  - `.git`
  - `.venv`
  - `__pycache__`
  - `.pytest_cache`
  - `build`
  - `dist`
  - `target`
  - `vendor`
- Scanned files are counted.
- Common languages are detected from extensions.
- Notable files are detected:
  - `Makefile`
  - `CMakeLists.txt`
  - `Dockerfile`
  - `docker-compose.yml`
  - `docker-compose.yaml`
  - `compose.yml`
  - `compose.yaml`
  - `compile_commands.json`
- The CLI prints a stable plain-text summary.
- Pytest tests exist and pass.

Important files:
- `src/archgen/__init__.py`
- `src/archgen/scanner.py`
- `tests/test_scanner.py`
- `tests/test_cli.py`

Acceptance for current baseline:
- `uv run pytest`
- `uv run archgen .`

## Milestone 2 Breakdown

The full product spec describes Milestone 2 broadly as "basic component detection."
For implementation, split that large milestone into smaller sub-milestones so each agent can implement and test one useful slice at a time.

Do not implement all of Milestone 2 at once.

## Milestone 2A - Explicit C/C++ Source/Header Detection

Goal:
Make C/C++ file detection explicit by classifying C/C++ sources separately from headers.

This is a narrow scanner enhancement. It should not parse file contents or infer architecture yet.

Add source detection for:
- `.c`
- `.cc`
- `.cpp`
- `.cxx`

Add header detection for:
- `.h`
- `.hh`
- `.hpp`
- `.hxx`

Implementation requirements:
- Extend the scanner summary model with separate C/C++ source and header file lists.
- Store C/C++ file paths as relative paths.
- Sort C/C++ file paths for stable output.
- Keep the existing language count behavior.
- Keep the existing ignore rules.
- Do not parse file contents.
- Do not detect `#include` relationships yet.
- Do not infer build targets yet.
- Do not implement systems-pattern detection yet.
- Do not implement Python/API/database/cache/Docker/test component detection yet.
- Do not implement Mermaid rendering yet.
- Do not add a graph model yet.

Expected CLI output should add a section like:

```text
C/C++ files:
  Sources: 2
    src/main.cpp
    src/platform.c
  Headers: 1
    include/platform.h
```

If no C/C++ files are found, print:

```text
C/C++ files:
  Sources: 0
    None
  Headers: 0
    None
```

Tests to add or update:
- C/C++ source files are detected.
- C/C++ header files are detected.
- C/C++ files inside ignored directories are excluded.
- CLI output includes the C/C++ section.
- Existing Milestone 1 behavior still passes.

Milestone 2A acceptance:
- `uv run pytest` passes.
- `uv run archgen .` prints the existing summary plus the new C/C++ files section.

## 2B - C/C++ Project Shape Detection

Goal:
Detect whether a scanned repository looks like a C or C++ project using file types, notable build files, and conventional directories.

Implementation should detect evidence such as:
- C/C++ source and header files from Milestone 2A.
- `Makefile`
- `CMakeLists.txt`
- `compile_commands.json`
- conventional directories such as `src/`, `include/`, `lib/`, and `tests/`

Expected output may add a component/evidence-style section, but keep it plain text until a graph model exists.

Do not parse Makefile or CMake targets in this step.
Do not parse includes in this step.
Do not implement Mermaid rendering in this step.

## Milestone 2C - Local Include Detection

Goal:
Detect local C/C++ include relationships using simple static text scanning.

Implementation should detect statements like:
- `#include "queue.h"`
- `#include "http/parser.hpp"`

Requirements:
- Only scan C/C++ source and header files.
- Only treat quoted includes as local includes.
- Store relationships as simple data, not a full graph model yet.
- Report include relationships in plain text or in scanner data for later graph work.

Do not attempt compiler-accurate include resolution.
Do not parse angle-bracket system includes yet.
Do not build Mermaid output yet.

##  Milestone 2D - Makefile/CMake Build Detection

Goal:
Detect basic build structure from Makefile and CMake files.

Implementation should start simple:
- Identify presence of `Makefile`.
- Identify presence of `CMakeLists.txt`.
- Optionally extract obvious target names using conservative heuristics.
- Preserve evidence paths.

Do not try to fully evaluate Make syntax or CMake scripts.
Do not infer runtime architecture yet.

## Milestone 2E - C/C++ Systems-Pattern Detection

Goal:
Detect common systems-programming concepts through simple content heuristics.

Initial patterns may include:
- sockets: `socket`, `bind`, `listen`, `accept`, `connect`, `send`, `recv`
- threads: `pthread_create`, `pthread_join`, `pthread_mutex`, `pthread_cond`
- synchronization: `sem_wait`, `sem_post`, mutexes, condition variables
- file I/O: `open`, `read`, `write`, `fopen`, `fread`, `fwrite`
- memory/process hints: `malloc`, `free`, `fork`, `exec`, `pipe`

Output should remain evidence-oriented and plain text until graph rendering exists.
Do not implement deep static analysis or call graphs.

Project constraints:
- Use `uv`.
- Keep code simple.
- Keep the `src/` layout.
- Use pytest.
- Do not create temporary files outside this repo.
- If scratch files are needed, place them under this repo and clearly state the path.
