# Migration Guide: From omni_schema/LinkML to Pydantic Models

This guide helps you migrate from the old `omni_schema` and LinkML-based models to the new Pydantic-based models in `omnibenchmark.model`.

## Overview

The new model system removes dependencies on `omni_schema` and `linkml` packages, replacing them with pure Pydantic models that provide the same functionality with better type safety and no external schema dependencies.

## Import Changes

### Old Imports
```python
from omni_schema.datamodel import omni_schema
from omni_schema.datamodel.omni_schema import (
    SoftwareBackendEnum,
    SoftwareEnvironment,
    IOFile,
    # ... other models
)
from omnibenchmark.benchmark.converter import LinkMLConverter
from omnibenchmark.utils import parse_instance
```

### New Imports
```python
from omnibenchmark.model import (
    SoftwareBackendEnum,
    SoftwareEnvironment,
    IOFile,
    BenchmarkConverter,  # or LinkMLConverter for compatibility
    Benchmark,
    Stage,
    Module,
    # ... other models
)
```

## Key Changes

### 1. LinkMLConverter → BenchmarkConverter

The `LinkMLConverter` class has been replaced with `BenchmarkConverter`. For backwards compatibility, `LinkMLConverter` is aliased to `BenchmarkConverter`.

```python
# Old
from omnibenchmark.benchmark.converter import LinkMLConverter
converter = LinkMLConverter(benchmark_yaml_path)

# New (preferred)
from omnibenchmark.model import BenchmarkConverter
converter = BenchmarkConverter(benchmark_yaml_path)

# New (backwards compatible)
from omnibenchmark.model import LinkMLConverter
converter = LinkMLConverter(benchmark_yaml_path)
```

### 2. Loading Benchmark Files

The `parse_instance` function is no longer needed. Use the Pydantic model's built-in methods:

```python
# Old
from omnibenchmark.utils import parse_instance
benchmark = parse_instance(path, omni_schema.Benchmark)

# New
from omnibenchmark.model import Benchmark
benchmark = Benchmark.from_yaml(path)
```

### 3. Model References

All `omni_schema.*` model references should be replaced with imports from `omnibenchmark.model`:

```python
# Old
stage: omni_schema.Stage
module: omni_schema.Module
env: omni_schema.SoftwareEnvironment

# New
from omnibenchmark.model import Stage, Module, SoftwareEnvironment
stage: Stage
module: Module
env: SoftwareEnvironment
```

### 4. Enum Access

Some enum properties have changed:

```python
# Old
software_backend.text  # For string representation

# New
software_backend.value  # For string representation
```

### 5. Type Annotations

Update type annotations throughout your code:

```python
# Old
def process_stage(stage: omni_schema.Stage) -> Dict[str, omni_schema.Module]:
    ...

# New
from omnibenchmark.model import Stage, Module
def process_stage(stage: Stage) -> Dict[str, Module]:
    ...
```

## Common Migration Patterns

### Pattern 1: Validator Usage
```python
# Old
from omnibenchmark.benchmark.converter import LinkMLConverter
from omnibenchmark.benchmark.validation.validator import Validator

converter = LinkMLConverter(benchmark_file)
validator = Validator()
converter = validator.validate(benchmark_dir, converter)

# New
from omnibenchmark.model import BenchmarkConverter
from omnibenchmark.benchmark.validation.validator import Validator

converter = BenchmarkConverter(benchmark_file)
validator = Validator()
converter = validator.validate(benchmark_dir, converter)
```

### Pattern 2: Accessing Model Properties
```python
# Old
from omni_schema.datamodel.omni_schema import SoftwareBackendEnum
if backend == SoftwareBackendEnum.conda:
    env_file = software_env["conda"]

# New
from omnibenchmark.model import SoftwareBackendEnum
if backend == SoftwareBackendEnum.conda:
    env_file = software_env.conda
```

### Pattern 3: Creating New Models
```python
# Old
import omni_schema
stage = omni_schema.Stage(
    id="stage1",
    modules=[...],
    outputs=[...]
)

# New
from omnibenchmark.model import Stage
stage = Stage(
    id="stage1",
    modules=[...],
    outputs=[...]
)
```

## Benefits of Migration

1. **No External Dependencies**: Removes dependency on `omni_schema` and `linkml` packages
2. **Better Type Safety**: Pydantic provides excellent type checking and validation
3. **Improved Performance**: Direct model instantiation without schema parsing overhead
4. **Easier Testing**: Models can be easily created and validated in tests
5. **Better IDE Support**: Full autocomplete and type hints in modern IDEs

## Gradual Migration

You can migrate gradually by using the compatibility aliases:

1. Start by replacing imports but keep using `LinkMLConverter` name
2. Update model type annotations
3. Replace `parse_instance` calls with `Benchmark.from_yaml()`
4. Finally, rename `LinkMLConverter` to `BenchmarkConverter`

## Need Help?

If you encounter any issues during migration:

1. Check that all imports are updated
2. Verify enum property access (`.value` instead of `.text`)
3. Ensure type annotations are updated
4. Look for any remaining `omni_schema` or `linkml` imports in your codebase