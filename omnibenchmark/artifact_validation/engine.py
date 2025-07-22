"""Main validation engine for artifact validation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from .base import (
    ModuleValidationResult,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
)
from .config import parse_validation_file, discover_validation_config
from .loaders.registry import get_global_registry as get_loader_registry
from .validators.registry import get_global_registry as get_validator_registry


class ValidationEngine:
    """Main engine for validating module artifacts."""

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        loader_registry=None,
        validator_registry=None,
    ):
        """
        Initialize the validation engine.

        Args:
            config_path: Optional path to validation.yaml file
            loader_registry: Optional custom loader registry
            validator_registry: Optional custom validator registry

        TODO: Add dynamic plugin loading capability
        -----
        Future extension for loading validators and loaders from external sources:

        1. Plugin discovery from directories:
           - Load from ~/.omnibenchmark/plugins/
           - Load from project-local plugins/ directory
           - Use importlib to dynamically import modules

        2. Plugin registration via entry points:
           - Use setuptools entry points for third-party plugins
           - Example: omnibenchmark.validators, omnibenchmark.loaders

        3. Plugin API:
           - Define plugin interface/protocol
           - Version compatibility checking
           - Plugin metadata (name, version, author)

        4. Implementation approach:
           - Use pluggy or similar plugin framework
           - Or simple importlib-based discovery:
             ```python
             def load_plugins(self, plugin_dir: Path):
                 for py_file in plugin_dir.glob("*.py"):
                     spec = importlib.util.spec_from_file_location(...)
                     module = importlib.util.module_from_spec(spec)
                     spec.loader.exec_module(module)
                     # Discover and register Validator/Loader subclasses
             ```

        Note: The module is named 'artifact_validation' instead of 'validation' to:
        - Be more specific about its purpose (validating module output artifacts)
        - Avoid confusion with the existing omnibenchmark.benchmark.validation module
        - Leave room for future validation types (e.g., workflow validation, config validation)
        """
        self.config_path = Path(config_path) if config_path else None
        self.config = None
        self.loader_registry = loader_registry or get_loader_registry()
        self.validator_registry = validator_registry or get_validator_registry()

        if self.config_path:
            self.load_config(self.config_path)

    def load_config(self, config_path: Union[str, Path]) -> None:
        """Load validation configuration from file."""
        self.config_path = Path(config_path)
        self.config = parse_validation_file(self.config_path)

    def discover_config(self, directory: Union[str, Path]) -> None:
        """Auto-discover and load validation.yaml from directory."""
        config_path = discover_validation_config(directory)
        self.load_config(config_path)

    def validate_file(
        self,
        file_path: Union[str, Path],
        rules: List[Dict],
        stage: str = "unknown",
        module: str = "unknown",
    ) -> ModuleValidationResult:
        """Validate a single file against a list of rules."""
        file_path = Path(file_path)
        validations = []
        overall_status = ValidationStatus.PASSED

        # Check if file exists
        if not file_path.exists():
            validations.append(
                ValidationResult(
                    rule="file_exists",
                    status=ValidationStatus.FAILED,
                    message=f"File not found: {file_path}",
                )
            )
            overall_status = ValidationStatus.FAILED
        else:
            # Get appropriate loader
            loader = self.loader_registry.get_loader(file_path)

            # Try to load the file
            data = None
            load_error = None
            if loader:
                try:
                    data = loader.load(file_path)
                except Exception as e:
                    load_error = str(e)
            else:
                load_error = f"No loader available for file type: {file_path.suffix}"

            # Apply each validation rule
            for rule_config in rules:
                rule_type = rule_config.get("type")
                params = {k: v for k, v in rule_config.items() if k != "type"}

                # Get validator
                validator = self.validator_registry.get_validator(rule_type)

                if not validator:
                    result = ValidationResult(
                        rule=rule_type,
                        status=ValidationStatus.ERROR,
                        message=f"Unknown validator: {rule_type}",
                    )
                elif load_error and rule_type != "not_empty":
                    result = ValidationResult(
                        rule=rule_type,
                        status=ValidationStatus.ERROR,
                        message=f"Cannot validate - file load error: {load_error}",
                    )
                else:
                    # Run validation
                    if rule_type == "not_empty" and data is None:
                        result = validator.validate(file_path, params)
                    else:
                        result = validator.validate(data, params)

                validations.append(result)

                # Update overall status
                if result.status == ValidationStatus.FAILED:
                    overall_status = ValidationStatus.FAILED
                elif (
                    result.status == ValidationStatus.ERROR
                    and overall_status != ValidationStatus.FAILED
                ):
                    overall_status = ValidationStatus.ERROR

        return ModuleValidationResult(
            stage=stage,
            module=module,
            status=overall_status,
            validations=validations,
        )

    def validate_stage(
        self,
        stage_name: str,
        results_dir: Union[str, Path],
    ) -> List[ModuleValidationResult]:
        """Validate all modules in a stage."""
        if not self.config:
            raise ValueError("No validation configuration loaded")

        if stage_name not in self.config.stages:
            raise ValueError(f"Unknown stage: {stage_name}")

        results_dir = Path(results_dir)
        stage_config = self.config.stages[stage_name]
        results = []

        # Find stage output directory
        stage_dir = results_dir / stage_name
        if not stage_dir.exists():
            return []

        # Validate each module in the stage
        for module_dir in stage_dir.iterdir():
            if not module_dir.is_dir():
                continue

            module_name = module_dir.name

            # Apply each file rule
            for file_rule in stage_config.rules:
                pattern = file_rule.file_pattern

                # Replace placeholders in pattern
                pattern = pattern.replace("{module}", module_name)
                pattern = pattern.replace("{stage}", stage_name)

                # Find matching files
                matching_files = list(module_dir.glob(pattern))

                if not matching_files:
                    # No matching files - this is a validation failure
                    result = ModuleValidationResult(
                        stage=stage_name,
                        module=module_name,
                        status=ValidationStatus.FAILED,
                        validations=[
                            ValidationResult(
                                rule="file_pattern",
                                status=ValidationStatus.FAILED,
                                message=f"No files matching pattern: {pattern}",
                            )
                        ],
                    )
                    results.append(result)
                else:
                    # Validate each matching file
                    for file_path in matching_files:
                        validations = []
                        for rule_dict in file_rule.validations:
                            rule_type = rule_dict.type
                            params = rule_dict.params
                            result = self.validate_file(
                                file_path,
                                [{"type": rule_type, **params}],
                                stage_name,
                                module_name,
                            )
                            validations.extend(result.validations)

                        # Aggregate results
                        overall_status = ValidationStatus.PASSED
                        for val in validations:
                            if val.status == ValidationStatus.FAILED:
                                overall_status = ValidationStatus.FAILED
                                break
                            elif val.status == ValidationStatus.ERROR:
                                overall_status = ValidationStatus.ERROR

                        results.append(
                            ModuleValidationResult(
                                stage=stage_name,
                                module=module_name,
                                status=overall_status,
                                validations=validations,
                            )
                        )

        return results

    def validate_all(
        self,
        results_dir: Union[str, Path],
        benchmark_name: Optional[str] = None,
    ) -> ValidationReport:
        """Validate all stages and modules."""
        if not self.config:
            raise ValueError("No validation configuration loaded")

        results_dir = Path(results_dir)
        all_results = []

        # Validate each stage
        for stage_name in self.config.stages:
            stage_results = self.validate_stage(stage_name, results_dir)
            all_results.extend(stage_results)

        # Calculate summary statistics
        total_modules = len(all_results)
        passed_modules = sum(
            1 for r in all_results if r.status == ValidationStatus.PASSED
        )
        failed_modules = sum(
            1 for r in all_results if r.status == ValidationStatus.FAILED
        )

        return ValidationReport(
            validation_timestamp=datetime.utcnow().isoformat() + "Z",
            benchmark=benchmark_name,
            total_modules=total_modules,
            passed_modules=passed_modules,
            failed_modules=failed_modules,
            results=all_results,
        )

    def format_results(
        self,
        report: ValidationReport,
        format: str = "human",
    ) -> str:
        """Format validation results for output."""
        if format == "json":
            return json.dumps(report.dict(), indent=2)
        else:
            # Human-readable format
            lines = []
            lines.append(f"Validation Report - {report.validation_timestamp}")
            if report.benchmark:
                lines.append(f"Benchmark: {report.benchmark}")
            lines.append("")
            lines.append(f"Total modules: {report.total_modules}")
            lines.append(f"Passed: {report.passed_modules}")
            lines.append(f"Failed: {report.failed_modules}")
            lines.append("")

            # Group by stage
            by_stage = {}
            for result in report.results:
                if result.stage not in by_stage:
                    by_stage[result.stage] = []
                by_stage[result.stage].append(result)

            for stage, stage_results in sorted(by_stage.items()):
                lines.append(f"Stage: {stage}")
                lines.append("-" * 50)

                for result in stage_results:
                    status_symbol = (
                        "✓" if result.status == ValidationStatus.PASSED else "✗"
                    )
                    lines.append(
                        f"  {status_symbol} Module: {result.module} - {result.status}"
                    )

                    if result.status != ValidationStatus.PASSED:
                        for val in result.validations:
                            if val.status != ValidationStatus.PASSED:
                                lines.append(f"    - {val.rule}: {val.message}")

                lines.append("")

            return "\n".join(lines)
