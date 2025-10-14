import json
import pytest
from pathlib import Path
import shutil
import tempfile

from tests.cli.cli_setup import OmniCLISetup


def validate_pipeline_results(output_dir: Path, expected_results: dict[str, int]):
    """
    Validate that JSON files in the output directory contain expected results.

    Args:
        output_dir: Path to the output directory to search
        expected_results: Dict mapping glob patterns to expected 'result' values
                         e.g., {"D1/D1_data.json": 15, "D2/methods/M1/**/D2_data.json": 125}

    Raises:
        AssertionError: If any expected result doesn't match or files are missing
    """
    print(f"\n=== VALIDATING PIPELINE RESULTS ===")

    for glob_pattern, expected_value in expected_results.items():
        print(f"Looking for pattern: {glob_pattern} (expecting result={expected_value})")

        # Find files matching the glob pattern
        matching_files = list(output_dir.glob(glob_pattern))

        assert len(matching_files) > 0, (
            f"No files found matching pattern '{glob_pattern}' in {output_dir}"
        )

        print(f"  Found {len(matching_files)} matching file(s):")

        # Validate each matching file
        for file_path in matching_files:
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
                print(f"      ✓ error=None (no errors)")

            # Check that 'result' field exists and matches expected value
            assert 'result' in data, (
                f"Missing 'result' field in {file_path}. Available fields: {list(data.keys())}"
            )

            actual_result = data['result']
            assert actual_result == expected_value, (
                f"Expected {expected_value}, got {actual_result}"
            )

            print(f"      ✓ result={actual_result} (matches expected)")

    print(f"=== ALL RESULTS VALIDATED SUCCESSFULLY ===\n")


@pytest.fixture
def linear_arithmetic_with_methods_config():
    """Get the path to the static linear arithmetic config with methods."""
    config_path = (
        Path(__file__).parent / "configs" / "linear_arithmetic_with_methods.yaml"
    )
    return config_path


def test_linear_arithmetic_with_methods_pipeline(
    linear_arithmetic_with_methods_config, tmp_path, bundled_repos, keep_files
):
    """Test a linear arithmetic pipeline with methods stage using the omnibenchmark CLI."""

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "linear_arithmetic_with_methods.yaml"
    shutil.copy2(linear_arithmetic_with_methods_config, config_file_in_tmp)

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
                "--continue-on-error", "-y"
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

        # Check that the output directory was created
        assert out_dir.exists(), "Output directory was not created"

        # Debug: Show actual directory structure before validation
        print(f"\n=== ACTUAL DIRECTORY STRUCTURE ===")
        print(f"Output directory: {out_dir}")
        all_files = list(out_dir.rglob("*"))
        for file_path in sorted(all_files):
            if file_path.is_file():
                print(f"FILE: {file_path.relative_to(out_dir)}")
            else:
                print(f"DIR:  {file_path.relative_to(out_dir)}/")
        print(f"=== END DIRECTORY STRUCTURE ===\n")

        # Show JSON files specifically
        json_files = list(out_dir.rglob("*.json"))
        print(f"Found {len(json_files)} JSON files:")
        for json_file in sorted(json_files):
            print(f"  - {json_file.relative_to(out_dir)}")
        print()

        # Validate the arithmetic results with comprehensive checks
        # This checks: file existence, error=None, and result values
        expected_results = {
            "data/D1/*/D1_data.json": 15,                   # 1+2+3+4+5 = 15
            "data/D2/*/D2_data.json": 25,                   # 20+5 = 25
            "data/D1/*/methods/M1/*/D1_data.json": 115,     # 15+100 = 115
            "data/D2/*/methods/M1/*/D2_data.json": 125,     # 25+100 = 125
        }

        validate_pipeline_results(out_dir, expected_results)

        # Additional verification: ensure we have the expected number of output files
        output_files = list(out_dir.rglob("*.json"))
        print(f"\nCreated {len(output_files)} total JSON output files:")
        for output_file in output_files:
            print(f"  - {output_file.relative_to(out_dir)}")

        # We expect at least 4 files (2 datasets + 2 method results)
        assert len(output_files) >= 4, (
            f"Expected at least 4 JSON files, but found {len(output_files)}"
        )
