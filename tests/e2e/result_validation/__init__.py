"""
Result validation module for omnibenchmark end-to-end tests.

This module provides functions for validating pipeline results and loading
expected results from configuration files.
"""

from .validation import validate_pipeline_results, load_expected_results, get_test_name_from_function

__all__ = ["validate_pipeline_results", "load_expected_results", "get_test_name_from_function"]
