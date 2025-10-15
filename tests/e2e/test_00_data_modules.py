import pytest
from pathlib import Path
import shutil
import tempfile

from tests.cli.cli_setup import OmniCLISetup
from tests.e2e.result_validation import validate_pipeline_results, load_expected_results, get_test_name_from_function


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

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "00_data_modules.yaml"
    shutil.copy2(data_modules_config, config_file_in_tmp)

    # bundled_repos fixture already creates tmp_path/bundles symlink

    # Create dummy conda environment file for Snakemake 9.x validation
    # This is required because Snakemake 9.x validates environment files even when ignored
    dummy_env_content = """name: omnibenchmark-dummy
channels:
  - conda-forge
dependencies:
  - python=3.12
"""

    # Create in system temp directory where Snakemake looks for fallback files
    system_temp = Path(tempfile.gettempdir())
    (system_temp / "conda_not_provided.yml").write_text(dummy_env_content)

    # Set up output directory
    out_dir = tmp_path / "out"

    with OmniCLISetup() as omni:
        result = omni.call(
            [
                "run",
                "benchmark",
                "--benchmark",
                str(config_file_in_tmp),
                "--out-dir",
                str(out_dir),
                "--local-storage",
            ],
            cwd=str(tmp_path),
        )

        # Debug: Always print CLI output
        print(f"\n=== CLI EXECUTION DEBUG ===")
        print(f"Return code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
        print(f"=== END DEBUG ===\n")

        # Check that CLI execution succeeded
        assert result.returncode == 0, (
            f"CLI execution failed with return code {result.returncode}\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

        # Debug: Show actual directory structure before validation (if debugging)
        if keep_files:
            print(f"\n=== ACTUAL DIRECTORY STRUCTURE ===")
            print(f"Output directory: {out_dir}")
            all_files = list(out_dir.rglob("*"))
            for file_path in sorted(all_files):
                if file_path.is_file():
                    print(f"FILE: {file_path.relative_to(out_dir)}")
                else:
                    print(f"DIR:  {file_path.relative_to(out_dir)}/")
            print(f"=== END DIRECTORY STRUCTURE ===\n")

        # Load expected results from JSON file and validate
        expected_results = load_expected_results("00_data_modules")
        validate_pipeline_results(out_dir, expected_results, verbose=keep_files)

        # Additional verification: ensure we have the expected number of output files
        output_files = list(out_dir.rglob("*.json"))
        if keep_files:
            print(f"\nCreated {len(output_files)} total JSON output files:")
            for output_file in output_files:
                print(f"  - {output_file.relative_to(out_dir)}")

        # We expect at least 2 files (2 datasets)
        assert len(output_files) >= 2, (
            f"Expected at least 2 JSON files, but found {len(output_files)}"
        )


def test_data_modules_output_structure(
    data_modules_config, tmp_path, bundled_repos, keep_files
):
    """Test that the data modules pipeline creates the expected output directory structure."""

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "00_data_modules.yaml"
    shutil.copy2(data_modules_config, config_file_in_tmp)

    # bundled_repos fixture already creates tmp_path/bundles symlink

    # No need to copy envs - using dummy paths for Snakemake compatibility

    # Set up output directory
    out_dir = tmp_path / "out"

    with OmniCLISetup() as omni:
        result = omni.call(
            [
                "run",
                "benchmark",
                "--benchmark",
                str(config_file_in_tmp),
                "--out-dir",
                str(out_dir),
                "--local-storage",
            ],
            cwd=str(tmp_path),
        )

        # Debug: Always print CLI output
        print(f"\n=== CLI EXECUTION DEBUG (structure test) ===")
        print(f"Return code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
        print(f"=== END DEBUG ===\n")

        # Check that CLI execution succeeded
        assert result.returncode == 0, (
            f"CLI execution failed with return code {result.returncode}\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

        # Use result validation system to check structure and values
        expected_results = load_expected_results("00_data_modules")
        validate_pipeline_results(out_dir, expected_results, verbose=keep_files)


def test_data_modules_idempotent(
    data_modules_config, tmp_path, bundled_repos, keep_files
):
    """Test that running the same workflow twice produces identical results."""

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "00_data_modules.yaml"
    shutil.copy2(data_modules_config, config_file_in_tmp)

    # bundled_repos fixture already creates tmp_path/bundles symlink

    # No need to copy envs - using dummy paths for Snakemake compatibility

    # Set up output directory
    out_dir = tmp_path / "out"

    with OmniCLISetup() as omni:
        # First run
        result1 = omni.call(
            [
                "run",
                "benchmark",
                "--benchmark",
                str(config_file_in_tmp),
                "--out-dir",
                str(out_dir),
                "--local-storage",
            ],
            cwd=str(tmp_path),
        )

        # Debug: Always print CLI output for first run
        print(f"\n=== CLI EXECUTION DEBUG (first run) ===")
        print(f"Return code: {result1.returncode}")
        print(f"STDOUT:\n{result1.stdout}")
        print(f"STDERR:\n{result1.stderr}")
        print(f"=== END DEBUG ===\n")

        assert result1.returncode == 0, (
            f"First CLI execution failed with return code {result1.returncode}\n"
            f"STDOUT: {result1.stdout}\n"
            f"STDERR: {result1.stderr}"
        )

        # Get results from first run using validation
        expected_results = load_expected_results("00_data_modules")
        validate_pipeline_results(out_dir, expected_results, verbose=keep_files)

        # Store first run files for comparison
        first_run_files = {}
        for json_file in out_dir.rglob("*.json"):
            with open(json_file, 'r') as f:
                first_run_files[str(json_file.relative_to(out_dir))] = f.read()

        # Second run
        result2 = omni.call(
            [
                "run",
                "benchmark",
                "--benchmark",
                str(config_file_in_tmp),
                "--out-dir",
                str(out_dir),
                "--local-storage",
            ],
            cwd=str(tmp_path),
        )

        # Debug: Always print CLI output for second run
        print(f"\n=== CLI EXECUTION DEBUG (second run) ===")
        print(f"Return code: {result2.returncode}")
        print(f"STDOUT:\n{result2.stdout}")
        print(f"STDERR:\n{result2.stderr}")
        print(f"=== END DEBUG ===\n")

        assert result2.returncode == 0, (
            f"Second CLI execution failed with return code {result2.returncode}\n"
            f"STDOUT: {result2.stdout}\n"
            f"STDERR: {result2.stderr}"
        )

        # Validate second run results
        validate_pipeline_results(out_dir, expected_results, verbose=keep_files)

        # Compare all files to ensure idempotency
        for json_file in out_dir.rglob("*.json"):
            file_key = str(json_file.relative_to(out_dir))
            with open(json_file, 'r') as f:
                second_run_content = f.read()
            assert first_run_files[file_key] == second_run_content, (
                f"File {file_key} changed between runs"
            )


def test_data_modules_cli_validation(
    data_modules_config, tmp_path, bundled_repos, keep_files
):
    """Test that the CLI handles the benchmark config correctly."""

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "00_data_modules.yaml"
    shutil.copy2(data_modules_config, config_file_in_tmp)

    # bundled_repos fixture already creates tmp_path/bundles symlink

    # No need to copy envs - using dummy paths for Snakemake compatibility

    # Set up output directory
    out_dir = tmp_path / "out"

    with OmniCLISetup() as omni:
        result = omni.call(
            [
                "run",
                "benchmark",
                "--benchmark",
                str(config_file_in_tmp),
                "--out-dir",
                str(out_dir),
                "--local-storage",
            ],
            cwd=str(tmp_path),
        )

        # Debug: Always print CLI output
        print(f"\n=== CLI EXECUTION DEBUG (validation test) ===")
        print(f"Return code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
        print(f"=== END DEBUG ===\n")

        # Check that CLI execution succeeded
        assert result.returncode == 0, (
            f"CLI execution failed with return code {result.returncode}\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

        # Verify that output directory was created
        assert out_dir.exists(), "Output directory was not created"

        # Use result validation system for comprehensive validation
        expected_results = load_expected_results("00_data_modules")
        validate_pipeline_results(out_dir, expected_results, verbose=keep_files)
