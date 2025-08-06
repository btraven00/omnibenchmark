"""Benchmark converter that provides compatibility with LinkMLConverter interface."""

import warnings
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from omnibenchmark.model.benchmark import (
    Benchmark,
    Stage,
    Module,
    IOFile,
    SoftwareEnvironment,
    SoftwareBackendEnum,
    Repository,
    MetricCollector,
)


class BenchmarkConverter:
    """
    Adapter class that provides the same interface as LinkMLConverter
    but uses the new Pydantic-based Benchmark model.
    """

    def __init__(self, benchmark_file: Path):
        """
        Initialize converter from a benchmark YAML file.

        Args:
            benchmark_file: Path to the benchmark YAML file
        """
        self.benchmark_file = benchmark_file
        self.model: Benchmark = Benchmark.from_yaml(benchmark_file)

    def get_name(self) -> str:
        """Get name of the benchmark"""
        return self.model.get_name()

    def get_version(self) -> str:
        """Get version of the benchmark"""
        return self.model.get_version()

    def get_author(self) -> str:
        """Get author of the benchmark"""
        return self.model.get_author()

    def get_software_backend(self) -> SoftwareBackendEnum:
        """Get software backend of the benchmark"""
        return self.model.get_software_backend()

    def get_software_environments(self) -> Dict[str, SoftwareEnvironment]:
        """Get software environments"""
        return self.model.get_software_environments()

    def get_definition(self) -> Benchmark:
        """Get underlying benchmark"""
        return self.model

    def get_easyconfigs(self) -> List[Optional[str]]:
        """Get easyconfigs"""
        return self.model.get_easyconfigs()

    def get_conda_envs(self) -> List[Optional[str]]:
        """Get conda envs"""
        return self.model.get_conda_envs()

    def get_stages(self) -> Dict[str, Stage]:
        """Get benchmark stages"""
        return self.model.get_stages()

    def get_stage(self, stage_id: str) -> Optional[Stage]:
        """Get stage by stage_id"""
        return self.model.get_stage(stage_id)

    def get_stage_by_output(self, output_id: str) -> Optional[Stage]:
        """Get stage that returns output with output_id"""
        return self.model.get_stage_by_output(output_id)

    def get_modules_by_stage(self, stage: Union[str, Stage]) -> Dict[str, Module]:
        """Get modules by stage/stage_id"""
        return self.model.get_modules_by_stage(stage)

    def get_stage_implicit_inputs(self, stage: Union[str, Stage]) -> List[List[str]]:
        """Get implicit inputs of a stage by stage/stage_id"""
        return self.model.get_stage_implicit_inputs(stage)

    def get_explicit_inputs(self, input_ids: List[str]) -> Dict[str, str]:
        """Get explicit inputs of a stage by input_id(s)"""
        return self.model.get_explicit_inputs(input_ids)

    def get_stage_outputs(self, stage: Union[str, Stage]) -> Dict[str, str]:
        """Get outputs of a stage by stage/stage_id"""
        return self.model.get_stage_outputs(stage)

    def get_output_stage(self, output_id: str) -> Optional[Stage]:
        """Get stage that returns output with out_id"""
        return self.model.get_output_stage(output_id)

    def get_module_excludes(self, module: Union[str, Module]) -> Optional[List[str]]:
        """Get module excludes by module/module_id"""
        return self.model.get_module_excludes(module)

    def get_module_parameters(self, module: Union[str, Module]) -> Optional[List[Any]]:
        """Get module parameters by module/module_id"""
        return self.model.get_module_parameters(module)

    def get_module_repository(self, module: Union[str, Module]) -> Optional[Repository]:
        """Get module repository by module/module_id"""
        return self.model.get_module_repository(module)

    def get_module_environment(self, module: Union[str, Module]) -> Optional[str]:
        """Get module software environment by module/module_id"""
        return self.model.get_module_environment(module)

    def get_metric_collectors(self) -> List[MetricCollector]:
        """Get metric collectors"""
        return self.model.get_metric_collectors()

    def is_initial(self, stage: Stage) -> bool:
        """Check if stage is initial"""
        return self.model.is_initial(stage)

    def get_outputs(self) -> Dict[str, IOFile]:
        """Get outputs"""
        return self.model.get_outputs()

    def get_modules(self) -> Dict[str, Module]:
        """Get modules"""
        return self.model.get_modules()

    def validate(self, benchmark_dir: Path) -> "BenchmarkConverter":
        """
        Validate the benchmark structure.

        Args:
            benchmark_dir: Directory containing the benchmark

        Returns:
            Self for chaining

        Raises:
            ValidationError: If validation fails
        """
        self.model.validate_structure(benchmark_dir)
        return self


# For backwards compatibility - use BenchmarkConverter when migrating from LinkMLConverter
class LinkMLConverter(BenchmarkConverter):
    """
    DEPRECATED: Use BenchmarkConverter instead.

    This class exists only for backwards compatibility and will be removed in a future version.
    """

    def __init__(self, benchmark_file: Path):
        warnings.warn(
            "LinkMLConverter is deprecated and will be removed in a future version. Please use BenchmarkConverter instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(benchmark_file)
