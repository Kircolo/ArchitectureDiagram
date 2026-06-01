from pathlib import Path
from types import SimpleNamespace

from archgen.detection import Detection
from archgen.graph import Edge
from archgen.graph_builder import build_architecture_graph, sanitize_node_id
from archgen.renderers.mermaid import render_mermaid
from archgen.scanner import CCppResolvedInclude


def repository_summary(
    *detections: Detection,
    c_cpp_resolved_includes: list[CCppResolvedInclude] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        detections=list(detections),
        c_cpp_resolved_includes=c_cpp_resolved_includes or [],
    )


def component(kind: str, name: str, *evidence: str) -> Detection:
    return Detection(
        kind=kind,
        name=name,
        evidence=tuple(Path(path) for path in evidence),
    )


def edge_pairs(edges: tuple[Edge, ...]) -> set[tuple[str, str]]:
    return {(edge.source, edge.target) for edge in edges}


def edge_triples(edges: tuple[Edge, ...]) -> set[tuple[str, str, str | None]]:
    return {(edge.source, edge.target, edge.label) for edge in edges}


def test_sanitize_node_id_produces_mermaid_safe_ids() -> None:
    assert sanitize_node_id("C/C++ Project: Main App!") == "c_c_project_main_app"
    assert sanitize_node_id("123 API") == "n_123_api"


def test_graph_builder_creates_nodes_for_detections_and_preserves_evidence() -> None:
    graph = build_architecture_graph(
        repository_summary(
            component("API", "FastAPI API", "app/main.py"),
            component("Cache", "Redis Cache", "requirements.txt", "app/cache.py"),
        )
    )

    nodes_by_id = {node.id: node for node in graph.nodes}

    assert graph.warnings == ()
    assert [node.id for node in graph.nodes] == [
        "api_fastapi_api",
        "cache_redis_cache",
    ]
    cache = nodes_by_id["cache_redis_cache"]
    assert cache.label == "Redis Cache"
    assert cache.kind == "Cache"
    assert cache.source_files == ("app/cache.py", "requirements.txt")
    assert {
        (node.id, node.label, node.kind)
        for node in graph.nodes
    } == {
        ("api_fastapi_api", "FastAPI API", "API"),
        ("cache_redis_cache", "Redis Cache", "Cache"),
    }


def test_graph_builder_resolves_node_id_collisions_with_warning() -> None:
    graph = build_architecture_graph(
        repository_summary(
            component("API", "FastAPI API", "app/main.py"),
            component("API", "FastAPI API", "app/admin.py"),
        )
    )

    assert [node.id for node in graph.nodes] == [
        "api_fastapi_api",
        "api_fastapi_api_2",
    ]
    assert graph.warnings == (
        'Resolved node ID collision for "api_fastapi_api" as "api_fastapi_api_2".',
    )


def test_graph_builder_adds_conservative_python_service_edges() -> None:
    graph = build_architecture_graph(
        repository_summary(
            component("API", "FastAPI API", "app/main.py"),
            component("Database", "PostgreSQL", "app/db.py"),
            component("Cache", "Redis Cache", "app/cache.py"),
            component("Docker", "Docker", "Dockerfile"),
            component("Tests", "Test Suite", "tests/test_app.py"),
        )
    )

    assert edge_pairs(graph.edges) == {
        ("api_fastapi_api", "database_postgresql"),
        ("api_fastapi_api", "cache_redis_cache"),
        ("tests_test_suite", "api_fastapi_api"),
        ("tests_test_suite", "database_postgresql"),
        ("tests_test_suite", "cache_redis_cache"),
    }


def test_graph_builder_adds_conservative_c_cpp_edges() -> None:
    graph = build_architecture_graph(
        repository_summary(
            component("C/C++ Project", "C application", "src/main.c"),
            component("C/C++ Module", "queue module", "include/queue.h", "src/queue.c"),
            component("C/C++ Module", "storage module", "src/storage.c"),
            component("Executable Target", "app", "CMakeLists.txt", "src/queue.c"),
            component("Library Target", "storage", "CMakeLists.txt", "src/storage.c"),
            component("Build Target", "package", "Makefile", "src/queue.c"),
            component("C/C++ Systems Pattern", "Queues", "src/queue.c"),
            component("C/C++ Systems Pattern", "Sockets", "src/server.c"),
            component("Tests", "Test Suite", "tests"),
        )
    )

    assert edge_pairs(graph.edges) == {
        ("c_c_project_c_application", "c_c_module_queue_module"),
        ("c_c_project_c_application", "c_c_module_storage_module"),
        ("c_c_project_c_application", "executable_target_app"),
        ("c_c_project_c_application", "library_target_storage"),
        ("build_target_package", "c_c_module_queue_module"),
        ("executable_target_app", "c_c_module_queue_module"),
        ("build_target_package", "c_c_systems_pattern_queues"),
        ("executable_target_app", "c_c_systems_pattern_queues"),
        ("library_target_storage", "c_c_module_storage_module"),
        ("c_c_module_queue_module", "c_c_systems_pattern_queues"),
        ("tests_test_suite", "c_c_project_c_application"),
    }


def test_graph_builder_does_not_connect_unmapped_targets_to_all_modules() -> None:
    graph = build_architecture_graph(
        repository_summary(
            component("C/C++ Module", "queue module", "src/queue.c"),
            component("Executable Target", "app", "CMakeLists.txt"),
        )
    )

    assert edge_pairs(graph.edges) == set()


def test_graph_builder_adds_include_derived_module_edges() -> None:
    graph = build_architecture_graph(
        repository_summary(
            component(
                "C/C++ Module",
                "server module",
                "include/server.h",
                "src/server.c",
            ),
            component(
                "C/C++ Module",
                "queue module",
                "include/queue.h",
                "src/queue.c",
            ),
            c_cpp_resolved_includes=[
                CCppResolvedInclude(
                    Path("src/server.c"),
                    "queue.h",
                    Path("include/queue.h"),
                    "resolved",
                ),
                CCppResolvedInclude(
                    Path("include/server.h"),
                    "queue.h",
                    Path("include/queue.h"),
                    "resolved",
                ),
                CCppResolvedInclude(
                    Path("src/server.c"),
                    "missing.h",
                    None,
                    "unresolved",
                ),
            ],
        )
    )

    include_edges = [
        edge
        for edge in graph.edges
        if edge.label == "includes"
    ]

    assert include_edges == [
        Edge(
            source="c_c_module_server_module",
            target="c_c_module_queue_module",
            label="includes",
        )
    ]


def test_graph_builder_adds_system_edges_for_modules_and_owned_targets() -> None:
    graph = build_architecture_graph(
        repository_summary(
            component(
                "C/C++ Module",
                "server module",
                "include/server.h",
                "src/server.c",
            ),
            component("C/C++ Module", "queue module", "include/queue.h", "src/queue.c"),
            component("Executable Target", "server", "CMakeLists.txt", "src/server.c"),
            component(
                "C/C++ Systems Pattern",
                "Socket Listener",
                "include/server.h",
                "src/server.c",
            ),
            component(
                "C/C++ Systems Pattern",
                "Shared Queue",
                "include/queue.h",
                "src/queue.c",
            ),
        )
    )

    assert {
        edge
        for edge in graph.edges
        if edge.label == "uses"
    } == {
        Edge(
            source="c_c_module_queue_module",
            target="c_c_systems_pattern_shared_queue",
            label="uses",
        ),
        Edge(
            source="c_c_module_server_module",
            target="c_c_systems_pattern_socket_listener",
            label="uses",
        ),
        Edge(
            source="executable_target_server",
            target="c_c_systems_pattern_socket_listener",
            label="uses",
        ),
    }
    assert (
        "executable_target_server",
        "c_c_systems_pattern_shared_queue",
    ) not in edge_pairs(graph.edges)


def test_graph_builder_keeps_c_cpp_edges_deterministic_and_deduplicated() -> None:
    graph = build_architecture_graph(
        repository_summary(
            component("C/C++ Module", "api module", "src/api.c", "include/api.h"),
            component(
                "C/C++ Module",
                "storage module",
                "src/storage.c",
                "include/storage.h",
            ),
            c_cpp_resolved_includes=[
                CCppResolvedInclude(
                    Path("src/api.c"),
                    "storage.h",
                    Path("include/storage.h"),
                    "resolved",
                ),
                CCppResolvedInclude(
                    Path("src/api.c"),
                    "storage.h",
                    Path("include/storage.h"),
                    "resolved",
                ),
            ],
        )
    )

    assert graph.edges == tuple(sorted(set(graph.edges), key=lambda edge: edge.source))
    assert edge_triples(graph.edges) == {
        (
            "c_c_module_api_module",
            "c_c_module_storage_module",
            "includes",
        )
    }


def test_graph_builder_mermaid_output_contains_c_cpp_4e_edges() -> None:
    graph = build_architecture_graph(
        repository_summary(
            component("C/C++ Module", "server module", "src/server.c"),
            component("C/C++ Module", "queue module", "include/queue.h", "src/queue.c"),
            component("Executable Target", "server", "CMakeLists.txt", "src/server.c"),
            component("C/C++ Systems Pattern", "Socket Listener", "src/server.c"),
            c_cpp_resolved_includes=[
                CCppResolvedInclude(
                    Path("src/server.c"),
                    "queue.h",
                    Path("include/queue.h"),
                    "resolved",
                )
            ],
        )
    )

    output = render_mermaid(graph)

    assert output.startswith("flowchart TD\n")
    assert (
        "c_c_module_server_module -->|includes| c_c_module_queue_module"
        in output
    )
    assert (
        "executable_target_server -->|uses| "
        "c_c_systems_pattern_socket_listener"
    ) in output
