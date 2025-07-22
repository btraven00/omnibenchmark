"""Utilities for handling optional dependencies."""

import importlib
from typing import Any


def import_pandas() -> Any:
    """Import pandas with a helpful error message if not installed."""
    try:
        return importlib.import_module("pandas")
    except ImportError:
        raise ImportError(
            "pandas is required for artifact validation. "
            "Please install it with: pip install omnibenchmark[validation]"
        )


def import_numpy() -> Any:
    """Import numpy with a helpful error message if not installed."""
    try:
        return importlib.import_module("numpy")
    except ImportError:
        raise ImportError(
            "numpy is required for artifact validation. "
            "Please install it with: pip install omnibenchmark[validation]"
        )
