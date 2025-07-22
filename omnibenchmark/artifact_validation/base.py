"""Base classes and models for the validation engine."""

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """Status of a validation rule execution."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class ValidationResult(BaseModel):
    """Result of a single validation rule execution."""

    rule: str
    status: ValidationStatus
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ModuleValidationResult(BaseModel):
    """Validation results for a single module."""

    stage: str
    module: str
    status: ValidationStatus
    validations: List[ValidationResult] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """Complete validation report for a benchmark."""

    validation_timestamp: str
    benchmark: Optional[str] = None
    total_modules: int = 0
    passed_modules: int = 0
    failed_modules: int = 0
    results: List[ModuleValidationResult] = Field(default_factory=list)


class Validator(ABC):
    """Abstract base class for validators."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this validator (e.g., 'not_empty')."""
        pass

    @abstractmethod
    def validate(self, data: Any, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate the data against the rule.

        Args:
            data: The loaded data to validate
            params: Parameters for the validation rule

        Returns:
            ValidationResult with the outcome
        """
        pass


class DataLoader(ABC):
    """Abstract base class for data loaders."""

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of supported file extensions (e.g., ['.csv', '.tsv'])."""
        pass

    @abstractmethod
    def load(self, file_path: Path) -> Any:
        """
        Load data from the file.

        Args:
            file_path: Path to the file to load

        Returns:
            Loaded data in a format suitable for validators

        Raises:
            Exception: If the file cannot be loaded
        """
        pass

    def can_load(self, file_path: Path) -> bool:
        """Check if this loader can handle the file."""
        return file_path.suffix.lower() in self.supported_extensions


class ValidationRule(BaseModel):
    """A single validation rule from the DSL."""

    type: str
    params: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        """Custom init to handle DSL parsing."""
        if "type" in data:
            rule_type = data.pop("type")
            super().__init__(type=rule_type, params=data)
        else:
            super().__init__(**data)


class FileRule(BaseModel):
    """File pattern and associated validations."""

    file_pattern: str
    validations: List[ValidationRule]


class StageValidation(BaseModel):
    """Validation rules for a stage."""

    rules: List[FileRule]


class ValidationConfig(BaseModel):
    """Complete validation configuration."""

    version: str = "1.0"
    stages: Dict[str, StageValidation]
