# Architecture Diagram Generator Mini Spec

Repo name: `archdia`
CLI/package name: `archgen`

Goal:
Build a Python CLI tool that scans a local repository and generates Mermaid architecture diagrams.

This mini spec is a handoff for Milestone 4 from `docs/fullSpec.md`: C/C++ architecture extraction.

## Source of Truth

Read and follow:
- `docs/AGENTS.md`
- `docs/fullSpec.md`

Relevant full spec sections:
- `8.2 Component detection`
- `8.4 Graph generation`
- `8.5 Mermaid rendering`
- `14. Example Output for a C Multithreaded HTTP Server Project`
- `15. Testing Strategy`
- `16. Milestone 4: C/C++ architecture extraction`
- `17. MVP Acceptance Criteria`

## Project Constraints

From `docs/AGENTS.md`:
- Use `uv`.
- Run tests with `uv run pytest`.
- Run the CLI with `uv run archgen .`.
- Prefer small, simple modules.
- Use dataclasses for core models.
- Keep detectors modular.
- Avoid heavy dependencies unless asked.
- Favor practical heuristics over deep static analysis.
- Do not add a web UI.
- Do not add AI/LLM features yet.
- Keep implementation focused on C/C++ systems projects and Python backend projects.

Done means:
- tests pass
- `uv run archgen .` works
- the diff is small enough to review
- new behavior is covered by at least one test when practical

## Current Baseline

Milestones 4A through 4C are implemented.

Current behavior:
- `uv run archgen PATH` scans a repository.
- The CLI writes Mermaid output to `docs/architecture.mmd` by default.
- The CLI supports `--output`, `--dry-run`, and `--verbose`.
- The scanner detects C/C++ files, local quoted includes, resolved local includes, Makefile/CMake targets, target source evidence, CLI binaries, and broad systems-pattern evidence.
- Component detections include C/C++ projects, grouped C/C++ modules, executable/library/build targets, C/C++ systems patterns, Python API/database/cache/Docker/tests.
- The graph model, graph builder, and Mermaid renderer exist.
- Build target to module edges are evidence-based when target source evidence overlaps module evidence.

Important files:
- `src/archgen/scanner.py`
- `src/archgen/detectors/c_cpp.py`
- `src/archgen/graph_builder.py`
- `src/archgen/summary.py`
- `tests/test_scanner.py`
- `tests/test_graph.py`

## Milestone 4 Goal

Generate useful diagrams for C/C++ systems projects.

Full spec deliverables:
- Include graph extraction from local headers.
- Makefile/CMake target extraction.
- Module grouping by folder and filename.
- Detection for socket servers, worker threads, queues, locks, file I/O, and encode/decode pipelines.
- Mermaid diagrams for C/C++ project fixtures.

Continue Milestone 4 in reviewable parts. 4A-4C are complete; the next agent should start with 4D.

## Completed: Milestone 4A - 4C

4A resolved local quoted includes:
- Added `CCppResolvedInclude`.
- Resolves local includes through source directory, repo-relative paths, `include/`, `src/`, `lib/`, and unique header basename fallback.
- Preserves `resolved`, `unresolved`, and `ambiguous` statuses.
- Shows resolved include evidence in verbose summary.

4B improved C/C++ module grouping:
- Pairs source/header files across root, `src/`, `include/`, and nested paths.
- Emits folder-level modules for cohesive multi-file folders.
- Adds conservative source-only modules for systems/utility evidence.
- Adds conservative header-only modules for public `include/` headers.
- Keeps file-level modules inside cohesive folders as a future detail-level option.

4C mapped build targets to module evidence:
- CMake parser extracts literal source/header arguments from simple one-line and multi-line `add_executable()` and `add_library()` calls.
- Makefile parser maps object prerequisites such as `queue.o` to scanned source files when unambiguous.
- Build target detections preserve target kind, build file evidence, and source file evidence.
- Graph target-to-module edges now use shared evidence instead of broad target-to-all-module edges.

Validation at completion:
- `uv run pytest` passed.
- `uv run archgen .` worked.
- Changes were committed and pushed to `origin/main` as `9876821 Implement C/C++ milestone 4A-4C extraction`.

## Milestone 4D - Systems Component Refinement

Goal:
Turn broad systems-pattern evidence into architecture components that read like a useful systems diagram.

Current baseline:
- Systems detections are category-level:
  - `Sockets`
  - `Threads`
  - `Synchronization`
  - `Queues`
  - `File I/O`
  - `Memory/process`

Implementation requirements:
- Keep the existing broad categories if they are useful, but add or refine component names when evidence supports them.
- Suggested component labels:
  - `Socket Listener`
  - `Client Socket`
  - `Worker Thread Pool`
  - `Shared Queue`
  - `Synchronization Layer`
  - `File Storage`
  - `Process Manager`
  - `Encoder`
  - `Decoder`
  - `Bit I/O`
- Use simple heuristics based on:
  - API calls
  - filename and directory names
  - module names
  - paired evidence across source/header files
- Examples:
  - `socket`, `bind`, `listen`, and `accept` in the same module can imply `Socket Listener`.
  - `pthread_create` plus queue evidence can imply `Worker Thread Pool`.
  - queue APIs or filenames can imply `Shared Queue`.
  - `open`, `read`, `write`, `fopen`, `fread`, or `fwrite` can imply `File Storage` or `File I/O`.
  - filenames containing `encode`, `decode`, `compress`, `decompress`, `bitreader`, or `bitwriter` can imply pipeline components.
- Preserve evidence paths.
- Do not implement call graphs or runtime control-flow analysis.
- Avoid false precision. Prefer a lower confidence score when evidence is weak.

Tests to add:
- socket server evidence creates `Socket Listener`
- pthread worker evidence creates `Worker Thread Pool`
- queue evidence creates `Shared Queue`
- file I/O evidence creates file storage or file I/O component
- encode/decode filenames create pipeline components
- comments and string literals remain ignored
- ambiguous weak evidence does not create misleading components

Milestone 4D acceptance:
- `uv run pytest` passes.
- C systems diagrams have readable systems component labels.
- Existing broad evidence remains available in verbose summary or detections.

## Milestone 4E - C/C++ Graph Assembly Rules

Goal:
Use include, module, build-target, and systems evidence to generate more useful C/C++ Mermaid diagrams.

Current baseline:
- Graph nodes are created from detections.
- Current C/C++ edges include:
  - `C/C++ Project -> C/C++ Module`
  - `C/C++ Project -> Executable Target`
  - evidence-based target -> module edges for executable/library/build targets
  - `C/C++ Module -> C/C++ Systems Pattern` when evidence files overlap

Implementation requirements:
- Add include-derived module edges:
  - module A includes module B
  - source/header file A includes file B
- Preserve and refine existing build-derived target edges.
- Add systems-derived edges:
  - module -> systems component when evidence overlaps
  - target -> systems component when the target owns the module evidence
- Prefer specific evidence-based edges over broad all-to-all edges.
- Add edge labels only when they improve clarity, such as `includes` or `uses`.
- Keep graph output deterministic.
- Keep Mermaid syntax valid.
- Avoid clutter:
  - do not render every include if it creates noisy duplicate relationships
  - de-duplicate edges
  - collapse file-level detail into module-level edges where possible

Tests to add:
- include relationships create module edges
- build target sources create target-to-module edges
- systems evidence creates module-to-component edges
- duplicate edges are removed
- graph output remains sorted and stable
- Mermaid output starts with `flowchart TD` and contains expected C/C++ edges

Milestone 4E acceptance:
- `uv run pytest` passes.
- Generated C/C++ Mermaid diagrams show specific architecture relationships instead of only broad project-to-module edges.

## Milestone 4F - C/C++ Fixture and Snapshot Coverage

Goal:
Prove Milestone 4 behavior on small realistic C/C++ fixture projects.

Implementation requirements:
- Add focused fixtures under `tests/fixtures/`.
- Keep fixtures small enough to review.
- Add snapshot-style tests for generated Mermaid where practical.
- Prefer expected key-node/key-edge assertions if full snapshots become brittle.

Recommended fixtures:
- `tests/fixtures/c_http_server/`
  - `src/main.c`
  - `src/server.c`
  - `src/http.c`
  - `src/queue.c`
  - `src/threadpool.c`
  - `src/storage.c`
  - matching headers under `include/`
  - Makefile or CMakeLists.txt
- `tests/fixtures/c_cli_encoder_decoder/`
  - encoder/decoder modules
  - bit reader/writer modules
  - file I/O evidence
  - Makefile
- `tests/fixtures/cpp_cmake_project/`
  - CMake executable target
  - CMake library target
  - source/header modules

Tests to add:
- CLI generates Mermaid for each fixture.
- Mermaid contains expected nodes.
- Mermaid contains expected architecture edges.
- Existing Python/backend tests still pass.

Milestone 4F acceptance:
- `uv run pytest` passes.
- Fixture diagrams are useful enough to inspect manually.
- `uv run archgen tests/fixtures/c_http_server --dry-run` prints a valid Mermaid diagram.

## Recommended Implementation Order

Recommended next agent task:
1. Implement Milestone 4D only.
2. Run `uv run pytest`.
3. Run `uv run archgen .`.
4. Stop and report what changed.

Then continue in this order:
1. 4D - systems component refinement
2. 4E - graph assembly rules
3. 4F - fixtures and snapshots

Each sub-milestone should be independently reviewable.

## Overall Milestone 4 Acceptance

Milestone 4 is complete when:
- `uv run pytest` passes.
- `uv run archgen .` works.
- A C HTTP server fixture produces a Mermaid diagram with recognizable server, listener, parser, queue, worker, and storage components.
- A C CLI encoder/decoder fixture produces a Mermaid diagram with recognizable binary, encoder/decoder, bit I/O, and file I/O components.
- A C++ CMake fixture produces a Mermaid diagram with executable/library target relationships.
- Include-derived module relationships are represented.
- Build target relationships are represented when evidence exists.
- Systems-pattern relationships are represented without pretending to be a full call graph.
- Output remains stable and deterministic.

## Out of Scope for Milestone 4

Do not implement:
- REST endpoint extraction.
- Markdown architecture docs.
- Config overrides.
- SVG export.
- Tree-sitter or compiler-accurate parsing.
- Full C/C++ call graphs.
- Full Makefile or CMake evaluation.
- System include graphing for angle-bracket includes.
- Python detector changes unless required to keep tests passing.
- Web UI or AI/LLM features.

## Future Tasks

- Optional file-level C/C++ module nodes: after folder-level grouping and graph assembly are stable, consider a detail-level option that emits file modules inside cohesive folders.
