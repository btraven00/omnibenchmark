"""Pydantic models for Omnibenchmark - replacing omni_schema and linkml dependencies."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from enum import Enum

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from omnibenchmark.utils import merge_dict_list  # type: ignore[import]


class ValidationError(Exception):
    """Exception raised for validation errors."""

    def __init__(self, *errors: Any) -> None:
        self.errors = errors[0] if len(errors) == 1 else errors
        super().__init__(*errors)

    def __str__(self) -> str:
        if isinstance(self.errors, str):
            return self.errors
        else:
            return "\n".join(map(str, self.errors))


def _find_duplicates(items: List[str]) -> List[str]:
    """Find duplicate items in a list."""
    from collections import Counter

    counts = Counter(items)
    return [item for item, count in counts.items() if count > 1]


def _is_url(string: str) -> bool:
    """Check if the string is a valid URL using urlparse."""
    from urllib.parse import urlparse

    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


# Validators
def validate_non_empty_string(v: str) -> str:
    """Validate that a string is not empty."""
    if not v or not v.strip():
        raise ValueError("must be a non-empty string")
    return v


def validate_non_empty_commit(v: str) -> str:
    """Validate commit hash is not empty."""
    if not v or not v.strip():
        raise ValueError("Commit must be a non-empty string")
    return v


def validate_hex_string(v: str) -> str:
    """Validate that a string is a valid hex string."""
    if not v:
        raise ValueError("must be a valid hexadecimal string")
    try:
        int(v, 16)
    except ValueError:
        raise ValueError("must be a valid hexadecimal string")
    return v


# Enums
class APIVersion(str, Enum):
    """API version enum."""

    V0_1_0 = "0.1.0"
    V0_2_0 = "0.2.0"
    V0_3_0 = "0.3.0"

    @classmethod
    def latest(cls) -> "APIVersion":
        return cls.V0_3_0

    @classmethod
    def supported_versions(cls) -> set[str]:
        return {version.value for version in cls}


class SoftwareBackendEnum(str, Enum):
    """Software backend types."""

    apptainer = "apptainer"
    conda = "conda"
    docker = "docker"
    envmodules = "envmodules"
    host = "host"


class RepositoryType(str, Enum):
    """Repository types."""

    git = "git"


class StorageAPIEnum(str, Enum):
    """Storage API types. Currently only S3 is supported."""

    s3 = "S3"


# Base models
class IdentifiableEntity(BaseModel):
    """Base class for entities with an ID."""

    id: str = Field(..., description="Unique identifier")


class DescribableEntity(IdentifiableEntity):
    """Base class for entities with ID, name, and description."""

    name: Optional[str] = Field(None, description="Human-readable name")
    description: Optional[str] = Field(None, description="Description of the entity")


class Repository(BaseModel):
    """Repository information."""

    url: str = Field(..., description="Repository URL")
    commit: str = Field(..., description="Commit hash")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return validate_non_empty_string(v)

    @field_validator("commit")
    @classmethod
    def validate_commit(cls, v: str) -> str:
        return validate_non_empty_commit(v)

    type: RepositoryType = Field(RepositoryType.git, description="Repository type")


class Storage(BaseModel):
    """
    Storage configuration for remote storage of benchmark artifacts.
    This is intended for the benchmarker role, since they will have to
    provide the needed credentials to write in the store.
    """

    api: StorageAPIEnum = Field(
        StorageAPIEnum.s3,
        description="Storage API type (currently only S3 is supported)",
    )
    endpoint: str = Field(..., description="Storage endpoint URL")
    bucket_name: Optional[str] = Field(
        None, description="Storage bucket name (only needed if using S3)"
    )


class Parameter(BaseModel):
    """Parameter definition."""

    id: str = Field(..., description="Parameter ID")
    values: List[str] = Field(..., description="Parameter values")

    @field_validator("values")
    @classmethod
    def validate_values(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Parameter values cannot be empty")
        return v


class IOFile(IdentifiableEntity):
    """Input/Output file definition."""

    path: str = Field(..., description="File path")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        return validate_non_empty_string(v)


class InputCollection(BaseModel):
    """Collection of input file IDs."""

    entries: List[str] = Field(..., description="List of input file IDs")


class SoftwareEnvironment(DescribableEntity):
    """Software environment configuration."""

    repository: Optional[Repository] = None
    conda: Optional[str] = Field(None, description="Conda environment file path")
    apptainer: Optional[str] = Field(
        None, description="Apptainer/Singularity image path"
    )
    docker: Optional[str] = Field(None, description="Docker image")
    envmodule: Optional[str] = Field(None, description="Environment module name")
    easyconfig: Optional[str] = Field(None, description="EasyBuild config path")

    @model_validator(mode="after")
    def validate_backend_config(self) -> "SoftwareEnvironment":
        """Ensure at least one backend configuration is provided."""
        # Temporarily disabled to allow benchmark-level validation
        # backends = [
        #     self.conda,
        #     self.apptainer,
        #     self.docker,
        #     self.envmodule,
        #     self.easyconfig,
        # ]
        # if not any(backends):
        #     raise ValueError(
        #         "At least one software backend must be configured (conda, apptainer, docker, envmodule, or easyconfig)"
        #     )
        return self


class SoftwareEnvironmentReference(BaseModel):
    """Reference to a software environment."""

    software_environment: str = Field(..., description="Software environment ID")


class Module(DescribableEntity, SoftwareEnvironmentReference):
    """Module definition."""

    repository: Repository = Field(..., description="Module repository")
    software_environment: str = Field(..., description="Software environment ID")
    parameters: Optional[List[Parameter]] = Field(None, description="Module parameters")
    exclude: Optional[List[str]] = Field(None, description="Paths to exclude")
    outputs: Optional[List[IOFile]] = Field(None, description="Module outputs")

    def has_environment_reference(self, env_id: str = None) -> bool:
        """Check if module has a software environment reference."""
        if env_id is None:
            return bool(self.software_environment)
        return self.software_environment == env_id


class MetricCollector(DescribableEntity, SoftwareEnvironmentReference):
    """Metric collector definition."""

    repository: Repository = Field(..., description="Repository information")
    software_environment: str = Field(..., description="Software environment ID")
    inputs: List[IOFile] = Field(..., description="Input files")

    def has_environment_reference(self, env_id: str = None) -> bool:
        """Check if metric collector has a software environment reference."""
        if env_id is None:
            return bool(self.software_environment)
        return self.software_environment == env_id


class Stage(DescribableEntity):
    """Stage definition."""

    modules: List[Module] = Field(..., description="Modules in this stage")
    inputs: Optional[List[InputCollection]] = Field(None, description="Stage inputs")
    outputs: List[IOFile] = Field(..., description="Stage outputs")


class Benchmark(DescribableEntity):
    """Main benchmark definition."""

    benchmarker: str = Field(..., description="Benchmark author")
    version: str = Field(..., description="Benchmark version")
    software_backend: SoftwareBackendEnum = Field(..., description="Software backend")
    software_environments: List[SoftwareEnvironment] = Field(
        ..., description="Available software environments"
    )
    stages: List[Stage] = Field(..., description="Benchmark stages")
    metric_collectors: Optional[List[MetricCollector]] = Field(
        None, description="Metric collectors"
    )
    storage: Optional[Storage] = Field(None, description="Remote storage configuration")
    storage_api: Optional[StorageAPIEnum] = Field(
        None, description="Storage API type (deprecated, use storage.api)"
    )
    storage_bucket_name: Optional[str] = Field(
        None, description="Storage bucket name (deprecated, use storage.bucket_name)"
    )
    benchmark_yaml_spec: Optional[str] = Field(
        None,
        description="Benchmark YAML specification version (deprecated, use api_version)",
    )
    api_version: APIVersion = Field(APIVersion.V0_3_0, description="API version")

    @field_validator("api_version", mode="before")
    @classmethod
    def validate_api_version(cls, v):
        """Convert string API version to enum."""
        if isinstance(v, str):
            for version in APIVersion:
                if version.value == v:
                    return version
            # If no match found, let Pydantic handle the error
        return v

    # Validation state
    _benchmark_dir: Optional[Path] = None

    def get_storage_api(self) -> Optional[str]:
        """Get storage API with backward compatibility."""
        if self.storage and self.storage.api:
            return str(self.storage.api.value)
        return str(self.storage_api.value) if self.storage_api else None

    def get_storage_bucket_name(self) -> Optional[str]:
        """Get storage bucket name with backward compatibility."""
        if self.storage and self.storage.bucket_name:
            return self.storage.bucket_name
        return self.storage_bucket_name

    def get_storage_endpoint(self) -> Optional[str]:
        """Get storage endpoint."""
        if self.storage and self.storage.endpoint:
            return self.storage.endpoint
        return None

    @classmethod
    def from_yaml(cls, path_or_content) -> "Benchmark":
        """Load benchmark from YAML file or string content."""
        if isinstance(path_or_content, (str, Path)) and "\n" not in str(
            path_or_content
        ):
            # Treat as file path
            with open(path_or_content, "r") as f:
                data = yaml.safe_load(f)
        else:
            # Treat as YAML content string
            data = yaml.safe_load(path_or_content)

        # Convert dict-style software_environments to list format
        if "software_environments" in data and isinstance(
            data["software_environments"], dict
        ):
            envs = []
            for env_id, env_config in data["software_environments"].items():
                env_dict = dict(env_config) if env_config else {}
                env_dict["id"] = env_id
                envs.append(env_dict)
            data["software_environments"] = envs

        # Convert string storage to Storage object
        if "storage" in data and isinstance(data["storage"], str):
            data["storage"] = {
                "api": data.get("storage_api", "S3"),
                "endpoint": data["storage"],
            }

        return cls(**data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Benchmark":
        """Create benchmark from dictionary."""
        return cls(**data)

    @model_validator(mode="after")
    def validate_no_duplicate_ids(self) -> "Benchmark":
        """Validate that there are no duplicate IDs in stages."""
        stage_ids = [stage.id for stage in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("Duplicate stage IDs found")
        return self

    def merge_with(self, other: "Benchmark") -> "Benchmark":
        """Merge this benchmark with another benchmark."""
        # Create a new benchmark with combined data
        merged_data = self.model_dump()
        other_data = other.model_dump()

        # Update with other's data (other takes precedence for scalar fields)
        for key, value in other_data.items():
            if key in ["stages", "metric_collectors", "software_environments"]:
                # For list fields, combine them
                if key == "stages":
                    existing_stages = {
                        stage["id"]: stage for stage in merged_data.get(key, [])
                    }
                    other_stages = {
                        stage["id"]: stage for stage in other_data.get(key, [])
                    }
                    existing_stages.update(other_stages)
                    merged_data[key] = list(existing_stages.values())
                elif key == "metric_collectors":
                    existing_collectors = {
                        mc["id"]: mc for mc in merged_data.get(key, [])
                    }
                    other_collectors = {mc["id"]: mc for mc in other_data.get(key, [])}
                    existing_collectors.update(other_collectors)
                    merged_data[key] = list(existing_collectors.values())
                elif key == "software_environments":
                    existing_envs = {env["id"]: env for env in merged_data.get(key, [])}
                    other_envs = {env["id"]: env for env in other_data.get(key, [])}
                    existing_envs.update(other_envs)
                    merged_data[key] = list(existing_envs.values())
            else:
                # For scalar fields, other takes precedence if not None
                if value is not None:
                    merged_data[key] = value

        return Benchmark(**merged_data)

    def upgrade_to_latest(self) -> "Benchmark":
        """Upgrade benchmark to latest API version."""
        # Check current version from either field
        current_version = getattr(self, "benchmark_yaml_spec", None) or str(
            self.api_version
        )
        latest_version = APIVersion.latest()

        if current_version == latest_version:
            return self

        # Create upgraded version
        data = self.model_dump()
        data["api_version"] = latest_version
        data["benchmark_yaml_spec"] = latest_version

        return Benchmark(**data)

    def validate_software_environments(self) -> List[str]:
        """
        Validate that all software environment references exist.

        Returns:
            List of validation error messages

        Raises:
            ValueError: If any validation errors are found
        """
        import warnings

        errors: List[str] = []
        env_ids = {env.id for env in self.software_environments}
        used_env_ids = set()

        # Check modules
        for stage in self.stages:
            for module in stage.modules:
                if module.software_environment not in env_ids:
                    errors.append(
                        f"Module '{module.id}' references undefined software environment: '{module.software_environment}'"
                    )
                else:
                    used_env_ids.add(module.software_environment)

        # Check metric collectors
        if self.metric_collectors:
            for collector in self.metric_collectors:
                if collector.software_environment not in env_ids:
                    errors.append(
                        f"Metric collector '{collector.id}' references undefined software environment: '{collector.software_environment}'"
                    )
                else:
                    used_env_ids.add(collector.software_environment)

        # Validate backend-specific configurations
        for env in self.software_environments:
            if self.software_backend == SoftwareBackendEnum.conda:
                if not env.conda:
                    errors.append(
                        f"Conda backend requires conda configuration for environment '{env.id}'"
                    )
            elif self.software_backend == SoftwareBackendEnum.docker:
                if not env.apptainer and not env.docker:
                    errors.append(
                        f"Docker backend requires apptainer configuration for environment '{env.id}'"
                    )
            elif self.software_backend == SoftwareBackendEnum.apptainer:
                if not env.apptainer:
                    errors.append(
                        f"Apptainer backend requires apptainer configuration for environment '{env.id}'"
                    )
            elif self.software_backend == SoftwareBackendEnum.envmodules:
                if not env.envmodule:
                    errors.append(
                        f"Envmodules backend requires envmodule configuration for environment '{env.id}'"
                    )

        # Check for unused environments
        unused_envs = env_ids - used_env_ids
        for unused_env in unused_envs:
            warnings.warn(
                f"Software environment '{unused_env}' is defined but not used",
                UserWarning,
            )

        if errors:
            raise ValueError(
                f"Software environment validation failed: {'; '.join(errors)}. Environment not defined."
            )

        return errors

    # Compatibility methods for LinkMLConverter interface
    def get_name(self) -> str:
        """Get name of the benchmark."""
        return self.name if self.name else self.id

    def get_version(self) -> str:
        """Get version of the benchmark."""
        return self.version

    def get_author(self) -> str:
        """Get author of the benchmark."""
        return self.benchmarker

    def get_software_backend(self) -> SoftwareBackendEnum:
        """Get software backend of the benchmark."""
        return self.software_backend

    def get_software_environments(self) -> Dict[str, SoftwareEnvironment]:
        """Get software environments as a dict."""
        return {env.id: env for env in self.software_environments}

    def get_stages(self) -> Dict[str, Stage]:
        """Get benchmark stages as a dict."""
        return {stage.id: stage for stage in self.stages}

    def get_stage(self, stage_id: str) -> Optional[Stage]:
        """Get stage by stage_id."""
        stages = self.get_stages()
        return stages.get(stage_id)

    def get_stage_by_output(self, output_id: str) -> Optional[Stage]:
        """Get stage that returns output with output_id."""
        for stage in self.stages:
            for output in stage.outputs:
                if output.id == output_id:
                    return stage
        return None

    def get_modules_by_stage(self, stage: Union[str, Stage]) -> Dict[str, Module]:
        """Get modules by stage/stage_id."""
        if isinstance(stage, str):
            stage_obj = self.get_stage(stage)
            if not stage_obj:
                return {}
            return {module.id: module for module in stage_obj.modules}
        return {module.id: module for module in stage.modules}

    def get_stage_implicit_inputs(self, stage: Union[str, Stage]) -> List[List[str]]:
        """Get implicit inputs of a stage by stage/stage_id."""
        if isinstance(stage, str):
            stage_obj = self.get_stage(stage)
            if not stage_obj or not stage_obj.inputs:
                return []
            return [input_col.entries for input_col in stage_obj.inputs]
        if not stage.inputs:
            return []
        return [input_col.entries for input_col in stage.inputs]

    def get_explicit_inputs(self, input_ids: List[str]) -> Dict[str, str]:
        """Get explicit inputs of a stage by input_id(s)."""
        all_stages_outputs: List[Dict[str, str]] = []
        for stage_id, stage in self.get_stages().items():
            outputs = self.get_stage_outputs(stage=stage_id)
            outputs = {
                key: value.format(
                    input="{input}",
                    stage=stage_id,
                    module="{module}",
                    params="{params}",
                    dataset="{dataset}",
                )
                for key, value in outputs.items()
            }
            all_stages_outputs.append(outputs)

        all_stages_outputs_merged: Dict[str, str] = merge_dict_list(all_stages_outputs)  # type: ignore[assignment]

        explicit: Dict[str, Optional[str]] = {key: None for key in input_ids}
        for in_deliverable in input_ids:
            curr_output = all_stages_outputs_merged.get(in_deliverable)
            if curr_output is not None:
                explicit[in_deliverable] = curr_output

        result: Dict[str, str] = {}
        for k, v in explicit.items():
            if v is not None:
                result[k] = v
        return result

    def get_stage_outputs(self, stage: Union[str, Stage]) -> Dict[str, str]:
        """Get outputs of a stage by stage/stage_id."""
        if isinstance(stage, str):
            stage_obj = self.get_stage(stage)
            if not stage_obj:
                return {}
            return {
                output.id: expand_output_path(output) for output in stage_obj.outputs
            }
        return {output.id: expand_output_path(output) for output in stage.outputs}

    def get_output_stage(self, output_id: str) -> Optional[Stage]:
        """Get stage that returns output with output_id."""
        return self.get_stage_by_output(output_id)

    def get_module_excludes(self, module: Union[str, Module]) -> Optional[List[str]]:
        """Get module excludes by module/module_id."""
        if isinstance(module, str):
            modules = self.get_modules()
            module_obj = modules.get(module)
            if not module_obj:
                return None
            return module_obj.exclude
        return module.exclude

    def get_module_parameters(self, module: Union[str, Module]) -> Optional[List[Any]]:
        """Get module parameters by module/module_id."""
        # Import here to avoid circular imports
        from omnibenchmark.benchmark import params

        if isinstance(module, str):
            modules = self.get_modules()
            module_obj = modules.get(module)
            if not module_obj or not module_obj.parameters:
                return None
            return [
                params.Params.from_cli_args(p.values) for p in module_obj.parameters
            ]  # type: ignore[misc]
        if not module or not module.parameters:
            return None
        return [params.Params.from_cli_args(p.values) for p in module.parameters]  # type: ignore[misc]

    def get_module_repository(self, module: Union[str, Module]) -> Optional[Repository]:
        """Get module repository by module/module_id."""
        if isinstance(module, str):
            modules = self.get_modules()
            module_obj = modules.get(module)
            if not module_obj:
                return None
            return module_obj.repository
        return module.repository

    def get_module_environment(self, module: Union[str, Module]) -> Optional[str]:
        """Get module software environment by module/module_id."""
        if isinstance(module, str):
            modules = self.get_modules()
            module_obj = modules.get(module)
            if not module_obj:
                return None
            return module_obj.software_environment
        return module.software_environment

    def get_metric_collectors(self) -> List[MetricCollector]:
        """Get metric collectors."""
        return self.metric_collectors or []

    def is_initial(self, stage: Stage) -> bool:
        """Check if stage is initial (has no inputs)."""
        return stage.inputs is None or len(stage.inputs) == 0

    def get_outputs(self) -> Dict[str, IOFile]:
        """Get all outputs from all stages."""
        outputs: Dict[str, IOFile] = {}
        for stage in self.stages:
            for output in stage.outputs:
                outputs[output.id] = output
        return outputs

    def get_modules(self) -> Dict[str, Module]:
        """Get all modules from all stages."""
        modules: Dict[str, Module] = {}
        for stage in self.stages:
            for module in stage.modules:
                modules[module.id] = module
        return modules

    def get_easyconfigs(self) -> List[Optional[str]]:
        """Get easyconfigs from software environments."""
        return [env.easyconfig for env in self.software_environments]

    def get_conda_envs(self) -> List[Optional[str]]:
        """Get conda environment files from software environments."""
        return [env.conda for env in self.software_environments]

    def validate_structure(self, benchmark_dir: Optional[Path] = None) -> None:
        """
        Validate the benchmark structure after loading.

        This performs comprehensive validation including:
        - Unique IDs for stages, modules, and outputs
        - Valid file paths
        - Stage inputs reference existing outputs
        - Software environments are properly defined
        - Environment paths exist (when benchmark_dir is provided)

        Args:
            benchmark_dir: Directory containing the benchmark (for path validation)

        Raises:
            ValidationError: If validation fails
        """
        errors: List[str] = []

        # Store benchmark directory for environment path validation
        if benchmark_dir:
            self._benchmark_dir = benchmark_dir

        # 1. Validate unique IDs
        stage_ids = [stage.id for stage in self.stages]
        duplicate_stage_ids = _find_duplicates(stage_ids)
        if duplicate_stage_ids:
            errors.append(
                f"Found duplicate stage ids: {', '.join(duplicate_stage_ids)}"
            )

        all_modules = self.get_modules()
        module_ids = list(all_modules.keys())
        duplicate_module_ids = _find_duplicates(module_ids)
        if duplicate_module_ids:
            errors.append(
                f"Found duplicate module ids: {', '.join(duplicate_module_ids)}"
            )

        all_outputs = self.get_outputs()
        output_ids = list(all_outputs.keys())
        duplicate_output_ids = _find_duplicates(output_ids)
        if duplicate_output_ids:
            errors.append(
                f"Found duplicate output ids: {', '.join(duplicate_output_ids)}"
            )

        # 2. Validate output file paths
        for output in all_outputs.values():
            if output.path.strip() == "":
                errors.append(f"Output path for file {output.id} is empty")
            if os.path.isabs(output.path):
                errors.append(
                    f"Output path for file {output.id} must be relative, not absolute: {output.path}"
                )

        # 3. Validate stage inputs reference valid outputs
        for stage in self.stages:
            if stage.inputs:
                for input_collection in stage.inputs:
                    for input_id in input_collection.entries:
                        if input_id not in output_ids:
                            errors.append(
                                f"Input with id '{input_id}' in stage '{stage.id}' is not valid"
                            )

        # 4. Validate software environment references
        env_ids = {env.id for env in self.software_environments}

        # Check modules
        for module in all_modules.values():
            if module.software_environment not in env_ids:
                errors.append(
                    f"Software environment with id '{module.software_environment}' is not defined."
                )

        # Check metric collectors
        if self.metric_collectors:
            for collector in self.metric_collectors:
                if collector.software_environment not in env_ids:
                    errors.append(
                        f"Software environment with id '{collector.software_environment}' for metric collector '{collector.id}' is not defined."
                    )

                # Validate metric collector inputs
                for collector_input in collector.inputs:
                    if collector_input.id not in output_ids:
                        errors.append(
                            f"Input with id '{collector_input.id}' for metric collector '{collector.id}' is not valid."
                        )

        # 5. Validate software environment paths (if benchmark_dir provided)
        if benchmark_dir and self.software_backend != SoftwareBackendEnum.host:
            for env in self.software_environments:
                env_errors = self._validate_environment_path(env, benchmark_dir)
                errors.extend(env_errors)

        # Raise error if any validation failed
        if errors:
            raise ValidationError(errors)

    def _validate_environment_path(
        self, env: SoftwareEnvironment, benchmark_dir: Path
    ) -> List[str]:
        """Validate software environment path based on backend."""
        errors: List[str] = []

        # Get the appropriate environment configuration
        if self.software_backend == SoftwareBackendEnum.envmodules:
            if env.envmodule:
                # Import here to avoid circular dependency
                from omnibenchmark.utils import try_avail_envmodule

                if not try_avail_envmodule(env.envmodule):  # type: ignore[no-untyped-call]
                    errors.append(
                        f"Software environment with id '{env.id}' and name '{env.envmodule}' could not be loaded as a valid `envmodule`."
                    )
            else:
                errors.append(
                    f"Software environment with id '{env.id}' does not have a valid backend definition for: '{self.software_backend.value}'."
                )

        elif self.software_backend in [
            SoftwareBackendEnum.conda,
            SoftwareBackendEnum.docker,
            SoftwareBackendEnum.apptainer,
        ]:
            # Get the environment path based on backend
            env_path = None
            if self.software_backend == SoftwareBackendEnum.conda:
                env_path = env.conda
            elif self.software_backend in [
                SoftwareBackendEnum.docker,
                SoftwareBackendEnum.apptainer,
            ]:
                env_path = env.apptainer

            if not env_path:
                errors.append(
                    f"Software environment with id '{env.id}' does not have a valid backend definition for: '{self.software_backend.value}'."
                )
            elif not _is_url(env_path) and not Path(env_path).is_absolute():
                # Relative path - check relative to benchmark_dir
                full_path = benchmark_dir / env_path
                if not full_path.exists():
                    errors.append(
                        f"Software environment path for '{self.software_backend.value}' does not exist: '{full_path}'."
                    )
            elif not _is_url(env_path) and Path(env_path).is_absolute():
                # Absolute path - check directly
                if not Path(env_path).exists():
                    errors.append(
                        f"Software environment path for '{self.software_backend.value}' does not exist: '{env_path}'."
                    )

        return errors


def expand_output_path(file: IOFile) -> str:
    """
    Expands a relative output path into a standardized templated format.

    This function ensures output paths follow a consistent structure by:
    1. Prepending the standard OUTPUT_PATH_PREFIX if not already present
    2. Adding a {dataset} placeholder to the filename if not already included
    """
    # Import here to avoid circular imports
    OUTPUT_PATH_PREFIX = os.path.join("{input}", "{stage}", "{module}", "{params}")

    output_path = file.path
    if output_path.strip() == "":
        raise ValueError(f"Output path for file {file.id} is empty")

    if os.path.isabs(output_path):
        raise ValueError(
            f"Output path for file {file.id} must be relative, not absolute: {output_path}"
        )

    if not output_path.startswith(OUTPUT_PATH_PREFIX):
        output_path = os.path.join(OUTPUT_PATH_PREFIX, output_path)

    if "{dataset}" not in output_path:
        parts = output_path.rsplit(os.path.sep, 1)
        if len(parts) == 2:
            directory, filename = parts
            output_path = os.path.join(directory, f"{{dataset}}.{filename}")
        else:
            filename = parts[0]
            output_path = f"{{dataset}}.{filename}"

    return output_path


# For backwards compatibility
SoftwareEnvironmentId = str
