# AGENTS.md

## Project
This repo is `archdia`, a Python CLI tool whose command name is `archgen`.

The goal is to scan source repositories and generate useful first-draft Mermaid architecture diagrams.

## Current MVP priority
Build incrementally. Do not implement the whole product at once.

Current order:
1. CLI skeleton
2. Repository scanner
3. File/language summary
4. Ignore rules
5. C/C++ file detection
6. Makefile/CMake detection
7. Graph model
8. Mermaid renderer

## Commands
Use uv.

Run tests:
`uv run pytest`

Run CLI:
`uv run archgen .`

## Coding style
Prefer small, simple modules.
Use dataclasses for core models.
Keep detectors modular.
Avoid heavy dependencies unless asked.
Favor practical heuristics over deep static analysis.

## Done means
A task is not done until:
- tests pass
- `uv run archgen .` works
- the diff is small enough to review
- new behavior is covered by at least one test when practical

## Do
Do ask exhaustive amounts of questions for clarification instead of making assumptions

## Do not
Do not add a web UI.
Do not add AI/LLM features yet.
Keep implementation focused on C/C++ systems projects and Python backend projects.
Do not rewrite the whole project structure without explaining why.
