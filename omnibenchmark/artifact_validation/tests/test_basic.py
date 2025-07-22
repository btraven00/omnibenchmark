"""Basic tests for the validation engine."""

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

from omnibenchmark.artifact_validation import ValidationEngine, ValidationStatus
from omnibenchmark.artifact_validation.config import parse_validation_config


def _pandas_available():
    """Check if pandas is available."""
    return importlib.util.find_spec("pandas") is not None


class TestValidationEngine:
    """Test the validation engine functionality."""

    def test_config_parsing(self):
        """Test parsing validation configuration."""
        config_data = {
            "version": "1.0",
            "stages": {
                "dataset": {
                    "rules": [
                        {
                            "file_pattern": "*.csv",
                            "validations": [
                                {"type": "not_empty"},
                                {"type": "has_columns", "columns": ["id", "value"]},
                            ],
                        }
                    ]
                }
            },
        }

        config = parse_validation_config(config_data)
        assert config.version == "1.0"
        assert "dataset" in config.stages
        assert len(config.stages["dataset"].rules) == 1
        assert config.stages["dataset"].rules[0].file_pattern == "*.csv"
        assert len(config.stages["dataset"].rules[0].validations) == 2

    def test_not_empty_validator(self):
        """Test the not_empty validator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test files
            empty_file = tmpdir / "empty.csv"
            empty_file.touch()

            valid_file = tmpdir / "valid.csv"
            valid_file.write_text("id,value\n1,100\n")

            # Create validation config
            config = tmpdir / "validation.yaml"
            config.write_text("""
version: 1.0
stages:
  test:
    rules:
      - file_pattern: "*.csv"
        validations:
          - type: not_empty
""")

            # Run validation
            engine = ValidationEngine(config)

            # Test empty file
            results = engine.validate_file(
                empty_file, [{"type": "not_empty"}], "test", "test_module"
            )
            assert results.status == ValidationStatus.FAILED

            # Test valid file
            results = engine.validate_file(
                valid_file, [{"type": "not_empty"}], "test", "test_module"
            )
            assert results.status == ValidationStatus.PASSED

    def test_json_validation(self):
        """Test JSON file validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test JSON
            test_file = tmpdir / "data.json"
            data = {"results": [{"id": 1, "score": 0.9}]}
            test_file.write_text(json.dumps(data))

            engine = ValidationEngine()

            # Test not empty
            results = engine.validate_file(
                test_file, [{"type": "not_empty"}], "test", "test_module"
            )
            assert results.status == ValidationStatus.PASSED

    def test_stage_validation(self):
        """Test validating an entire stage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create directory structure
            stage_dir = tmpdir / "method" / "test_module"
            stage_dir.mkdir(parents=True)

            # Create test file
            (stage_dir / "output.json").write_text('{"result": "ok"}')

            # Create validation config
            config = tmpdir / "validation.yaml"
            config.write_text("""
version: 1.0
stages:
  method:
    rules:
      - file_pattern: "output.json"
        validations:
          - type: not_empty
""")

            # Run validation
            engine = ValidationEngine(config)
            results = engine.validate_stage("method", tmpdir)

            assert len(results) == 1
            assert results[0].module == "test_module"
            assert results[0].status == ValidationStatus.PASSED

    def test_validation_report(self):
        """Test generating a complete validation report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create modules
            for module in ["module1", "module2"]:
                module_dir = tmpdir / "dataset" / module
                module_dir.mkdir(parents=True)
                (module_dir / "data.json").write_text('{"data": [1,2,3]}')

            # Create validation config
            config = tmpdir / "validation.yaml"
            config.write_text("""
version: 1.0
stages:
  dataset:
    rules:
      - file_pattern: "data.json"
        validations:
          - type: not_empty
""")

            # Generate report
            engine = ValidationEngine(config)
            report = engine.validate_all(tmpdir, benchmark_name="test_benchmark")

            assert report.benchmark == "test_benchmark"
            assert report.total_modules == 2
            assert report.passed_modules == 2
            assert report.failed_modules == 0

            # Test formatting
            human_output = engine.format_results(report, format="human")
            assert "test_benchmark" in human_output
            assert "Total modules: 2" in human_output

            json_output = engine.format_results(report, format="json")
            parsed = json.loads(json_output)
            assert parsed["benchmark"] == "test_benchmark"


@pytest.mark.skipif(not _pandas_available(), reason="pandas not installed")
class TestPandasValidators:
    """Test validators that require pandas."""

    def test_has_columns_validator(self):
        """Test the has_columns validator with CSV files."""
        import pandas as pd

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test CSV
            test_file = tmpdir / "data.csv"
            df = pd.DataFrame(
                {"id": [1, 2, 3], "name": ["A", "B", "C"], "value": [10, 20, 30]}
            )
            df.to_csv(test_file, index=False)

            engine = ValidationEngine()

            # Test with all columns present
            results = engine.validate_file(
                test_file,
                [{"type": "has_columns", "columns": ["id", "name"]}],
                "test",
                "test_module",
            )
            assert results.status == ValidationStatus.PASSED

            # Test with missing columns
            results = engine.validate_file(
                test_file,
                [{"type": "has_columns", "columns": ["id", "missing_column"]}],
                "test",
                "test_module",
            )
            assert results.status == ValidationStatus.FAILED

    def test_has_shape_validator(self):
        """Test the has_shape validator with CSV files."""
        import pandas as pd

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test CSV
            test_file = tmpdir / "data.csv"
            df = pd.DataFrame({"a": range(5), "b": range(5), "c": range(5)})
            df.to_csv(test_file, index=False)

            engine = ValidationEngine()

            # Test with valid shape
            results = engine.validate_file(
                test_file,
                [{"type": "has_shape", "min_rows": 3, "min_cols": 2}],
                "test",
                "test_module",
            )
            assert results.status == ValidationStatus.PASSED

            # Test with invalid shape
            results = engine.validate_file(
                test_file,
                [{"type": "has_shape", "min_rows": 10}],
                "test",
                "test_module",
            )
            assert results.status == ValidationStatus.FAILED
