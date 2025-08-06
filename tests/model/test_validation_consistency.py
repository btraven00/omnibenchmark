"""Tests for validation consistency with the old validator behavior."""

import pytest
from unittest.mock import patch

from pydantic import ValidationError


from .factories import (
    make_benchmark,
    make_software_environment,
    make_iofile,
)


@pytest.mark.short
class TestValidationConsistency:
    """Test that the new model provides consistent validation with the old validator."""

    def test_validate_duplicate_ids(self):
        """Test validation of duplicate IDs across different entity types."""
        # Create a benchmark with duplicate stage IDs
        with pytest.raises(ValidationError):
            make_benchmark(
                stages=[
                    {"id": "duplicate_id", "modules": []},
                    {"id": "duplicate_id", "modules": []},  # Duplicate
                ]
            )

    def test_validate_file_paths(self):
        """Test validation of file paths (relative vs absolute)."""
        # Valid relative paths
        valid_file = make_iofile(path="relative/path/file.txt")
        assert valid_file.path == "relative/path/file.txt"

        # Empty path should fail
        with pytest.raises(ValidationError):
            make_iofile(path="")

        # Whitespace-only path should fail
        with pytest.raises(ValidationError):
            make_iofile(path="   ")

    def test_validate_stage_inputs(self):
        """Test validation of stage inputs referencing outputs."""
        benchmark = make_benchmark(
            software_environments={"env1": {}},
            stages=[
                {
                    "id": "stage1",
                    "modules": [
                        {
                            "id": "mod1",
                            "software_environment": "env1",
                            "outputs": [{"id": "output1", "path": "out1.txt"}],
                        }
                    ],
                },
                {
                    "id": "stage2",
                    "modules": [
                        {
                            "id": "mod2",
                            "software_environment": "env1",
                            "inputs": [{"id": "output1", "path": "out1.txt"}],
                            "outputs": [{"id": "output2", "path": "out2.txt"}],
                        }
                    ],
                },
            ],
        )

        # Should validate without errors
        benchmark.validate_software_environments()

    def test_validate_software_environments_undefined(self):
        """Test validation of undefined software environment references."""
        benchmark = make_benchmark(
            software_environments={"env1": {}},
            stages=[
                {
                    "modules": [
                        {"software_environment": "undefined_env"}  # This doesn't exist
                    ]
                }
            ],
        )

        with pytest.raises(ValueError, match="undefined_env.*not defined"):
            benchmark.validate_software_environments()

    def test_validate_software_backend_configurations(self):
        """Test validation of software backend configurations."""
        # Test conda backend
        conda_benchmark = make_benchmark(
            software_backend="conda",
            software_environments={
                "conda_env": {"conda": "environment.yml"}  # Required for conda
            },
        )

        # Should validate successfully
        conda_benchmark.validate_software_environments()

        # Test conda backend without conda field
        with pytest.raises(ValueError, match="conda configuration"):
            invalid_conda = make_benchmark(
                software_backend="conda",
                software_environments={"no_conda": {}},  # Missing conda field
                stages=[{"modules": [{"software_environment": "no_conda"}]}],
            )
            invalid_conda.validate_software_environments()

    def test_validate_metric_collector_environments(self):
        """Test validation of metric collector software environments."""
        benchmark = make_benchmark(
            software_environments={"env1": {}},
            metric_collectors=[
                {
                    "software_environment": "undefined_env"  # This doesn't exist
                }
            ],
        )

        with pytest.raises(ValueError, match="undefined_env.*not defined"):
            benchmark.validate_software_environments()

    def test_validate_metric_collector_inputs(self):
        """Test validation of metric collector inputs."""
        benchmark = make_benchmark(
            software_environments={"env1": {}},
            stages=[
                {
                    "modules": [
                        {
                            "software_environment": "env1",
                            "outputs": [{"id": "stage_output", "path": "output.txt"}],
                        }
                    ]
                }
            ],
            metric_collectors=[
                {
                    "software_environment": "env1",
                    "inputs": [
                        {"id": "stage_output", "path": "output.txt"}
                    ],  # Valid reference
                }
            ],
        )

        # Should validate successfully
        benchmark.validate_software_environments()

    @patch("omnibenchmark.utils.try_avail_envmodule")
    def test_envmodules_backend_validation(self, mock_try_avail):
        """Test validation with envmodules backend."""
        mock_try_avail.return_value = True

        benchmark = make_benchmark(
            software_backend="envmodules",
            software_environments={"module_env": {"envmodule": "python/3.12"}},
            stages=[{"modules": [{"software_environment": "module_env"}]}],
        )

        # Should validate successfully
        benchmark.validate_software_environments()

    def test_is_url_detection(self):
        """Test URL detection for environment paths."""
        # These should be detected as URLs
        urls = [
            "https://example.com/file.sif",
            "http://registry.com/image:tag",
            "ftp://server.com/path/to/file",
            "docker://python:3.12",
        ]

        for url in urls:
            env = make_software_environment(apptainer=url)
            assert env.apptainer == url

        # These should NOT be detected as URLs
        non_urls = [
            "relative/path/file.sif",
            "/absolute/path/file.sif",
            "./relative/file.sif",
            "../parent/file.sif",
        ]

        for non_url in non_urls:
            env = make_software_environment(conda=non_url)
            assert env.conda == non_url

    def test_path_resolution(self):
        """Test path resolution for different backends and path types."""
        # Test absolute paths
        abs_env = make_software_environment(conda="/absolute/path/env.yaml")
        assert abs_env.conda == "/absolute/path/env.yaml"

        # Test relative paths
        rel_env = make_software_environment(conda="envs/environment.yaml")
        assert rel_env.conda == "envs/environment.yaml"

        # Test URLs
        url_env = make_software_environment(apptainer="https://registry.com/image.sif")
        assert url_env.apptainer == "https://registry.com/image.sif"

    def test_comprehensive_validation_errors(self):
        """Test that validation collects all errors before raising."""
        # Create a benchmark with multiple validation errors
        benchmark = make_benchmark(
            software_backend="conda",
            software_environments={
                "env1": {}  # Missing conda field for conda backend
            },
            stages=[
                {
                    "modules": [
                        {"software_environment": "undefined_env"},  # Undefined
                        {"software_environment": "env1"},  # Missing conda config
                    ]
                }
            ],
            metric_collectors=[
                {"software_environment": "another_undefined"}  # Also undefined
            ],
        )

        # Should raise ValueError with multiple issues
        with pytest.raises(ValueError) as exc_info:
            benchmark.validate_software_environments()

        error_message = str(exc_info.value)
        assert "undefined_env" in error_message
        assert "another_undefined" in error_message
        assert "conda configuration" in error_message

    def test_unused_environment_warning(self):
        """Test that unused environments generate warnings."""
        benchmark = make_benchmark(
            software_environments={"used_env": {}, "unused_env": {}},
            stages=[{"modules": [{"software_environment": "used_env"}]}],
        )

        # Should warn about unused environment
        with pytest.warns(UserWarning, match="unused_env"):
            benchmark.validate_software_environments()

    def test_environment_reference_propagation(self):
        """Test that environment references are checked in all components."""
        benchmark = make_benchmark(
            software_backend="conda",
            software_environments={
                "env1": {"conda": "env1.yaml"},
                "env2": {"conda": "env2.yaml"},
            },
            stages=[
                {
                    "modules": [
                        {"software_environment": "env1"},
                        {"software_environment": "env2"},
                    ]
                }
            ],
            metric_collectors=[{"software_environment": "env1"}],
        )

        # All references are valid
        benchmark.validate_software_environments()

        # Now make one reference invalid
        benchmark.metric_collectors[0].software_environment = "env3"

        with pytest.raises(ValueError, match="env3.*not defined"):
            benchmark.validate_software_environments()

    def test_backend_specific_validation(self):
        """Test backend-specific validation rules."""
        backends_and_fields = [
            ("conda", "conda", "environment.yml"),
            ("docker", "apptainer", "image.sif"),
            ("apptainer", "apptainer", "image.sif"),
            ("envmodules", "envmodule", "module/1.0"),
        ]

        for backend, field, value in backends_and_fields:
            # Valid configuration
            valid = make_benchmark(
                software_backend=backend,
                software_environments={"env1": {field: value}},
                stages=[{"modules": [{"software_environment": "env1"}]}],
            )
            valid.validate_software_environments()

            # Invalid configuration (missing required field)
            with pytest.raises(ValueError, match=f"{field} configuration"):
                invalid = make_benchmark(
                    software_backend=backend,
                    software_environments={"env1": {}},  # Missing required field
                    stages=[{"modules": [{"software_environment": "env1"}]}],
                )
                invalid.validate_software_environments()

    def test_host_backend_no_requirements(self):
        """Test that host backend doesn't require specific configuration."""
        benchmark = make_benchmark(
            software_backend="host",
            software_environments={
                "env1": {}  # No specific fields required
            },
            stages=[{"modules": [{"software_environment": "env1"}]}],
        )

        # Should validate successfully
        benchmark.validate_software_environments()
