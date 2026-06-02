from pathlib import Path

import pytest
from typer.testing import CliRunner

from archgen import app


FIXTURE_ROOT = Path(__file__).parent / "fixtures"

runner = CliRunner()


@pytest.mark.parametrize(
    ("fixture_name", "expected_nodes", "expected_edges"),
    [
        (
            "c_http_server",
            [
                'c_c_project_c_application["C application"]',
                'executable_target_server["server"]',
                'c_c_module_server_module["server module"]',
                'c_c_module_http_module["HTTP module"]',
                'c_c_module_queue_module["queue module"]',
                'c_c_module_threadpool_module["threadpool module"]',
                'c_c_module_storage_module["storage module"]',
                'c_c_systems_pattern_socket_listener["Socket Listener"]',
                'c_c_systems_pattern_shared_queue["Shared Queue"]',
                'c_c_systems_pattern_worker_thread_pool["Worker Thread Pool"]',
                'c_c_systems_pattern_file_storage["File Storage"]',
            ],
            [
                "c_c_module_server_module -->|includes| c_c_module_http_module",
                "c_c_module_server_module -->|includes| c_c_module_queue_module",
                "c_c_module_threadpool_module -->|includes| c_c_module_queue_module",
                (
                    "c_c_module_server_module -->|uses| "
                    "c_c_systems_pattern_socket_listener"
                ),
                (
                    "c_c_module_threadpool_module -->|uses| "
                    "c_c_systems_pattern_worker_thread_pool"
                ),
                (
                    "executable_target_server -->|uses| "
                    "c_c_systems_pattern_shared_queue"
                ),
                "executable_target_server --> c_c_module_storage_module",
            ],
        ),
        (
            "c_cli_encoder_decoder",
            [
                'c_c_project_c_application["C application"]',
                'build_target_codec["codec"]',
                'executable_target_cli_binary["CLI Binary"]',
                'c_c_module_encoder_module["encoder module"]',
                'c_c_module_decoder_module["decoder module"]',
                'c_c_module_bitreader_module["bitreader module"]',
                'c_c_module_bitwriter_module["bitwriter module"]',
                'c_c_module_file_storage_module["file storage module"]',
                'c_c_systems_pattern_encoder["Encoder"]',
                'c_c_systems_pattern_decoder["Decoder"]',
                'c_c_systems_pattern_bit_i_o["Bit I/O"]',
                'c_c_systems_pattern_file_storage["File Storage"]',
            ],
            [
                "build_target_codec --> c_c_module_encoder_module",
                "build_target_codec -->|uses| c_c_systems_pattern_encoder",
                "build_target_codec -->|uses| c_c_systems_pattern_bit_i_o",
                (
                    "c_c_module_encoder_module -->|includes| "
                    "c_c_module_bitwriter_module"
                ),
                (
                    "c_c_module_decoder_module -->|includes| "
                    "c_c_module_bitreader_module"
                ),
                (
                    "c_c_module_file_storage_module -->|uses| "
                    "c_c_systems_pattern_file_storage"
                ),
            ],
        ),
        (
            "cpp_cmake_project",
            [
                'c_c_project_c_application["C++ application"]',
                'executable_target_app["app"]',
                'library_target_core["core"]',
                'c_c_module_app_module["app module"]',
                'c_c_module_core_engine_module["core engine module"]',
            ],
            [
                "c_c_module_app_module -->|includes| c_c_module_core_engine_module",
                "executable_target_app --> c_c_module_app_module",
                "library_target_core --> c_c_module_core_engine_module",
                "c_c_project_c_application --> library_target_core",
            ],
        ),
    ],
)
def test_c_cpp_fixture_cli_mermaid_contains_expected_architecture(
    fixture_name: str,
    expected_nodes: list[str],
    expected_edges: list[str],
) -> None:
    fixture_path = FIXTURE_ROOT / fixture_name

    result = runner.invoke(app, [str(fixture_path), "--dry-run"])

    assert result.exit_code == 0
    assert result.stdout.startswith("flowchart TD\n")
    assert "Generated" not in result.stdout
    for node in expected_nodes:
        assert node in result.stdout
    for edge in expected_edges:
        assert edge in result.stdout
