import pytest
from pathlib import Path

from tests.e2e.common import (
    E2ETestRunner,
    run_standard_pipeline_test,
    store_pipeline_files,
    compare_pipeline_runs,
    extract_test_name_from_config,
)


@pytest.fixture
def data_modules_config():
    """Get the path to the data modules config."""
    config_path = Path(__file__).parent / "configs" / "00_data_modules.yaml"
    return config_path


def test_data_modules_pipeline(
    data_modules_config, tmp_path, bundled_repos, keep_files
):
    """Test a data modules pipeline using the omnibenchmark CLI.

    This is a black-box test - we execute the CLI and validate outputs.
    """
    run_standard_pipeline_test(
        config_path=data_modules_config,
        config_filename="00_data_modules.yaml",
        test_name="00_data_modules",
        tmp_path=tmp_path,
        keep_files=keep_files,
        min_expected_files=2,  # We expect 2 data files (D1_data.json, D2_data.json, excluding symlinks)
    )


def test_data_modules_output_structure(
    data_modules_config, tmp_path, bundled_repos, keep_files
):
    """Test that the data modules pipeline creates the expected output directory structure."""
    run_standard_pipeline_test(
        config_path=data_modules_config,
        config_filename="00_data_modules.yaml",
        test_name="00_data_modules",
        tmp_path=tmp_path,
        keep_files=keep_files,
        min_expected_files=2,
    )


def test_data_modules_idempotent(
    data_modules_config, tmp_path, bundled_repos, keep_files
):
    """Test that running the same workflow twice produces identical results."""
    runner = E2ETestRunner(tmp_path, keep_files)
    config_filename = "00_data_modules.yaml"
    test_name = extract_test_name_from_config(config_filename)

    # Setup environment
    config_file_in_tmp = runner.setup_test_environment(
        data_modules_config, config_filename
    )

    # First run
    runner.execute_cli_command(config_file_in_tmp, debug_label="first run")
    runner.validate_results(test_name)

    # Store first run files for comparison
    first_run_files = store_pipeline_files(runner.out_dir)

    # Second run
    runner.execute_cli_command(config_file_in_tmp, debug_label="second run")
    runner.validate_results(test_name)

    # Compare files to ensure idempotency
    compare_pipeline_runs(runner.out_dir, first_run_files)


def test_data_modules_cli_validation(
    data_modules_config, tmp_path, bundled_repos, keep_files
):
    """Test that the CLI handles the benchmark config correctly."""
    # This test is functionally identical to the basic pipeline test
    # The CLI validation is inherent in the execution and result validation
    run_standard_pipeline_test(
        config_path=data_modules_config,
        config_filename="00_data_modules.yaml",
        test_name="00_data_modules",
        tmp_path=tmp_path,
        keep_files=keep_files,
        min_expected_files=2,
    )
