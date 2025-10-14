# End-to-End Tests for Omnibenchmark

## Purpose

Simple e2e tests to validate core omnibenchmark functionality with deterministic dummy modules.

## Goal

Create a minimal working e2e test that:
1. Uses a simple linear pipeline: data → process → method → metric
2. Uses dummymodule for predictable arithmetic operations
3. Validates outputs are correct
4. Runs quickly (< 2 minutes)

## Test Strategy

### Linear Pipeline Test

Test a basic workflow with deterministic arithmetic operations:

```yaml
data → process → method → metric
```

**Expected behavior:**
- Data module produces known numeric values
- Process module performs arithmetic transformation
- Method module applies another operation
- Metric module calculates final result
- All outputs are predictable and testable

### Using Dummymodule

The `dummymodule` provides arithmetic operations:
```bash
run_dummymodule.py --evaluate "2+2" --output result.json
# Produces: {"result": 4, "error": null}
```

This gives us:
- **Deterministic results** - Same input always produces same output
- **No external dependencies** - Just arithmetic
- **Fast execution** - No heavy computation
- **Easy validation** - Assert exact numeric values

### Test Design

1. **Create simple benchmark config** using dummymodule at each stage
2. **Use known input values** (e.g., [1, 2, 3, 4, 5])
3. **Define expected arithmetic chain**:
   - Data: outputs `{"values": [1, 2, 3, 4, 5]}`
   - Process: sums → `{"result": 15}`
   - Method: multiplies by 2 → `{"result": 30}`
   - Metric: computes mean → `{"result": 6.0}` (30/5)
4. **Assert final result** matches expected value

### Implementation Plan

1. **Create test config** - Simple YAML with dummymodule at each stage
2. **Define arithmetic chain** - Predictable operations
3. **Run workflow** - Execute full pipeline
4. **Validate outputs** - Check intermediate and final results
5. **Factor out boilerplate** - Reuse existing workflow test infrastructure

## File Structure

```
tests/e2e/
├── README.md                    # This file
├── test_linear_arithmetic.py    # Linear pipeline with dummymodule
├── conftest.py                  # Shared fixtures
└── configs/
    └── linear_arithmetic.yaml   # Simple benchmark config
```
