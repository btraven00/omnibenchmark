# This file has been removed as part of the migration away from the converter pattern.
# The BenchmarkConverter and LinkMLConverter classes are no longer needed.
# Use the Benchmark class directly instead of going through a converter layer.
#
# Migration guide:
# - Instead of: converter = BenchmarkConverter(path); converter.get_name()
# - Use: benchmark = Benchmark.from_yaml(path); benchmark.get_name()
#
# The converter was just a pass-through wrapper that added no value.
