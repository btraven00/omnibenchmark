#!/usr/bin/env python3
"""Example usage of the omnibenchmark artifact validation engine."""

import json
import tempfile
from pathlib import Path


def create_sample_data(base_dir: Path):
    """Create sample benchmark output structure."""
    # Create directory structure
    dataset_dir = base_dir / "dataset" / "synthetic_data"
    method_dir = base_dir / "method" / "kmeans"
    metric_dir = base_dir / "metric" / "silhouette"

    for dir in [dataset_dir, method_dir, metric_dir]:
        dir.mkdir(parents=True, exist_ok=True)

    # Create dataset files
    (dataset_dir / "data.csv").write_text("""sample_id,feature_1,feature_2,label
1,0.1,0.2,A
2,0.2,0.4,A
3,0.3,0.6,B
4,0.4,0.8,B
""")

    # Dataset metadata
    (dataset_dir / "metadata.json").write_text(
        json.dumps(
            {
                "dataset_name": "synthetic_clustering",
                "n_samples": 4,
                "n_features": 2,
                "n_classes": 2,
            },
            indent=2,
        )
    )

    # Method outputs
    (method_dir / "clusters.csv").write_text("""sample_id,cluster_id
1,0
2,0
3,1
4,1
""")

    (method_dir / "params.json").write_text(
        json.dumps(
            {"algorithm": "kmeans", "n_clusters": 2, "random_state": 42}, indent=2
        )
    )

    # Metric outputs
    (metric_dir / "scores.json").write_text(
        json.dumps({"silhouette_score": 0.75, "davies_bouldin_score": 0.45}, indent=2)
    )

    # Create an invalid module
    invalid_method_dir = base_dir / "method" / "hierarchical"
    invalid_method_dir.mkdir(parents=True, exist_ok=True)
    (invalid_method_dir / "clusters.csv").touch()  # Empty file


def main():
    """Run validation examples."""
    # Import here to show the optional dependency handling
    try:
        from omnibenchmark.artifact_validation import ValidationEngine
    except ImportError as e:
        print(f"Error: {e}")
        print(
            "Please install validation dependencies: pip install omnibenchmark[validation]"
        )
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        # Create sample data
        print("Creating sample data...")
        create_sample_data(base_dir)

        # Create validation config
        config_path = base_dir / "validation.yaml"
        config_path.write_text(
            """
version: 1.0
stages:
  dataset:
    rules:
      - file_pattern: "*.csv"
        validations:
          - type: not_empty
          - type: has_columns
            columns: ["sample_id", "feature_1", "feature_2", "label"]

  method:
    rules:
      - file_pattern: "clusters.csv"
        validations:
          - type: not_empty
          - type: has_columns
            columns: ["sample_id", "cluster_id"]

  metric:
    rules:
      - file_pattern: "scores.json"
        validations:
          - type: not_empty
""".strip()
        )

        # Initialize validation engine
        print("\nInitializing validation engine...")
        engine = ValidationEngine(config_path)

        # Validate all stages
        print("\n" + "=" * 60)
        print("Validating all stages")
        print("=" * 60)

        report = engine.validate_all(base_dir, benchmark_name="clustering_benchmark")
        print(engine.format_results(report, format="human"))

        # JSON output
        print("\n" + "=" * 60)
        print("JSON output (truncated)")
        print("=" * 60)

        json_output = engine.format_results(report, format="json")
        data = json.loads(json_output)
        # Show only first result for brevity
        truncated = {
            "validation_timestamp": data["validation_timestamp"],
            "benchmark": data["benchmark"],
            "total_modules": data["total_modules"],
            "passed_modules": data["passed_modules"],
            "failed_modules": data["failed_modules"],
            "first_result": data["results"][0] if data["results"] else None,
        }
        print(json.dumps(truncated, indent=2))


if __name__ == "__main__":
    main()
