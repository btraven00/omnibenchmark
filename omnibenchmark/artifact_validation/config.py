"""Configuration parser for validation YAML files."""

from pathlib import Path
from typing import Dict, Union

import yaml

from .base import (
    FileRule,
    StageValidation,
    ValidationConfig as ValidationConfigModel,
    ValidationRule,
)


def parse_validation_file(file_path: Union[str, Path]) -> ValidationConfigModel:
    """
    Parse a validation YAML file.

    Args:
        file_path: Path to the validation.yaml file

    Returns:
        ValidationConfigModel instance

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is invalid
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Validation file not found: {file_path}")

    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML file: {e}")

    return parse_validation_config(data)


def parse_validation_config(data: Dict) -> ValidationConfigModel:
    """
    Parse validation configuration from a dictionary.

    Args:
        data: Dictionary representation of the config

    Returns:
        ValidationConfigModel instance
    """
    stages = {}

    for stage_name, stage_data in data.get("stages", {}).items():
        rules = []

        for rule_data in stage_data.get("rules", []):
            validations = []

            for val_data in rule_data.get("validations", []):
                if isinstance(val_data, dict):
                    val_type = val_data.pop("type", None)
                    if val_type:
                        validation = ValidationRule(type=val_type, params=val_data)
                    else:
                        raise ValueError(f"Validation rule missing 'type': {val_data}")
                else:
                    validation = ValidationRule(type=str(val_data))
                validations.append(validation)

            file_rule = FileRule(
                file_pattern=rule_data["file_pattern"], validations=validations
            )
            rules.append(file_rule)

        stages[stage_name] = StageValidation(rules=rules)

    return ValidationConfigModel(version=data.get("version", "1.0"), stages=stages)


def discover_validation_config(directory: Union[str, Path]) -> Path:
    """
    Auto-discover validation.yaml in a directory.

    Args:
        directory: Directory to search in

    Returns:
        Path to the validation file

    Raises:
        FileNotFoundError: If no validation file is found
    """
    directory = Path(directory)
    candidates = ["validation.yaml", "validation.yml"]

    for candidate in candidates:
        config_path = directory / candidate
        if config_path.exists():
            return config_path

    raise FileNotFoundError(
        f"No validation file found in {directory}. "
        f"Looked for: {', '.join(candidates)}"
    )
