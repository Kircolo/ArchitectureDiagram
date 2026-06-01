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

The current workspace appears to have Milestones 1 through 3 implemented enough for Milestone 4 work.

Current behavior:
- `uv run archgen PATH` scans a repository.
- The CLI writes Mermaid output to `docs/architecture.mmd` by default.
- The CLI supports `--output`, `--dry-run`, and `--verbose`.
- The scanner detects:
  - C/C++ source files
  - C/C++ header files
  - C/C++ local quoted includes
  - Makefile and CMake files
  - simple Makefile target names
  - simple CMake target names
  - CMake executable and library targets
  - systems-pattern evidence for sockets, threads, synchronization, queues, file I/O, and memory/process hints
- Component detections exist for:
  - C/C++ projects
  - C/C++ modules
  - executable targets
  - build targets
  - C/C++ systems patterns
  - Python API, database, cache, Docker, and tests
- A graph model, graph builder, and Mermaid renderer exist.
- Existing C/C++ graph edges are intentionally conservative and broad.

Important files:
- `src/archgen/__init__.py`
- `src/archgen/scanner.py`
- `src/archgen/detection.py`
- `src/archgen/summary.py`
- `src/archgen/detectors/c_cpp.py`
- `src/archgen/graph.py`
- `src/archgen/graph_builder.py`
- `src/archgen/renderers/mermaid.py`
- `tests/test_scanner.py`
- `tests/test_graph.py`
- `tests/test_mermaid.py`
- `tests/test_cli.py`

## Milestone 4 Goal

Generate useful diagrams for C/C++ systems projects.

Full spec deliverables:
- Include graph extraction from local headers.
- Makefile/CMake target extraction.
- Module grouping by folder and filename.
- Detection for socket servers, worker threads, queues, locks, file I/O, and encode/decode pipelines.
- Mermaid diagrams for C/C++ project fixtures.

Do not implement all of Milestone 4 at once. Split it into the parts below.

## Milestone 4A - Resolved Local Include Graph

Goal:
Turn existing local include evidence into resolved file-to-file relationships.

Current baseline:
- `scan_repository()` already records `CCppLocalInclude(source, included_path)`.
- `included_path` is currently just the quoted string from `#include "..."`
- The graph builder does not yet use include relationships directly.

Implementation requirements:
- Only scan C/C++ source and header files.
- Only treat quoted includes as local includes.
- Resolve includes against simple, explainable candidates:
  - the including file's directory
  - repository-relative include paths
  - conventional include roots such as `include/`, `src/`, and `lib/`
  - unique basename matches among scanned C/C++ headers, if unambiguous
- Preserve unresolved includes as evidence or warnings instead of failing.
- Preserve ambiguous includes as warnings instead of guessing.
- Store resolved include relationships in structured data, preferably a dataclass.
- Keep paths relative to the repository root.
- Keep output sorted and stable.

Suggested model:

```python
@dataclass(frozen=True)
class CCppResolvedInclude:
    source: Path
    included_path: str
    resolved_path: Path | None
    status: str
```

Suggested statuses:
- `resolved`
- `unresolved`
- `ambiguous`

Tests to add:
- resolves includes next to the source file
- resolves includes through `include/`
- resolves nested includes such as `#include "http/parser.h"`
- resolves a unique basename include such as `#include "queue.h"`
- marks missing includes unresolved
- marks duplicate basename matches ambiguous
- ignores angle-bracket system includes
- ignores files in ignored directories

Milestone 4A acceptance:
- `uv run pytest` passes.
- `uv run archgen .` still works.
- Include resolution is covered by tests.
- No Mermaid behavior needs to change yet unless it is a small, low-risk addition.

## Milestone 4B - C/C++ Module Grouping

Goal:
Improve module detection so C/C++ diagrams are organized around useful project modules, not only exact source/header stem pairs.

Current baseline:
- `detect_source_header_modules()` creates a `C/C++ Module` only when source and header files have the same stem.

Implementation requirements:
- Group related C/C++ files by conservative heuristics:
  - source/header stem pairs such as `queue.c` and `queue.h`
  - paired paths across `src/` and `include/`, such as `src/http/parser.c` and `include/http/parser.h`
  - source-only modules when the source file has strong module evidence
  - header-only modules when the header file has strong interface evidence
  - folder-level modules for cohesive directories such as `src/net/`, `src/http/`, `src/storage/`
- Preserve evidence files for every module.
- Keep labels readable, for example `queue module`, `HTTP parser module`, or `storage module`.
- Keep IDs and output stable.
- Avoid deep static analysis.
- Avoid creating excessive nodes for every tiny file if a folder-level module is clearer.

Tests to add:
- source/header pairs produce one module
- `src/foo.c` pairs with `include/foo.h`
- nested `src/http/parser.c` pairs with `include/http/parser.h`
- source-only files can produce modules when appropriate
- folder-level grouping is stable
- module evidence is sorted

Milestone 4B acceptance:
- `uv run pytest` passes.
- C/C++ module detections are more useful and stable.
- Existing graph and Mermaid tests still pass or are intentionally updated.

## Milestone 4C - Build Target to Module Mapping

Goal:
Map Makefile/CMake targets to the modules and source files they build.

Current baseline:
- Makefile target names are detected conservatively.
- CMake target names are detected from `add_executable()` and `add_library()`.
- Target source files are not fully extracted or mapped to modules.
- The graph currently adds broad `Executable Target -> C/C++ Module` edges.

Implementation requirements:
- For CMake:
  - parse simple one-line and multi-line `add_executable()` calls
  - parse simple one-line and multi-line `add_library()` calls
  - extract literal source/header arguments when they are path-like
  - ignore variables, generator expressions, and complex CMake syntax
- For Makefile:
  - keep target parsing conservative
  - optionally map object prerequisites such as `queue.o` back to `queue.c` or `queue.cpp` when unambiguous
  - do not try to evaluate Make variables or includes
- Add structured target information that can preserve:
  - target name
  - target kind, such as executable, library, or make target
  - source file evidence
  - build file evidence
- Connect build targets to modules only when there is evidence.
- Keep fallback behavior conservative if source mapping is unavailable.

Tests to add:
- CMake executable target extracts literal sources
- CMake library target extracts literal sources
- multi-line CMake target extraction works
- CMake variables are ignored safely
- Makefile object prerequisites map to source files when unique
- ambiguous Makefile object mappings do not guess
- graph edges use target-to-module evidence

Milestone 4C acceptance:
- `uv run pytest` passes.
- CMake fixture diagrams show executable/library relationships.
- Broad target-to-all-module edges are removed or narrowed when better evidence exists.

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
- Current C/C++ edges are broad:
  - `C/C++ Project -> C/C++ Module`
  - `C/C++ Project -> Executable Target`
  - `Executable Target -> C/C++ Module`
  - `C/C++ Module -> C/C++ Systems Pattern` when evidence files overlap

Implementation requirements:
- Add include-derived module edges:
  - module A includes module B
  - source/header file A includes file B
- Add build-derived target edges:
  - executable target -> module
  - library target -> module
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
1. Implement Milestone 4A only.
2. Run `uv run pytest`.
3. Run `uv run archgen .`.
4. Stop and report what changed.

Then continue in this order:
1. 4B - module grouping
2. 4C - build target to module mapping
3. 4D - systems component refinement
4. 4E - graph assembly rules
5. 4F - fixtures and snapshots

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
