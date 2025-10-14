import json
import pytest
from pathlib import Path
import shutil
import tempfile

from tests.cli.cli_setup import OmniCLISetup


@pytest.fixture
def linear_arithmetic_config():
    """Get the path to the static linear arithmetic config."""
    config_path = Path(__file__).parent / "configs" / "linear_arithmetic.yaml"
    return config_path


def test_linear_arithmetic_pipeline(
    linear_arithmetic_config, tmp_path, bundled_repos, keep_files
):
    """Test a complete linear arithmetic pipeline using the omnibenchmark CLI.

    This is a black-box test - we execute the CLI and validate outputs.
    """

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "linear_arithmetic.yaml"
    shutil.copy2(linear_arithmetic_config, config_file_in_tmp)

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

        # Now validate outputs contain expected values

        # Check D1 data stage output (1+2+3+4+5 = 15)
        d1_data_file = out_dir / "data" / "D1" / "evaluate-1+2+3+4+5" / "D1_data.json"
        assert d1_data_file.exists(), f"D1 data output not found: {d1_data_file}"

        with open(d1_data_file) as f:
            d1_data_result = json.load(f)
        assert d1_data_result["result"] == 15, (
            f"Expected D1 result=15, got {d1_data_result['result']}"
        )
        assert d1_data_result["error"] is None

        # Check D2 data stage output (20+5 = 25)
        d2_data_file = out_dir / "data" / "D2" / "evaluate-20+5" / "D2_data.json"
        assert d2_data_file.exists(), f"D2 data output not found: {d2_data_file}"

        with open(d2_data_file) as f:
            d2_data_result = json.load(f)
        assert d2_data_result["result"] == 25, (
            f"Expected D2 result=25, got {d2_data_result['result']}"
        )
        assert d2_data_result["error"] is None

        # For now, only test the data stage (D1 and D2 datasets)


def test_linear_arithmetic_output_structure(
    linear_arithmetic_config, tmp_path, bundled_repos, keep_files
):
    """Test that the linear pipeline creates the expected output directory structure."""

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "linear_arithmetic.yaml"
    shutil.copy2(linear_arithmetic_config, config_file_in_tmp)

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

        # Validate expected directory structure exists
        expected_files = [
            "data/D1/evaluate-1+2+3+4+5/D1_data.json",
            "data/D2/evaluate-20+5/D2_data.json",
        ]

        for expected_file in expected_files:
            file_path = out_dir / expected_file
            assert file_path.exists(), f"Expected output file missing: {file_path}"

            # Validate JSON content
            with open(file_path) as f:
                result = json.load(f)
                assert "result" in result, f"Missing 'result' field in {expected_file}"
                assert "error" in result, f"Missing 'error' field in {expected_file}"
                assert result["error"] is None, (
                    f"Unexpected error in {expected_file}: {result['error']}"
                )

        # Validate specific results
        d1_file = out_dir / "data/D1/evaluate-1+2+3+4+5/D1_data.json"
        with open(d1_file) as f:
            d1_result = json.load(f)
        assert d1_result["result"] == 15, f"D1: Expected 15, got {d1_result['result']}"

        d2_file = out_dir / "data/D2/evaluate-20+5/D2_data.json"
        with open(d2_file) as f:
            d2_result = json.load(f)
        assert d2_result["result"] == 25, f"D2: Expected 25, got {d2_result['result']}"


def test_linear_arithmetic_idempotent(
    linear_arithmetic_config, tmp_path, bundled_repos, keep_files
):
    """Test that running the same workflow twice produces identical results."""

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "linear_arithmetic.yaml"
    shutil.copy2(linear_arithmetic_config, config_file_in_tmp)

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

        # Read D1 results from first run
        d1_file = out_dir / "data" / "D1" / "evaluate-1+2+3+4+5" / "D1_data.json"
        with open(d1_file) as f:
            first_d1_result = json.load(f)

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

        # Read D1 results from second run
        with open(d1_file) as f:
            second_d1_result = json.load(f)

        # Results should be identical
        assert first_d1_result == second_d1_result, "D1 results changed between runs"


def test_linear_arithmetic_cli_validation(
    linear_arithmetic_config, tmp_path, bundled_repos, keep_files
):
    """Test that the CLI handles the benchmark config correctly."""

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "linear_arithmetic.yaml"
    shutil.copy2(linear_arithmetic_config, config_file_in_tmp)

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

        # Verify that at least one output file was created
        output_files = list(out_dir.rglob("*.json"))
        assert len(output_files) >= 2, (
            f"Expected at least 2 JSON output files (D1 and D2), got {len(output_files)}"
        )

        # Verify all output files contain valid JSON
        for output_file in output_files:
            with open(output_file) as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in {output_file}: {e}")
