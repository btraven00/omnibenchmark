"""Has columns validator implementation."""

from typing import Any, Dict, Set

from ..base import ValidationResult, ValidationStatus, Validator


class HasColumnsValidator(Validator):
    """Validator that checks if data has required columns."""

    @property
    def name(self) -> str:
        """Return the name of this validator."""
        return "has_columns"

    def validate(self, data: Any, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate that the data has required columns.

        Args:
            data: The loaded data to validate (DataFrame, dict, or list of dicts)
            params: Parameters with 'columns' key containing list of required columns

        Returns:
            ValidationResult with the outcome
        """
        try:
            # Get required columns from params
            required_columns = params.get("columns", [])
            if not required_columns:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.SKIPPED,
                    message="No columns specified to check",
                )

            # Convert to set for easier comparison
            required_set = set(required_columns)

            # Extract columns based on data type
            actual_columns = self._extract_columns(data)

            if actual_columns is None:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.FAILED,
                    message=f"Cannot extract columns from data type {type(data).__name__}",
                )

            # Check for missing columns
            missing_columns = required_set - actual_columns

            if missing_columns:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.FAILED,
                    message=f"Missing required columns: {sorted(missing_columns)}",
                    details={
                        "required": sorted(required_columns),
                        "actual": sorted(actual_columns),
                        "missing": sorted(missing_columns),
                    },
                )

            return ValidationResult(
                rule=self.name,
                status=ValidationStatus.PASSED,
                message="All required columns present",
                details={
                    "required": sorted(required_columns),
                    "actual": sorted(actual_columns),
                },
            )

        except Exception as e:
            return ValidationResult(
                rule=self.name,
                status=ValidationStatus.ERROR,
                message=f"Error during validation: {str(e)}",
            )

    def _extract_columns(self, data: Any) -> Set[str]:
        """
        Extract column names from various data types.

        Args:
            data: The data to extract columns from

        Returns:
            Set of column names, or None if cannot extract
        """
        # Check if it's a pandas DataFrame (without importing pandas)
        if hasattr(data, "columns"):
            try:
                return set(data.columns.tolist())
            except Exception:
                # If tolist() fails, try other methods
                try:
                    return set(list(data.columns))
                except Exception:
                    pass

        elif isinstance(data, dict):
            # Check if it's a dict of lists/arrays (DataFrame-like)
            if all(isinstance(v, (list, tuple)) for v in data.values()):
                return set(data.keys())
            # Single record
            return set(data.keys())

        elif isinstance(data, list) and data:
            # List of dicts (records)
            if all(isinstance(item, dict) for item in data):
                # Get union of all keys
                columns = set()
                for item in data:
                    columns.update(item.keys())
                return columns

        return None
