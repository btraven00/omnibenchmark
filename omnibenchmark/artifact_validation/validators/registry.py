"""Registry for validators."""

from typing import Dict, Optional

from ..base import Validator


class ValidatorRegistry:
    """Registry for managing validators."""

    def __init__(self):
        """Initialize the validator registry."""
        self._validators: Dict[str, Validator] = {}

    def register(self, validator: Validator, name: Optional[str] = None) -> None:
        """
        Register a validator.

        Args:
            validator: Validator instance to register
            name: Optional name for the validator (defaults to validator.name)
        """
        if name is None:
            name = validator.name

        self._validators[name] = validator

    def get_validator(self, name: str) -> Optional[Validator]:
        """
        Get a validator by name.

        Args:
            name: Name of the validator

        Returns:
            Validator instance or None if not found
        """
        return self._validators.get(name)

    @classmethod
    def create_default(cls) -> "ValidatorRegistry":
        """
        Create a registry with default validators.

        Returns:
            ValidatorRegistry with built-in validators registered
        """
        from .not_empty import NotEmptyValidator
        from .has_columns import HasColumnsValidator
        from .has_shape import HasShapeValidator
        from .not_na import NotNaValidator

        registry = cls()
        registry.register(NotEmptyValidator())
        registry.register(HasColumnsValidator())
        registry.register(HasShapeValidator())
        registry.register(NotNaValidator())
        return registry


# Global registry instance
_global_registry = None


def get_global_registry() -> ValidatorRegistry:
    """Get or create the global validator registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ValidatorRegistry.create_default()
    return _global_registry
