"""Pydantic models for Omnibenchmark."""

from omnibenchmark.model.benchmark import (
    # Base classes
    IdentifiableEntity,
    DescribableEntity,
    # Enums
    APIVersion,
    SoftwareBackendEnum,
    RepositoryType,
    StorageAPIEnum,
    # Core models
    Repository,
    Storage,
    Parameter,
    IOFile,
    InputCollection,
    SoftwareEnvironment,
    SoftwareEnvironmentReference,
    Module,
    MetricCollector,
    Stage,
    Benchmark,
    # Exceptions
    ValidationError,
    # Utility functions
    expand_output_path,
    validate_non_empty_string,
    validate_non_empty_commit,
    validate_hex_string,
)
from omnibenchmark.model.converter import (
    BenchmarkConverter,
    LinkMLConverter,  # Alias for backwards compatibility
)
from omnibenchmark.model.module import (
    DerivedSoftware,
    ModuleMetadata,
)

__all__ = [
    # Base classes
    "IdentifiableEntity",
    "DescribableEntity",
    # Enums
    "APIVersion",
    "SoftwareBackendEnum",
    "RepositoryType",
    "StorageAPIEnum",
    # Core models
    "Repository",
    "Storage",
    "Parameter",
    "IOFile",
    "InputCollection",
    "SoftwareEnvironment",
    "SoftwareEnvironmentReference",
    "Module",
    "MetricCollector",
    "Stage",
    "Benchmark",
    # Exceptions
    "ValidationError",
    # Converters
    "BenchmarkConverter",
    "LinkMLConverter",
    # Module metadata
    "DerivedSoftware",
    "ModuleMetadata",
    # Utility functions
    "expand_output_path",
    "validate_non_empty_string",
    "validate_non_empty_commit",
    "validate_hex_string",
]
