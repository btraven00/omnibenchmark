"""Not empty validator implementation."""

from pathlib import Path
from typing import Any, Dict

from ..base import ValidationResult, ValidationStatus, Validator


class NotEmptyValidator(Validator):
    """Validator that checks if a file/data is not empty."""

    @property
    def name(self) -> str:
        """Return the name of this validator."""
        return "not_empty"

    def validate(self, data: Any, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate that the data is not empty.

        Args:
            data: The loaded data to validate (can be DataFrame, dict, list, or Path)
            params: Parameters for the validation rule (not used for this validator)

        Returns:
            ValidationResult with the outcome
        """
        try:
            # Handle different data types
            if isinstance(data, Path):
                # Check file size
                if not data.exists():
                    return ValidationResult(
                        rule=self.name,
                        status=ValidationStatus.FAILED,
                        message="File does not exist",
                    )

                if data.stat().st_size == 0:
                    return ValidationResult(
                        rule=self.name,
                        status=ValidationStatus.FAILED,
                        message="File is empty (0 bytes)",
                    )

                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.PASSED,
                    message="File exists and is not empty",
                )

            # Check if it's a pandas DataFrame (without importing pandas)
            elif hasattr(data, "empty") and hasattr(data, "shape"):
                # Likely a pandas DataFrame
                if data.empty:
                    return ValidationResult(
                        rule=self.name,
                        status=ValidationStatus.FAILED,
                        message="DataFrame is empty",
                        details={"shape": data.shape},
                    )

                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.PASSED,
                    message="DataFrame is not empty",
                    details={"shape": data.shape},
                )

            elif isinstance(data, (dict, list)):
                if len(data) == 0:
                    return ValidationResult(
                        rule=self.name,
                        status=ValidationStatus.FAILED,
                        message=f"{type(data).__name__} is empty",
                        details={"length": 0},
                    )

                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.PASSED,
                    message=f"{type(data).__name__} is not empty",
                    details={"length": len(data)},
                )

            elif data is None:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.FAILED,
                    message="Data is None",
                )

            else:
                # For other types, consider them not empty
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.PASSED,
                    message=f"Data of type {type(data).__name__} is not empty",
                )

        except Exception as e:
            return ValidationResult(
                rule=self.name,
                status=ValidationStatus.ERROR,
                message=f"Error during validation: {str(e)}",
            )
