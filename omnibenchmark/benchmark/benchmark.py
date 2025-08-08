import os.path

from pathlib import Path
from typing import Dict, List, Set, Optional

from omnibenchmark.benchmark._mermaid import generate_mermaid_diagram
from omnibenchmark.benchmark._paths import (
    collect_output_paths,
    collect_path_exclusions,
)

from omnibenchmark.benchmark import _graph as graph
from omnibenchmark.model import Benchmark as BenchmarkModel
from omnibenchmark.utils import format_mc_output

from ._dot import export_to_dot


class ExecutionContext:
    """Encapsulates execution-specific context like paths and directories."""

    def __init__(self, benchmark_yaml: Path, out_dir: Path = Path("out")):
        # base path is always the location of the benchmark YAML file
        # TODO: rename to definition_file
        self.path = benchmark_yaml

        # directory is used to lookup files and directories expressed in relative paths,
        # like the environment definition paths
        self.directory = benchmark_yaml.parent.absolute()

        # where are we going to write the output files, in the case of local execution
        self.out_dir = out_dir

        # TODO: only if needed, otherwise we always create the out dir
        if not os.path.exists(out_dir):
            os.mkdir(out_dir)


class BenchmarkExecution:
    """
    BenchmarkExecution contains the execution context and the benchmark model.
    """

    def __init__(self, benchmark_yaml: Path, out_dir: Path = Path("out")):
        self.context = ExecutionContext(benchmark_yaml, out_dir)

        self.model = BenchmarkModel.from_yaml(benchmark_yaml)

        # Validate execution context separately from pure model validation
        # Pure model validation happens automatically via Pydantic
        self.model.validate_execution_context(self.context.directory)

        # Build DAG directly from model
        self.G = graph.build_benchmark_dag(self.model, self.context.out_dir)

        self.execution_paths = None

    def get_converter(self):
        # Create converter on demand for compatibility
        from omnibenchmark.model import BenchmarkConverter

        return BenchmarkConverter(self.context.path)

    def get_storage_api(self) -> Optional[str]:
        """Get storage API with backward compatibility."""
        return self.model.get_storage_api()

    def get_storage_bucket_name(self) -> Optional[str]:
        """Get storage bucket name with backward compatibility."""
        return self.model.get_storage_bucket_name()

    def get_storage_endpoint(self) -> Optional[str]:
        """Get storage endpoint."""
        return self.model.get_storage_endpoint()

    def get_model(self):
        """Get the underlying Pydantic model."""
        return self.model

    def get_benchmark_name(self):
        return self.model.get_name()

    def get_benchmark_version(self):
        return self.model.get_version()

    def get_benchmark_author(self):
        return self.model.get_author()

    def get_benchmark_software_backend(self):
        return self.model.get_software_backend()

    def get_benchmark_software_environments(self):
        return self.model.get_software_environments()

    def get_definition(self):
        return self.model

    def get_definition_file(self) -> Path:
        return self.context.path

    def get_easyconfigs(self):
        return self.model.get_easyconfigs()

    def get_conda_envs(self):
        return self.model.get_conda_envs()

    def get_nodes(self):
        return list(self.G.nodes)

    def get_stages(self):
        return self.model.get_stages()

    def get_node_by_id(self, node_id):
        return graph.find_node_by_id(self.G, node_id)

    def get_nodes_by_module_id(self, module_id: str) -> List:
        return graph.get_nodes_by_module_id(self.G, module_id)

    def get_nodes_by_stage_id(self, stage_id: str) -> List:
        return graph.get_nodes_by_stage_id(self.G, stage_id)

    def get_benchmark_datasets(self) -> List[str]:
        return graph.get_benchmark_datasets(self.model, self.get_stages())

    def get_execution_paths(self):
        if self.execution_paths is None:
            self.execution_paths = self._generate_execution_paths()

        return self.execution_paths

    def get_output_paths(self) -> Set[str]:
        execution_paths = self.get_execution_paths()
        return collect_output_paths(execution_paths, self.context.out_dir, self.model)

    def get_metric_collector_output_paths(self):
        collectors = self.get_metric_collectors()
        output_paths = []

        for collector in collectors:
            for output in collector.outputs:
                output_paths.append(
                    format_mc_output(output, self.context.out_dir, collector.id)
                )

        return set(output_paths)

    def get_explicit_inputs(self, stage_id: str):
        stage = self.model.get_stage(stage_id)
        if stage is None:
            return []
        implicit_inputs = self.model.get_stage_implicit_inputs(stage)
        explicit_inputs = [self.model.get_explicit_inputs(i) for i in implicit_inputs]
        return explicit_inputs

    def get_explicit_input(self, input_ids: List[str]) -> Dict[str, str]:
        return self.model.get_explicit_inputs(input_ids)

    def get_explicit_outputs(self, stage_id: str):
        stage = self.model.get_stage(stage_id)
        if stage is None:
            return {}
        return self.model.get_stage_outputs(stage)

    def get_available_parameter(self, module_id: str):
        node = graph.find_node_with_module_id(self.G, module_id)
        return node.get_parameters() if node else None

    def get_metric_collectors(self):
        return self.model.get_metric_collectors()

    def _generate_execution_paths(self):
        path_exclusions = collect_path_exclusions(self.model)
        initial_nodes, terminal_nodes = graph.find_initial_and_terminal_nodes(self.G)

        execution_paths = []
        for initial_node in initial_nodes:
            for terminal_node in terminal_nodes:
                paths = graph.list_all_paths(self.G, initial_node, terminal_node)
                paths_after_exclusion = graph.exclude_paths(paths, path_exclusions)

                execution_paths.extend(paths_after_exclusion)

        return execution_paths

    # Visualization functions

    def export_to_dot(self):
        return export_to_dot(self.G, title=self.get_benchmark_name())

    def export_to_mermaid(self, show_params: bool = True) -> str:
        """Export the benchmark workflow as a Mermaid diagram.

        Args:
            show_params: Whether to include parameter subgraphs in the diagram

        Returns:
            A string containing the complete Mermaid diagram syntax
        """
        return generate_mermaid_diagram(self.model, self.G, show_params)

    def __str__(self):
        return f"Benchmark({self.get_definition})"
