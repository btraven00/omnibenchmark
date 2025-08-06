from pathlib import Path

import pytest

from omnibenchmark.model import Benchmark


@pytest.mark.short
def test_parse_benchmark():
    benchmark_file = "../data/Benchmark_001.yaml"
    benchmark_file_path = Path(__file__).parent / benchmark_file

    try:
        benchmark = Benchmark.from_yaml(benchmark_file_path)
        # Verify basic properties
        assert benchmark is not None
        assert isinstance(benchmark, Benchmark)
        assert hasattr(benchmark, "id")
        assert hasattr(benchmark, "stages")
        assert hasattr(benchmark, "software_environments")
    except Exception as e:
        pytest.fail(f"Parsing benchmark model failed: {e}")


@pytest.mark.short
def test_parse_benchmark_deprecated():
    """Test that the deprecated parse_instance still works but warns."""
    from omnibenchmark.utils import parse_instance
    from omnibenchmark.model import Benchmark

    benchmark_file = "../data/Benchmark_001.yaml"
    benchmark_file_path = Path(__file__).parent / benchmark_file

    # Test with deprecation warning
    with pytest.warns(DeprecationWarning, match="parse_instance is deprecated"):
        benchmark = parse_instance(benchmark_file_path, Benchmark)
        assert benchmark is not None
        assert isinstance(benchmark, Benchmark)
