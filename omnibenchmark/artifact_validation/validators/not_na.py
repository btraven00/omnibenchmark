"""Not NA validator implementation."""

from typing import Any, Dict

from ..base import ValidationResult, ValidationStatus, Validator
from ..utils import import_pandas, import_numpy


class NotNaValidator(Validator):
    """Validator that checks if specified columns don't contain all NA values."""

    def __init__(self):
        """Initialize the validator."""
        self._pd = None
        self._np = None

    @property
    def name(self) -> str:
        """Return the name of this validator."""
        return "not_na"

    @property
    def pd(self):
        """Lazy import pandas."""
        if self._pd is None:
            self._pd = import_pandas()
        return self._pd

    @property
    def np(self):
        """Lazy import numpy."""
        if self._np is None:
            self._np = import_numpy()
        return self._np

    def validate(self, data: Any, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate that specified columns don't contain all NA values.

        Args:
            data: The loaded data to validate (DataFrame, dict, or list of dicts)
            params: Parameters with 'columns' key containing list of columns to check

        Returns:
            ValidationResult with the outcome
        """
        try:
            # Get columns to check from params
            columns_to_check = params.get("columns", [])
            if not columns_to_check:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.SKIPPED,
                    message="No columns specified to check for NA values",
                )

            # Convert data to DataFrame if possible
            df = self._to_dataframe(data)
            if df is None:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.FAILED,
                    message=f"Cannot check NA values for data type {type(data).__name__}",
                )

            # Check each specified column
            all_na_columns = []
            missing_columns = []
            na_counts = {}

            for col in columns_to_check:
                if col not in df.columns:
                    missing_columns.append(col)
                else:
                    na_count = df[col].isna().sum()
                    total_count = len(df[col])
                    na_counts[col] = {
                        "na_count": int(na_count),
                        "total_count": int(total_count),
                        "na_percentage": float(na_count / total_count * 100)
                        if total_count > 0
                        else 0,
                    }

                    # Check if all values are NA
                    if na_count == total_count and total_count > 0:
                        all_na_columns.append(col)

            # Prepare result based on findings
            if missing_columns:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.FAILED,
                    message=f"Columns not found: {missing_columns}",
                    details={
                        "missing_columns": missing_columns,
                        "available_columns": list(df.columns),
                    },
                )

            if all_na_columns:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.FAILED,
                    message=f"Columns contain all NA values: {all_na_columns}",
                    details={
                        "all_na_columns": all_na_columns,
                        "na_statistics": na_counts,
                    },
                )

            return ValidationResult(
                rule=self.name,
                status=ValidationStatus.PASSED,
                message="No columns contain all NA values",
                details={"na_statistics": na_counts},
            )

        except Exception as e:
            return ValidationResult(
                rule=self.name,
                status=ValidationStatus.ERROR,
                message=f"Error during validation: {str(e)}",
            )

    def _to_dataframe(self, data: Any):
        """
        Convert various data types to DataFrame.

        Args:
            data: The data to convert

        Returns:
            DataFrame or None if cannot convert
        """
        # If it's already a DataFrame
        if hasattr(data, "isna") and hasattr(data, "columns"):
            return data

        # For other data types, we need pandas
        pd = self.pd

        if isinstance(data, dict):
            try:
                # Try to create DataFrame from dict
                if all(isinstance(v, (list, tuple)) for v in data.values()):
                    return pd.DataFrame(data)
                else:
                    # Single record
                    return pd.DataFrame([data])
            except Exception:
                return None

        elif isinstance(data, list) and data:
            try:
                # List of dicts
                if all(isinstance(item, dict) for item in data):
                    return pd.DataFrame(data)
            except Exception:
                return None

        return None
