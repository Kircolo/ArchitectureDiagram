from __future__ import annotations

from archgen.detectors.c_cpp import detect_c_cpp_components
from archgen.detectors.cache import detect_cache_components
from archgen.detectors.database import detect_database_components
from archgen.detectors.docker import detect_docker_components
from archgen.detectors.python_api import detect_python_api_components
from archgen.detectors.tests import detect_test_components

__all__ = [
    "detect_c_cpp_components",
    "detect_cache_components",
    "detect_database_components",
    "detect_docker_components",
    "detect_python_api_components",
    "detect_test_components",
]

