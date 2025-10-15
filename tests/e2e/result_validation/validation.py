"""
Validation utilities for omnibenchmark end-to-end tests.

This module provides functions to validate pipeline results and load expected
results from configuration files.

It relies on the companion dummymodule structure, that is used to exercise e2e tests.
"""

import json
from pathlib import Path
from typing import Dict


def validate_pipeline_results(output_dir: Path, expected_results: Dict[str, int], verbose: bool = False) -> None:
    """
    Validate that JSON files in the output directory contain expected results.

    Args:
        output_dir: Path to the output directory to search
        expected_results: Dict mapping glob patterns to expected 'result' values
                         e.g., {"D1/D1_data.json": 15, "D2/methods/M1/*/D2_data.json": 125}
        verbose: If True, print detailed validation info

    Raises:
        AssertionError: If any expected result doesn't match or files are missing
    """
    if verbose:
        print(f"\n=== VALIDATING PIPELINE RESULTS ===")

    for glob_pattern, expected_value in expected_results.items():
        if verbose:
            print(f"Looking for pattern: {glob_pattern} (expecting result={expected_value})")

        # Find files matching the glob pattern
        matching_files = list(output_dir.glob(glob_pattern))

        assert len(matching_files) > 0, (
            f"No files found matching pattern '{glob_pattern}' in {output_dir}"
        )

        if verbose:
            print(f"  Found {len(matching_files)} matching file(s):")

        # Validate each matching file
        for file_path in matching_files:
            if verbose:
                print(f"    - {file_path.relative_to(output_dir)}")

            # Check that file exists
            assert file_path.exists(), f"File {file_path} does not exist"

            # Load and validate JSON content
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                raise AssertionError(f"Failed to load JSON from {file_path}: {e}")

            # Check that 'error' field is None (no errors occurred)
            if 'error' in data:
                assert data['error'] is None, (
                    f"Error found in {file_path}: {data['error']}"
                )
                if verbose:
                    print(f"      ✓ error=None (no errors)")

            # Check that 'result' field exists and matches expected value
            assert 'result' in data, (
                f"Missing 'result' field in {file_path}. Available fields: {list(data.keys())}"
            )

            actual_result = data['result']
            assert actual_result == expected_value, (
                f"Expected {expected_value}, got {actual_result}"
            )

            if verbose:
                print(f"      ✓ result={actual_result} (matches expected)")

    if verbose:
        print(f"=== ALL RESULTS VALIDATED SUCCESSFULLY ===\n")


def load_expected_results(test_name: str, configs_dir: Path = None) -> Dict[str, int]:
    """
    Load expected results from a JSON file based on test name.

    Args:
        test_name: Name of the test (without 'test_' prefix)
        configs_dir: Directory containing config files (defaults to configs/ relative to caller)

    Returns:
        Dictionary mapping glob patterns to expected result values

    Raises:
        FileNotFoundError: If the expected results file doesn't exist
        json.JSONDecodeError: If the JSON file is malformed
    """
    if configs_dir is None:
        # Default to configs directory relative to the test file
        configs_dir = Path(__file__).parent.parent / "configs"

    expected_file = configs_dir / f"{test_name}.expected.json"

    if not expected_file.exists():
        raise FileNotFoundError(f"Expected results file not found: {expected_file}")

    try:
        with open(expected_file, 'r') as f:
            expected_results = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in expected results file {expected_file}: {e}")

    return expected_results


def get_test_name_from_function(test_function_name: str) -> str:
    """
    Extract test name from pytest function name.

    Args:
        test_function_name: Full pytest function name (e.g., 'test_linear_arithmetic_with_methods_pipeline')

    Returns:
        Clean test name without 'test_' prefix and '_pipeline' suffix
        (e.g., 'linear_arithmetic_with_methods')
    """
    name = test_function_name

    # Remove 'test_' prefix
    if name.startswith('test_'):
        name = name[5:]

    # Remove common suffixes
    suffixes = ['_pipeline', '_test', '_e2e']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    return name
