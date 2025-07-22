"""Integration tests for the artifact validation system."""

import json
import tempfile
from pathlib import Path

import pytest

from omnibenchmark.artifact_validation import ValidationEngine, ValidationStatus


def test_end_to_end_validation():
    """Test complete validation workflow without pandas dependency."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a simple benchmark structure
        # Dataset stage
        dataset_dir = tmpdir / "dataset" / "test_data"
        dataset_dir.mkdir(parents=True)

        # Create a JSON dataset file
        dataset_file = dataset_dir / "data.json"
        dataset_file.write_text(
            json.dumps(
                {
                    "samples": [
                        {"id": 1, "value": 10},
                        {"id": 2, "value": 20},
                        {"id": 3, "value": 30},
                    ],
                    "metadata": {"created": "2025-01-27", "version": "1.0"},
                }
            )
        )

        # Method stage
        method_dir = tmpdir / "method" / "simple_method"
        method_dir.mkdir(parents=True)

        # Create method output
        method_output = method_dir / "results.json"
        method_output.write_text(
            json.dumps({"clusters": [0, 0, 1], "parameters": {"k": 2}})
        )

        # Create empty file for failure case
        method_dir2 = tmpdir / "method" / "failed_method"
        method_dir2.mkdir(parents=True)
        (method_dir2 / "results.json").touch()  # Empty file

        # Create validation config
        config_file = tmpdir / "validation.yaml"
        config_file.write_text("""
version: 1.0
stages:
  dataset:
    rules:
      - file_pattern: "data.json"
        validations:
          - type: not_empty

  method:
    rules:
      - file_pattern: "results.json"
        validations:
          - type: not_empty
""")

        # Run validation
        engine = ValidationEngine(config_file)
        report = engine.validate_all(tmpdir, benchmark_name="test_benchmark")

        # Check results
        assert report.benchmark == "test_benchmark"
        assert report.total_modules == 3  # test_data, simple_method, failed_method
        assert report.passed_modules == 2
        assert report.failed_modules == 1

        # Check individual results
        results_by_module = {r.module: r for r in report.results}

        assert results_by_module["test_data"].status == ValidationStatus.PASSED
        assert results_by_module["simple_method"].status == ValidationStatus.PASSED
        assert results_by_module["failed_method"].status == ValidationStatus.FAILED

        # Test JSON output
        json_output = engine.format_results(report, format="json")
        parsed = json.loads(json_output)
        assert parsed["benchmark"] == "test_benchmark"
        assert isinstance(parsed["validation_timestamp"], str)

        # Test human-readable output
        human_output = engine.format_results(report, format="human")
        assert "test_benchmark" in human_output
        assert "✓" in human_output  # Check for passed symbol
        assert "✗" in human_output  # Check for failed symbol
        assert "failed_method" in human_output


def test_discover_config():
    """Test automatic config discovery."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create config file
        config_file = tmpdir / "validation.yaml"
        config_file.write_text("""
version: 1.0
stages:
  test:
    rules:
      - file_pattern: "*.json"
        validations:
          - type: not_empty
""")

        # Create test data
        test_dir = tmpdir / "test" / "module1"
        test_dir.mkdir(parents=True)
        (test_dir / "output.json").write_text('{"result": "ok"}')

        # Test discovery
        engine = ValidationEngine()
        engine.discover_config(tmpdir)

        # Should work after discovery
        report = engine.validate_all(tmpdir)
        assert report.total_modules == 1
        assert report.passed_modules == 1


def test_missing_file_validation():
    """Test validation when expected files are missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create module directory but no files
        module_dir = tmpdir / "dataset" / "incomplete_module"
        module_dir.mkdir(parents=True)

        # Create validation config expecting a file
        config_file = tmpdir / "validation.yaml"
        config_file.write_text("""
version: 1.0
stages:
  dataset:
    rules:
      - file_pattern: "required_data.json"
        validations:
          - type: not_empty
""")

        # Run validation
        engine = ValidationEngine(config_file)
        report = engine.validate_all(tmpdir)

        # Should fail due to missing file
        assert report.total_modules == 1
        assert report.failed_modules == 1

        # Check the specific failure
        result = report.results[0]
        assert result.module == "incomplete_module"
        assert result.status == ValidationStatus.FAILED
        assert any("No files matching pattern" in v.message for v in result.validations)


def test_multiple_file_patterns():
    """Test validation with multiple file patterns in a stage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create module with multiple output files
        module_dir = tmpdir / "analysis" / "multi_output"
        module_dir.mkdir(parents=True)

        (module_dir / "summary.json").write_text('{"count": 100}')
        (module_dir / "details.json").write_text('{"items": [1, 2, 3]}')

        # Create validation config with multiple patterns
        config_file = tmpdir / "validation.yaml"
        config_file.write_text("""
version: 1.0
stages:
  analysis:
    rules:
      - file_pattern: "summary.json"
        validations:
          - type: not_empty
      - file_pattern: "details.json"
        validations:
          - type: not_empty
""")

        # Run validation
        engine = ValidationEngine(config_file)
        results = engine.validate_stage("analysis", tmpdir)

        # Should have validated both files
        assert len(results) == 2  # Two file patterns = two results
        assert all(r.status == ValidationStatus.PASSED for r in results)


def test_invalid_config():
    """Test handling of invalid configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create invalid config (missing required fields)
        config_file = tmpdir / "validation.yaml"
        config_file.write_text("""
version: 1.0
stages:
  test:
    rules:
      - file_pattern: "*.json"
        validations:
          - columns: ["a", "b"]  # Missing 'type' field
""")

        # Should raise error on load
        with pytest.raises(ValueError, match="missing 'type'"):
            ValidationEngine(config_file)


def test_unknown_validator():
    """Test handling of unknown validator type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test file
        test_dir = tmpdir / "test" / "module"
        test_dir.mkdir(parents=True)
        (test_dir / "data.json").write_text('{"value": 1}')

        # Create config with unknown validator
        config_file = tmpdir / "validation.yaml"
        config_file.write_text("""
version: 1.0
stages:
  test:
    rules:
      - file_pattern: "data.json"
        validations:
          - type: unknown_validator
""")

        # Run validation
        engine = ValidationEngine(config_file)
        report = engine.validate_all(tmpdir)

        # Should have error status
        assert report.total_modules == 1
        assert report.failed_modules == 1

        result = report.results[0]
        assert any(
            v.status == ValidationStatus.ERROR and "Unknown validator" in v.message
            for v in result.validations
        )
