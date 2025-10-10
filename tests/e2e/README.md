# End-to-End Omnibenchmark Tests

## Overview

This document outlines the roadmap for implementing comprehensive end-to-end (e2e) tests for omnibenchmark, focusing on validating real benchmark workflows with different module topologies and integration patterns.

## Test Architecture

### Primary Goals

1. **Validate Core Workflows**: Ensure benchmark YAML configurations execute without changes across different branches and environments
2. **Test Module Topologies**: Verify different scatter and aggregation patterns work correctly
3. **Integration Testing**: Confirm CLI → Workflow → Execution pipeline integrity
4. **Deterministic Results**: Use predictable dummy modules for reliable test assertions

## Test Scenarios

### Scenario 1: Basic Linear Pipeline
**File**: `test_linear_workflow.py`
```yaml
data → process → method → metric
```
- Single module per stage
- Validates basic data flow
- Uses a simplified version of existing `Benchmark_001.yaml`

### Scenario 2: Basic Scatter Pattern
**File**: `test_basic_scatter.py`
```yaml
data (D1, D2) → process → method → metric
```
- 2 datasets scatter to single downstream modules
- Tests parameter expansion and file routing
- Based on existing benchmark patterns
- Checks that the correct number of files are generated
- Validation modules will extend the checks on this scenario when implemented

### Scenario 3: Single Metric Collector

TODO

### Scenario 4: Multi-Stage Scatter with Dual Collectors
**File**: `test_multi_metric_collectors.py`
```yaml
data (D1, D2) → process (P1, P2) → method (M1, M2) → metrics (m1, m2) → collectors (C1, C2) → aggregator
```

**Topology Details**:

- **Data Stage**: 2 datasets (D1, D2)
- **Process Stage**: 2 processors (P1, P2) - creates 4 combinations (D1×P1, D1×P2, D2×P1, D2×P2)
- **Method Stage**: 2 methods (M1, M2) - creates 8 combinations
- **Metrics Stage**: 2 metrics modules (m1, m2) - creates 16 result files
- **Collector Stage**: 2 collectors (C1, C2) that aggregate subsets of metrics
- **Final Aggregator**: Combines outputs from both collectors

**Key Testing Points**:
- Combinatorial explosion handled correctly
- File routing through complex DAG
- Metric collectors receive correct input subsets
- Final aggregation produces expected results

## Dummy Module Design

### Design Principles
- **Deterministic**: Same inputs always produce same outputs
- **Language Agnostic**: Support both Python and R execution
- **Arithmetic Operations**: Use simple math for predictable test assertions
- **JSON Output**: Standardized format for easy validation

### Core Dummy Modules

#### 1. Sum Module (Python & R)
**Purpose**: Aggregates numeric data for predictable testing
```python
# Input: data.json = {"values": [1, 2, 3, 4, 5]}
# Output: result.json = {"sum": 15, "count": 5, "mean": 3.0}
```

**Implementations**:
- `dummy_modules/sum_python/`: Pure Python stdlib implementation
- `dummy_modules/sum_r/`: R implementation using base R only

#### 2. Filter Module (Python)
**Purpose**: Data processing with configurable parameters
```python
# Parameters: --threshold 10 --operation gt
# Input: data.json = {"values": [5, 10, 15, 20]}
# Output: filtered.json = {"values": [15, 20], "filtered_count": 2}
```

#### 3. Transform Module (R)
**Purpose**: Method-style transformations
```r
# Input: data.json, parameters from config
# Output: transformed.json with modified values
```

#### 4. Metric Calculator (Python)
**Purpose**: Compute evaluation metrics
```python
# Input: ground_truth.json, predictions.json
# Output: metrics.json = {"mse": 2.5, "mae": 1.2, "r2": 0.85}
```

#### 5. Collector Modules (Python)
**Purpose**: Aggregate results from multiple metrics modules
```python
# C1: Aggregates accuracy-based metrics
# C2: Aggregates error-based metrics
# Input: Multiple metrics.json files
# Output: aggregated.json with combined statistics
```

### Container Strategy
- **Python Modules**: Use `python:3.12-slim` base image
- **R Modules**: Use `rocker/r-ver:4.3` base image
- **Unified Interface**: All modules accept same CLI patterns
- **Test Data**: Embedded JSON files with known expected results

## Test Data Management

### Fixture Strategy
```python
@pytest.fixture
def arithmetic_test_data():
    """Provides deterministic test data with known expected results"""
    return {
        "dataset_1": {"values": [1, 2, 3, 4, 5]},  # sum = 15
        "dataset_2": {"values": [10, 20, 30]},     # sum = 60
        # Expected combined sum = 75
    }

@pytest.fixture
def dummy_benchmark_config():
    """Generates benchmark YAML with dummy modules"""
    # Creates config using dummy modules instead of real repositories
    # Enables full pipeline testing without external dependencies
```

### Expected Results Matrix
| Dataset | Process | Method | Expected Sum | Expected Count |
|---------|---------|---------|--------------|----------------|
| D1      | P1      | M1      | 15           | 5              |
| D1      | P1      | M2      | 15           | 5              |
| D1      | P2      | M1      | 30           | 5              |
| D1      | P2      | M2      | 30           | 5              |
| D2      | P1      | M1      | 60           | 3              |
| ...     | ...     | ...     | ...          | ...            |

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Set up dummy module repositories with simple sum operations
- [ ] Create basic linear pipeline test
- [ ] Establish test data fixtures and expected results
- [ ] Implement `@pytest.mark.e2e` infrastructure

### Phase 2: Basic Scatter (Week 2)
- [ ] Implement 2-dataset scatter test
- [ ] Validate parameter expansion works correctly
- [ ] Test file routing through DAG
- [ ] Add Python and R module variants

### Phase 3: Multi-Stage Scatter (Week 3)
- [ ] Implement full 2×2×2 scatter topology
- [ ] Add dual metric collectors
- [ ] Test combinatorial result aggregation
- [ ] Validate final aggregated results match expectations

### Phase 4: Integration Polish (Week 4)
- [ ] Add error handling scenarios
- [ ] Performance benchmarking of test execution
- [ ] CI/CD integration with appropriate timeouts
- [ ] Documentation and examples

## Test Execution Strategy

### Pytest Markers
```python
@pytest.mark.e2e           # All e2e tests
@pytest.mark.e2e_fast      # < 30 seconds
@pytest.mark.e2e_slow      # > 30 seconds
@pytest.mark.e2e_python    # Python-only modules
@pytest.mark.e2e_r         # Includes R modules
@pytest.mark.e2e_scatter   # Complex topology tests
```

### Mock Strategy
- **Mock External**: Git clones, storage backends, software installation
- **Real Internal**: YAML parsing, DAG building, workflow generation
- **Dummy Execution**: Use dummy modules instead of real computational tools

### Assertion Patterns
```python
def test_scatter_aggregation_results(dummy_benchmark, expected_results):
    # Execute full workflow
    result = run_benchmark(dummy_benchmark)

    # Validate structure
    assert result.exit_code == 0
    assert len(result.outputs) == expected_combinations

    # Validate arithmetic results
    final_sum = extract_final_sum(result.outputs)
    assert final_sum == expected_results.total_sum

    # Validate individual combinations
    for combination, expected in expected_results.items():
        actual = extract_result(result.outputs, combination)
        assert actual.sum == expected.sum
        assert actual.count == expected.count
```

## Success Criteria

### For PR Approval
- [ ] All existing benchmark YAMLs parse and execute successfully
- [ ] Basic scatter topology (2 datasets) works end-to-end
- [ ] Multi-stage scatter with collectors produces correct results
- [ ] Tests run reliably in CI (< 5 minutes total execution time)

### For Comprehensive Coverage
- [ ] Both Python and R module execution verified
- [ ] Error scenarios handled gracefully
- [ ] Performance characteristics documented
- [ ] Complex topology edge cases tested

## File Structure
```
tests/e2e/
├── README.md                           # This document
├── conftest.py                         # E2E test fixtures
├── test_linear_workflow.py            # Basic pipeline test
├── test_basic_scatter.py              # 2-dataset scatter
├── test_multi_scatter_collectors.py   # Complex topology
├── dummy_modules/
│   ├── sum_python/                     # Python sum module
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── test_data.json
│   ├── sum_r/                          # R sum module
│   │   ├── Dockerfile
│   │   ├── main.R
│   │   └── test_data.json
│   ├── filter_python/                  # Processing module
│   ├── transform_r/                    # R transformation
│   ├── metric_calculator/              # Metrics computation
│   └── collectors/                     # Aggregation modules
├── benchmark_configs/
│   ├── linear_dummy.yaml              # Simple pipeline config
│   ├── scatter_dummy.yaml             # Basic scatter config
│   └── multi_scatter_dummy.yaml       # Complex topology config
└── fixtures/
    ├── test_data.py                    # Deterministic test data
    └── expected_results.py             # Expected computation results
```
