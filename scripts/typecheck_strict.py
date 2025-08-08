#!/usr/bin/env python3
"""Run strict type checking on specific modules."""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Modules that should have strict type checking
STRICT_MODULES = [
    "omnibenchmark/dag",
    "omnibenchmark/model",
    "tests/dag",
]


def run_pyright_on_module(module_path: str) -> Tuple[bool, str]:
    """Run pyright on a specific module with strict checking.

    Args:
        module_path: Path to the module to check

    Returns:
        Tuple of (success, output)
    """
    cmd = [sys.executable, "-m", "pyright", module_path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(__file__).parent.parent,
        )
        # Pyright returns 0 for success, 1 for errors
        success = result.returncode == 0
        output = result.stdout if result.stdout else result.stderr

        # Parse the output to extract error/warning counts
        # lines = output.strip().split("\n")
        # summary_line = lines[-1] if lines else ""

        return success, output
    except Exception as e:
        return False, f"Error running pyright: {e}"


def main() -> int:
    """Run strict type checking on all specified modules."""
    print("Running strict type checking on new modules...")
    print("=" * 70)
    print("\nNote: These modules are configured for strict type checking in")
    print("pyrightconfig.json with executionEnvironments settings.\n")

    all_passed = True
    results: List[Tuple[str, bool, str]] = []

    for module in STRICT_MODULES:
        module_path = Path(module)
        if not module_path.exists():
            print(f"⚠️  Skipping {module} (path does not exist)")
            continue

        print(f"Checking {module}...", end=" ", flush=True)
        success, output = run_pyright_on_module(module)
        results.append((module, success, output))

        if success:
            # Extract summary from pyright output
            lines = output.strip().split("\n")
            summary = lines[-1] if lines else "No output"

            # Check if it's the "0 errors, 0 warnings" format
            if "0 errors" in summary:
                print(f"✅ PASS ({summary})")
            else:
                print("✅ PASS")
        else:
            print("❌ FAIL")
            all_passed = False

    # Print detailed results only for failures
    failures = [(m, o) for m, s, o in results if not s]
    if failures:
        print("\n" + "=" * 70)
        print("FAILED MODULES - DETAILED OUTPUT")
        print("=" * 70)

        for module, output in failures:
            print(f"\n--- {module} ---")
            print(output)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    print(f"\nModules checked: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")

    if all_passed:
        print("\n✅ All modules passed strict type checking!")
        print(
            "\nThese modules are configured with strict type checking in pyrightconfig.json"
        )
        print("using executionEnvironments. This ensures:")
        print("- All functions have type annotations")
        print("- All variables have clear types")
        print("- No implicit Any types")
        print("- Strict null/None checking")
        return 0
    else:
        print("\n❌ Some modules failed type checking.")
        print("\nTo fix type errors:")
        print("1. Add type annotations to all function parameters and return values")
        print("2. Ensure all variables have explicit types or can be inferred")
        print("3. Use 'typing' module for complex types (List, Dict, Optional, etc.)")
        print("4. Avoid using Any type unless absolutely necessary")
        print("5. Handle None values explicitly with Optional[T] or Union[T, None]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
