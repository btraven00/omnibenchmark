# Type Checking Setup

This project uses type checking to ensure code quality and catch errors early. We use a dual setup that supports both `pyright` and `ty` for flexibility and performance.

## Quick Start

```bash
# Run type checking on core modules
python scripts/typecheck_strict.py
```

## Type Checkers Supported

### pyright (Default)
- **Pros**: Full-featured, excellent VS Code integration, stable
- **Cons**: Slower on large codebases
- **Installation**: `pip install pyright`

### ty (Pre-release - Use with Caution)
- **Pros**: Much faster than pyright when it works
- **Cons**: Pre-release software, unstable, frequent failures
- **Installation**: `pip install ty` (not recommended for CI)
- **Status**: ⚠️ Not ready for production use

The script can try `ty` but will fallback to `pyright` when it fails.

## Configuration Files

### pyrightconfig.strict.json
Enhanced type checking for core modules with focus on safety over strictness:
- ✅ **Critical errors**: Assignment types, optional/None safety, method overrides
- ⚠️ **Warnings**: Missing parameter types, unused variables
- 🔇 **Disabled**: Overly strict checks that block development

### ty.toml
Equivalent configuration for `ty` with same safety focus but optimized for speed.

### pyrightconfig.json
Basic type checking for the entire codebase with relaxed settings.

## CI Integration

Type checking runs in CI after linting:
- Uses `continue-on-error: true` during migration period
- Only uses stable `pyright` in CI (ty is pre-release)
- Does not block CI during gradual adoption

## Adding New Modules

To add a module to enhanced type checking:

1. Add the path to `include` in both config files:
   ```json
   // pyrightconfig.strict.json
   "include": [
     "omnibenchmark/dag",
     "omnibenchmark/model", 
     "omnibenchmark/benchmark",
     "tests/dag",
     "your/new/module"  // Add here
   ]
   ```

2. Fix any type errors that appear
3. Gradually enable stricter settings as the module matures

## Local Development

### Command Line
```bash
# Check specific module  
pyright omnibenchmark/model           # Recommended (stable)
ty check omnibenchmark/model           # Faster but pre-release

# Check all enhanced modules (with fallback logic)
python scripts/typecheck_strict.py
```

## Gradual Migration Strategy

1. **Phase 1**: Basic safety (current) - Focus on None/Optional safety
2. **Phase 2**: Add parameter type hints gradually  
3. **Phase 3**: Enable stricter settings as codebase improves
4. **Phase 4**: Full strict mode for new modules

## Troubleshooting

### Too many warnings
Warnings don't fail CI and can be addressed gradually. Focus on errors first.

## Type Checking Best Practices

1. **Start with Optional/None safety** - Most critical for runtime errors
2. **Add return type hints** - Helps catch logic errors early  
3. **Use Union types sparingly** - Prefer specific types when possible
4. **Avoid Any** - Use specific types or disable checking for that line
