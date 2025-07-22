# Omnibenchmark Artifact Validation

A lightweight validation engine for validating module outputs in omnibenchmark workflows.

> **Note**: This module is named `artifact_validation` to distinguish it from the existing `omnibenchmark.benchmark.validation` module, which validates benchmark configuration files. This module specifically validates the output artifacts produced by benchmark modules during execution.

## Installation

The validation engine requires pandas and numpy, which are optional dependencies:

```bash
pip install omnibenchmark[validation]
```

## Quick Start

### 1. Create a validation.yaml file

```yaml
version: 1.0
stages:
  dataset:
    rules:
      - file_pattern: "*.csv"
        validations:
          - type: not_empty
          - type: has_columns
            columns: ["sample_id", "value"]
          - type: has_shape
            min_rows: 10
```

### 2. Run validation

```python
from omnibenchmark.artifact_validation import ValidationEngine

# Initialize engine with config
engine = ValidationEngine("validation.yaml")

# Validate all stages
report = engine.validate_all("results_directory")

# Print results
print(engine.format_results(report))
```

## Built-in Validators

- **not_empty**: Ensures files are not empty
- **has_columns**: Validates required columns in tabular data
- **has_shape**: Validates data dimensions (min/max rows/columns)
- **not_na**: Ensures columns don't contain all NA values

## Validation Configuration

The `validation.yaml` file defines rules for each stage:

```yaml
version: 1.0
stages:
  <stage_name>:
    rules:
      - file_pattern: "<glob_pattern>"
        validations:
          - type: <validator_name>
            <param1>: <value1>
            <param2>: <value2>
```

### File Patterns

- Use glob patterns: `*.csv`, `results_*.json`
- Placeholders: `{module}`, `{stage}`

### Example Configuration

```yaml
version: 1.0
stages:
  method:
    rules:
      - file_pattern: "clusters.csv"
        validations:
          - type: not_empty
          - type: has_columns
            columns: ["sample_id", "cluster_id"]
          - type: not_na
            columns: ["cluster_id"]
          - type: has_shape
            min_rows: 1
            
  metric:
    rules:
      - file_pattern: "scores.json"
        validations:
          - type: not_empty
```

## Output Formats

### Human-readable

```
Validation Report - 2025-01-27T10:30:00Z
Benchmark: my_benchmark

Total modules: 3
Passed: 2
Failed: 1

Stage: method
--------------------------------------------------
  ✓ Module: kmeans - passed
  ✗ Module: hierarchical - failed
    - not_empty: File is empty
```

### JSON

```json
{
  "validation_timestamp": "2025-01-27T10:30:00Z",
  "benchmark": "my_benchmark",
  "total_modules": 3,
  "passed_modules": 2,
  "failed_modules": 1,
  "results": [...]
}
```

## Custom Validators

Create custom validators by subclassing `Validator`:

```python
from omnibenchmark.artifact_validation.base import Validator, ValidationResult, ValidationStatus

class MyValidator(Validator):
    @property
    def name(self) -> str:
        return "my_validator"
    
    def validate(self, data, params):
        # Validation logic
        if some_condition:
            return ValidationResult(
                rule=self.name,
                status=ValidationStatus.PASSED
            )
        else:
            return ValidationResult(
                rule=self.name,
                status=ValidationStatus.FAILED,
                message="Validation failed"
            )

# Register the validator
engine.validator_registry.register(MyValidator())
```

## API Reference

### ValidationEngine

```python
# Initialize with config
engine = ValidationEngine("validation.yaml")

# Or discover config
engine = ValidationEngine()
engine.discover_config("project_dir")

# Validate everything
report = engine.validate_all("results_dir")

# Validate specific stage
results = engine.validate_stage("method", "results_dir")

# Format results
print(engine.format_results(report))  # Human-readable
json_str = engine.format_results(report, format="json")
```

### Validation Results

- `ValidationStatus.PASSED`: All checks passed
- `ValidationStatus.FAILED`: One or more checks failed
- `ValidationStatus.ERROR`: Error during validation
- `ValidationStatus.SKIPPED`: Validation was skipped

## Examples

See `examples/example_usage.py` for a complete working example.