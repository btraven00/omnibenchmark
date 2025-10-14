import json
import pytest
from pathlib import Path
import shutil
import tempfile

from tests.cli.cli_setup import OmniCLISetup


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

        # Now validate outputs - basic test, no specific assertions yet
        # Just check that the structure exists
        assert out_dir.exists(), "Output directory was not created"

        # Check that output files were created (basic validation)
        output_files = list(out_dir.rglob("*.json"))
        assert len(output_files) > 0, "No JSON output files were created"

        print(f"Created {len(output_files)} output files")
        for output_file in output_files:
            print(f"  - {output_file.relative_to(out_dir)}")
