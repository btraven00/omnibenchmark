# Versioning Module

The `omnibenchmark.versioning` module provides robust version management for benchmarks with file-based locking for concurrency control and optional git integration for tracking versions through file history.

## Overview

This module was created to provide clean separation of concerns in the omnibenchmark architecture:
- **Version Management**: Handles version tracking, comparison, and auto-increment
- **Concurrency Control**: File-based locking prevents race conditions
- **Git Integration**: Optional tracking of git commit information
- **No Model Dependencies**: The versioning module does not depend on the model layer

## Key Components

### Version Class
```python
from omnibenchmark.versioning import Version

v = Version("1.2.3")
v.major  # 1
v.minor  # 2
v.patch  # 3

# Supports comparison
v1 = Version("1.0.0")
v2 = Version("2.0.0")
assert v1 < v2

# Increment operations
v3 = v1.increment_minor()  # "1.1"
```

### BenchmarkVersionManager
Provides version management with file-based locking:

```python
from omnibenchmark.versioning import BenchmarkVersionManager

manager = BenchmarkVersionManager(
    benchmark_name="my_benchmark",
    lock_dir="/path/to/locks",  # Optional, defaults to temp dir
    lock_timeout=30.0  # Seconds to wait for lock
)

# Create versions
manager.create_version("1.0.0")
manager.create_version()  # Auto-increment to "1.1"

# Get version history
versions = manager.get_versions()  # ["1.0.0", "1.1"]

# Add metadata
manager.create_version("2.0.0", metadata={"author": "user", "changes": ["feature X"]})

# Concurrency-safe operations
with manager.acquire_lock():
    # Exclusive access to version history
    manager.create_version("3.0.0")
```

### GitAwareBenchmarkVersionManager
Extends BenchmarkVersionManager with git commit tracking:

```python
from omnibenchmark.versioning import GitAwareBenchmarkVersionManager

manager = GitAwareBenchmarkVersionManager(
    benchmark_name="my_benchmark",
    git_repo_path="/path/to/repo"  # Optional, defaults to current dir
)

# Create version with git tracking
manager.create_version_with_git_tracking("1.0.0")

# Git info is automatically stored in metadata
metadata = manager.get_version_metadata("1.0.0")
print(metadata["git"]["commit"])  # Short commit hash
print(metadata["git"]["branch"])  # Current branch
print(metadata["git"]["author"])  # Commit author
print(metadata["git"]["clean"])   # True if working dir is clean
```

## Architecture

### Separation of Concerns

1. **Version Operations** (`version.py`):
   - Version parsing and validation
   - Version comparison logic
   - Version increment operations
   - No external dependencies

2. **Version Management** (`manager.py`):
   - Version history tracking
   - File-based locking for concurrency
   - Metadata storage
   - Hook system for integration

3. **Git Integration** (`git_manager.py`):
   - Git repository detection
   - Commit information tracking
   - Optional enhancement, not required

### Integration with IO Layer

The versioning module is designed to integrate with the IO layer without circular dependencies:

```python
# In MinIOStorage or similar
from omnibenchmark.versioning import BenchmarkVersionManager

class MinIOStorage:
    def __init__(self, benchmark_name, ...):
        self.version_manager = BenchmarkVersionManager(benchmark_name)

    def create_new_version(self, version=None):
        # Use hooks for storage operations
        def pre_create_hook(version):
            # Validate storage state
            pass

        def post_create_hook(version):
            # Tag objects in storage
            self._tag_objects_with_version(version)

        # Delegate version management
        created_version = self.version_manager.create_version(
            version=version,
            pre_create_hook=pre_create_hook,
            post_create_hook=post_create_hook
        )
        return created_version
```

## Features

### Concurrency Control
- File-based locking using `fcntl`
- Configurable lock timeout
- Shared (read) and exclusive (write) locks
- Automatic lock cleanup

### Version Validation
- Semantic versioning format (x.y.z or x.y)
- Automatic format validation
- Prevents version downgrades
- Handles YAML numeric values (e.g., 1.0 from float)

### Atomic Operations
- Version history stored in JSON
- Atomic file writes using temp files
- In-memory caching for performance
- Thread-safe operations

### Auto-increment
- Automatic version increment when not specified
- Configurable increment component (major/minor/patch)
- Based on last version in history

## Error Handling

The module provides specific exceptions for different error cases:

- `VersioningError`: Base exception for all versioning errors
- `VersionFormatError`: Invalid version string format
- `VersionDowngradeError`: Attempt to create older version
- `VersionAlreadyExistsError`: Version already exists
- `VersionLockError`: Unable to acquire lock
- `VersionNotFoundError`: Requested version not found

## Testing

The module includes comprehensive tests (67 tests total):

```bash
# Run all versioning tests
pytest tests/versioning/ -v -m short
```

## Design Decisions

1. **No YAML Serialization**: The versioning module does not handle YAML loading/saving. This remains the responsibility of the model layer.

3. **Version Source**: Versions come from the benchmark YAML field, not from git tags.

4. **Lock Files**: Lock files are transient, should not be persisted.

5. **Hook System**: Pre/post-create hooks allow integration with storage systems without tight coupling.
