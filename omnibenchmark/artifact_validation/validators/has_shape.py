"""Has shape validator implementation."""

from typing import Any, Dict, Optional, Tuple

from ..base import ValidationResult, ValidationStatus, Validator


class HasShapeValidator(Validator):
    """Validator that checks if data meets shape requirements."""

    @property
    def name(self) -> str:
        """Return the name of this validator."""
        return "has_shape"

    def validate(self, data: Any, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate that the data meets shape requirements.

        Args:
            data: The loaded data to validate (DataFrame, dict, or list)
            params: Parameters with optional 'min_rows', 'max_rows', 'min_cols', 'max_cols'

        Returns:
            ValidationResult with the outcome
        """
        try:
            # Extract shape constraints from params
            min_rows = params.get("min_rows")
            max_rows = params.get("max_rows")
            min_cols = params.get("min_cols")
            max_cols = params.get("max_cols")

            # If no constraints specified, skip validation
            if all(x is None for x in [min_rows, max_rows, min_cols, max_cols]):
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.SKIPPED,
                    message="No shape constraints specified",
                )

            # Get actual shape
            actual_rows, actual_cols = self._get_shape(data)

            if actual_rows is None or actual_cols is None:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.FAILED,
                    message=f"Cannot determine shape for data type {type(data).__name__}",
                )

            # Check constraints
            violations = []

            if min_rows is not None and actual_rows < min_rows:
                violations.append(f"rows ({actual_rows}) < min_rows ({min_rows})")

            if max_rows is not None and actual_rows > max_rows:
                violations.append(f"rows ({actual_rows}) > max_rows ({max_rows})")

            if min_cols is not None and actual_cols < min_cols:
                violations.append(f"cols ({actual_cols}) < min_cols ({min_cols})")

            if max_cols is not None and actual_cols > max_cols:
                violations.append(f"cols ({actual_cols}) > max_cols ({max_cols})")

            if violations:
                return ValidationResult(
                    rule=self.name,
                    status=ValidationStatus.FAILED,
                    message=f"Shape constraints violated: {'; '.join(violations)}",
                    details={
                        "actual_shape": (actual_rows, actual_cols),
                        "constraints": {
                            "min_rows": min_rows,
                            "max_rows": max_rows,
                            "min_cols": min_cols,
                            "max_cols": max_cols,
                        },
                    },
                )

            return ValidationResult(
                rule=self.name,
                status=ValidationStatus.PASSED,
                message="Shape constraints satisfied",
                details={
                    "actual_shape": (actual_rows, actual_cols),
                    "constraints": {
                        "min_rows": min_rows,
                        "max_rows": max_rows,
                        "min_cols": min_cols,
                        "max_cols": max_cols,
                    },
                },
            )

        except Exception as e:
            return ValidationResult(
                rule=self.name,
                status=ValidationStatus.ERROR,
                message=f"Error during validation: {str(e)}",
            )

    def _get_shape(self, data: Any) -> Tuple[Optional[int], Optional[int]]:
        """
        Get shape (rows, cols) from various data types.

        Args:
            data: The data to get shape from

        Returns:
            Tuple of (rows, cols) or (None, None) if cannot determine
        """
        # Check if it's a pandas DataFrame (without importing pandas)
        if hasattr(data, "shape"):
            try:
                return data.shape
            except Exception:
                pass

        elif isinstance(data, dict):
            # Check if it's a dict of lists/arrays (DataFrame-like)
            if all(isinstance(v, (list, tuple)) for v in data.values()):
                # All lists should have same length for valid shape
                lengths = [len(v) for v in data.values()]
                if lengths and all(length == lengths[0] for length in lengths):
                    return lengths[0], len(data)
                else:
                    # Inconsistent lengths, use max
                    return max(lengths) if lengths else 0, len(data)
            else:
                # Single record
                return 1, len(data)

        elif isinstance(data, list):
            if not data:
                return 0, 0

            # List of dicts (records)
            if all(isinstance(item, dict) for item in data):
                # Get max columns across all records
                all_keys = set()
                for item in data:
                    all_keys.update(item.keys())
                return len(data), len(all_keys)
            else:
                # List of values
                return len(data), 1

        return None, None
