import pytest
from pathlib import Path

from tests.e2e.common import (
    E2ETestRunner,
)


@pytest.fixture
def cartesian_product_exclude_config():
    """Get the path to the cartesian product exclude config."""
    config_path = (
        Path(__file__).parent / "configs" / "05_cartesian_product_exclude.yaml"
    )
    return config_path


def test_cartesian_product_exclude_pipeline(
    cartesian_product_exclude_config, tmp_path, bundled_repos, keep_files
):
    """Test a cartesian product pipeline with exclude functionality.

    This test demonstrates the exclude keyword functionality where:
    - 3 datasets (D1, D2, D3) are processed by 2 methods (M1, M2)
    - D2 excludes M2, preventing the D2-M2 combination from executing
    - Expected results: D1 works with both M1&M2, D2 works only with M1, D3 works with both M1&M2
    - Total execution paths: 5 method results (D1-M1, D1-M2, D2-M1, D3-M1, D3-M2)
    """
    runner = E2ETestRunner(tmp_path, keep_files)
    config_file_in_tmp = runner.setup_test_environment(
        cartesian_product_exclude_config,
        "05_cartesian_product_exclude.yaml",
    )

    # Execute CLI with default args
    runner.execute_cli_command(config_file_in_tmp, ["--continue-on-error", "-y"])

    # Validate results
    runner.validate_results("05_cartesian_product_exclude")

    # Verify expected file counts:
    # - 3 data files (D1, D2, D3)
    # - 5 method files (D1-M1, D1-M2, D2-M1, D3-M1, D3-M2) - note D2-M2 is excluded
    runner.verify_output_file_count(3, "*_data.json")
    runner.verify_output_file_count(5, "*_method.json")


def test_cartesian_product_exclude_idempotent(
    cartesian_product_exclude_config, tmp_path, bundled_repos, keep_files
):
    """Test that running the cartesian product exclude workflow twice produces identical results."""
    from tests.e2e.common import (
        store_pipeline_files,
        compare_pipeline_runs,
        extract_test_name_from_config,
    )

    runner = E2ETestRunner(tmp_path, keep_files)
    config_filename = "05_cartesian_product_exclude.yaml"
    test_name = extract_test_name_from_config(config_filename)

    # Setup environment
    config_file_in_tmp = runner.setup_test_environment(
        cartesian_product_exclude_config, config_filename
    )

    # First run
    runner.execute_cli_command(
        config_file_in_tmp, ["--continue-on-error", "-y"], debug_label="first run"
    )
    runner.validate_results(test_name)

    # Store first run files for comparison
    first_run_files = store_pipeline_files(runner.out_dir, "*.json")

    # Second run
    runner.execute_cli_command(
        config_file_in_tmp, ["--continue-on-error", "-y"], debug_label="second run"
    )
    runner.validate_results(test_name)

    # Compare files to ensure idempotency
    compare_pipeline_runs(runner.out_dir, first_run_files, "*.json")
