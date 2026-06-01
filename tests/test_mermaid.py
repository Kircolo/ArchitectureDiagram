from archgen.graph import ArchitectureGraph, Edge, Node
from archgen.renderers.mermaid import render_mermaid


def test_mermaid_renderer_starts_with_flowchart_and_trailing_newline() -> None:
    graph = ArchitectureGraph(nodes=(), edges=())

    output = render_mermaid(graph)

    assert output == "flowchart TD\n"


def test_mermaid_renderer_renders_nodes_before_edges_and_sorts_output() -> None:
    graph = ArchitectureGraph(
        nodes=(
            Node("z_api", "API", "API", ()),
            Node("a_db", "PostgreSQL", "Database", ()),
            Node("m_cache", "Redis Cache", "Cache", ()),
        ),
        edges=(
            Edge("z_api", "m_cache"),
            Edge("z_api", "a_db"),
        ),
    )

    output = render_mermaid(graph)

    assert output == (
        "flowchart TD\n"
        '    a_db[("PostgreSQL")]\n'
        '    m_cache[("Redis Cache")]\n'
        '    z_api["API"]\n'
        "    z_api --> a_db\n"
        "    z_api --> m_cache\n"
    )


def test_mermaid_renderer_escapes_quotes_in_node_and_edge_labels() -> None:
    graph = ArchitectureGraph(
        nodes=(
            Node("api", 'FastAPI "public"', "API", ()),
            Node("db", 'PostgreSQL "main"', "Database", ()),
        ),
        edges=(Edge("api", "db", label='reads "writes"'),),
    )

    output = render_mermaid(graph)

    assert 'api["FastAPI \\"public\\""]' in output
    assert 'db[("PostgreSQL \\"main\\"")]' in output
    assert 'api -->|reads \\"writes\\"| db' in output


def test_mermaid_renderer_sanitizes_node_ids_and_edge_references() -> None:
    graph = ArchitectureGraph(
        nodes=(
            Node("API Service", "API", "API", ()),
            Node("123 db.main", "Database", "Database", ()),
        ),
        edges=(Edge("API Service", "123 db.main"),),
    )

    output = render_mermaid(graph)

    assert output == (
        "flowchart TD\n"
        '    API_Service["API"]\n'
        '    n_123_db_main[("Database")]\n'
        "    API_Service --> n_123_db_main\n"
    )


def test_mermaid_renderer_resolves_sanitized_id_collisions() -> None:
    graph = ArchitectureGraph(
        nodes=(
            Node("api.main", "Main API", "API", ()),
            Node("api main", "Admin API", "API", ()),
        ),
        edges=(Edge("api.main", "api main"),),
    )

    output = render_mermaid(graph)

    assert output == (
        "flowchart TD\n"
        '    api_main["Admin API"]\n'
        '    api_main_2["Main API"]\n'
        "    api_main_2 --> api_main\n"
    )
