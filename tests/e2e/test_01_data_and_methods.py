import pytest
from pathlib import Path
import shutil
import tempfile

from tests.cli.cli_setup import OmniCLISetup
from tests.e2e.result_validation import validate_pipeline_results, load_expected_results, get_test_name_from_function


@pytest.fixture
def data_and_methods_config():
    """Get the path to the data and methods config."""
    config_path = (
        Path(__file__).parent / "configs" / "01_data_and_methods.yaml"
    )
    return config_path


def test_data_and_methods_pipeline(
    data_and_methods_config, tmp_path, bundled_repos, keep_files
):
    """Test a data and methods pipeline using the omnibenchmark CLI."""

    if keep_files:
        print(f"\n=== TEMP PATH FOR INSPECTION ===")
        print(f"Files will be kept at: {tmp_path}")
        print(f"=== END TEMP PATH INFO ===\n")

    # Copy config to tmp_path
    config_file_in_tmp = tmp_path / "01_data_and_methods.yaml"
    shutil.copy2(data_and_methods_config, config_file_in_tmp)

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

            # Show JSON files specifically
            json_files = list(out_dir.rglob("*.json"))
            print(f"Found {len(json_files)} JSON files:")
            for json_file in sorted(json_files):
                print(f"  - {json_file.relative_to(out_dir)}")
            print()

        # Load expected results from JSON file and validate
        expected_results = load_expected_results("01_data_and_methods")
        validate_pipeline_results(out_dir, expected_results, verbose=keep_files)

        # Additional verification: ensure we have the expected number of output files
        output_files = list(out_dir.rglob("*.json"))
        if keep_files:
            print(f"\nCreated {len(output_files)} total JSON output files:")
            for output_file in output_files:
                print(f"  - {output_file.relative_to(out_dir)}")

        # We expect at least 4 files (2 datasets + 2 method results)
        assert len(output_files) >= 4, (
            f"Expected at least 4 JSON files, but found {len(output_files)}"
        )
