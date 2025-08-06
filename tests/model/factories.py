"""Factory functions for creating test objects with minimal boilerplate."""

from typing import Dict, Any
from omnibenchmark.model import (
    Benchmark,
    SoftwareEnvironment,
    SoftwareBackendEnum,
    StorageAPIEnum,
    Repository,
    Module,
    Stage,
    MetricCollector,
    IOFile,
)


def make_repository(**kwargs) -> Repository:
    """Create a Repository with defaults."""
    defaults = {
        "url": "https://github.com/example/repo.git",
        "commit": "abc123",
        "type": "git",
    }
    return Repository(**{**defaults, **kwargs})


def make_iofile(**kwargs) -> IOFile:
    """Create an IOFile with defaults."""
    defaults = {"id": "output1", "path": "results/output.txt"}
    return IOFile(**{**defaults, **kwargs})


def make_software_environment(**kwargs) -> SoftwareEnvironment:
    """Create a SoftwareEnvironment with defaults."""
    defaults = {"id": "test_env", "description": "Test environment"}
    return SoftwareEnvironment(**{**defaults, **kwargs})


def make_module(**kwargs) -> Module:
    """Create a Module with defaults."""
    defaults = {
        "id": "test_module",
        "name": "Test Module",
        "software_environment": "test_env",
        "repository": make_repository(),
    }
    # Handle nested objects
    if "repository" in kwargs and isinstance(kwargs["repository"], dict):
        kwargs["repository"] = make_repository(**kwargs["repository"])
    if "outputs" in kwargs and kwargs["outputs"] is not None:
        kwargs["outputs"] = [
            make_iofile(**out) if isinstance(out, dict) else out
            for out in kwargs["outputs"]
        ]
    return Module(**{**defaults, **kwargs})


def make_metric_collector(**kwargs) -> MetricCollector:
    """Create a MetricCollector with defaults."""
    defaults = {
        "id": "metrics",
        "name": "Test Metrics",
        "software_environment": "test_env",
        "repository": make_repository(),
        "inputs": [],
        "outputs": [],
    }
    # Handle nested objects
    if "repository" in kwargs and isinstance(kwargs["repository"], dict):
        kwargs["repository"] = make_repository(**kwargs["repository"])
    if "inputs" in kwargs and kwargs["inputs"] is not None:
        kwargs["inputs"] = [
            make_iofile(**inp) if isinstance(inp, dict) else inp
            for inp in kwargs["inputs"]
        ]
    if "outputs" in kwargs and kwargs["outputs"] is not None:
        kwargs["outputs"] = [
            make_iofile(**out) if isinstance(out, dict) else out
            for out in kwargs["outputs"]
        ]
    return MetricCollector(**{**defaults, **kwargs})


def make_stage(**kwargs) -> Stage:
    """Create a Stage with defaults."""
    defaults = {"id": "test_stage", "modules": [], "outputs": []}
    # Handle nested objects
    if "modules" in kwargs and kwargs["modules"] is not None:
        kwargs["modules"] = [
            make_module(**mod) if isinstance(mod, dict) else mod
            for mod in kwargs["modules"]
        ]
    if "outputs" in kwargs and kwargs["outputs"] is not None:
        kwargs["outputs"] = [
            make_iofile(**out) if isinstance(out, dict) else out
            for out in kwargs["outputs"]
        ]
    return Stage(**{**defaults, **kwargs})


def make_benchmark(**kwargs) -> Benchmark:
    """Create a Benchmark with sensible defaults.

    Only specify the fields you want to override.
    Example:
        benchmark = make_benchmark(
            id="my_benchmark",
            software_backend="conda",
            software_environments={"env1": {...}}
        )
    """
    defaults = {
        "id": "test_benchmark",
        "description": "Test benchmark",
        "version": "1.0",
        "benchmarker": "Test User",
        "storage": "https://storage.example.com",
        "benchmark_yaml_spec": "0.3.0",
        "storage_api": StorageAPIEnum.S3,
        "storage_bucket_name": "test-bucket",
        "software_backend": SoftwareBackendEnum.host,
        "software_environments": {},
        "stages": [],
        "metric_collectors": [],
        "outputs": [],
    }

    # Handle nested objects
    final_kwargs = {**defaults, **kwargs}

    if "software_environments" in kwargs and kwargs["software_environments"]:
        final_kwargs["software_environments"] = {
            k: make_software_environment(**v) if isinstance(v, dict) else v
            for k, v in kwargs["software_environments"].items()
        }

    if "stages" in kwargs and kwargs["stages"] is not None:
        final_kwargs["stages"] = [
            make_stage(**stage) if isinstance(stage, dict) else stage
            for stage in kwargs["stages"]
        ]

    if "metric_collectors" in kwargs and kwargs["metric_collectors"] is not None:
        final_kwargs["metric_collectors"] = [
            make_metric_collector(**mc) if isinstance(mc, dict) else mc
            for mc in kwargs["metric_collectors"]
        ]

    if "outputs" in kwargs and kwargs["outputs"] is not None:
        final_kwargs["outputs"] = [
            make_iofile(**out) if isinstance(out, dict) else out
            for out in kwargs["outputs"]
        ]

    return Benchmark(**final_kwargs)


def make_benchmark_dict(**kwargs) -> Dict[str, Any]:
    """Create a benchmark dictionary (not instantiated)."""
    defaults = {
        "id": "test_benchmark",
        "description": "Test benchmark",
        "version": "1.0",
        "benchmarker": "Test User",
        "storage": "https://storage.example.com",
        "benchmark_yaml_spec": "0.3.0",
        "storage_api": "S3",
        "storage_bucket_name": "test-bucket",
        "software_backend": "host",
    }
    return {**defaults, **kwargs}


def make_yaml_content(**kwargs) -> str:
    """Create YAML content for a benchmark."""
    data = make_benchmark_dict(**kwargs)
    import yaml

    return yaml.dump(data, default_flow_style=False)
