"""cli commands related to benchmark/module execution and start"""

import os
import sys
from itertools import chain
from pathlib import Path

import click

from omni.cli.utils.logging import debug_option, logger
from omni.io.utils import get_storage_from_benchmark
from omni.cli.utils.validation import validate_benchmark


@click.group(name="run")
@debug_option
@click.pass_context
def run(ctx):
    """Run benchmarks or benchmark modules."""
    ctx.ensure_object(dict)


@run.command(name="benchmark")
@click.option(
    "-b",
    "--benchmark",
    help="Path to benchmark yaml file or benchmark id.",
    required=True,
    envvar="OB_BENCHMARK",
    type=click.Path(exists=True),
)
@click.option(
    "-p",
    "--threads",
    help="The parallelism level for the workflow scheduler.",
    type=int,
    default=1,
)
@click.option(
    "-u",
    "--update",
    help="Force re-run execution for all modules and stages.",
    is_flag=True,
    default=False,
)
@click.option("-d", "--dry", help="Dry run.", is_flag=True, default=False)
@click.option(
    "-l",
    "--local",
    help="Execute and store results locally. Default False.",
    is_flag=True,
    default=False,
)
@click.option(
    "--keep-module-logs/--no-keep-module-logs",
    default=False,
    help="Keep module-specific log files after execution.",
)
@click.pass_context
def run_benchmark(ctx, benchmark, threads, update, dry, local, keep_module_logs):
    """Run a benchmark as specified in the yaml."""
    ctx.ensure_object(dict)

    from omni.io.utils import remote_storage_snakemake_args
    from omni.workflow.snakemake import SnakemakeEngine
    from omni.workflow.workflow import WorkflowEngine

    benchmark = validate_benchmark(benchmark)
    workflow: WorkflowEngine = SnakemakeEngine()

    if update and not dry:
        update_prompt = click.confirm(
            "Are you sure you want to re-run the entire workflow?", abort=True
        )
        if not update_prompt:
            raise click.Abort()

    if not local:
        storage_options = remote_storage_snakemake_args(benchmark)
        # creates bucket if it doesn't exist
        _ = get_storage_from_benchmark(benchmark)
    else:
        storage_options = {}

    # Controlling resource allocation with Snakemake is tricky
    # -c only controls the number of parallelism for the Snakemake scheduler
    # bioinfo methods are not designed with limited resources in mind (most)
    # Future: Create yaml for communicating resources for individual methods
    logger.info("Running benchmark...")
    success = workflow.run_workflow(
        benchmark,
        cores=threads,
        update=update,
        dryrun=dry,
        keep_module_logs=keep_module_logs,
        backend=benchmark.get_benchmark_software_backend(),
        **storage_options,
    )

    if success:
        logger.info("Benchmark run has finished successfully.")
    else:
        logger.error("Benchmark run has failed.")

    sys.exit(0 if success else 1)  # click.Exit(code=0 if success else 1)


@run.command(name="module")
@click.option(
    "-b",
    "--benchmark",
    help="Path to benchmark yaml file or benchmark id.",
    required=True,
    envvar="OB_BENCHMARK",
    type=click.Path(exists=True),
)
@click.option("-m", "--module", help="Module id to execute", type=str, required=True)
@click.option(
    "-i",
    "--input_dir",
    help="Path to the folder with the appropriate input files.",
    type=click.Path(exists=True, writable=True),
    default=None,
)
@click.option("-d", "--dry", help="Dry run.", is_flag=True, default=False)
@click.option(
    "-u",
    "--update",
    help="Force re-run execution for all modules and stages.",
    is_flag=True,
    default=False,
)
@click.option(
    "--keep-module-logs/--no-keep-module-logs",
    default=False,
    help="Keep module-specific log files after execution.",
)
@click.pass_context
def run_module(ctx, benchmark, module, input_dir, dry, update, keep_module_logs):
    """
    Run a specific module that is part of the benchmark.
    """
    behaviours = {"input": input_dir, "example": None, "all": None}

    non_none_behaviours = {
        key: value for key, value in behaviours.items() if value is not None
    }
    if len(non_none_behaviours) >= 2:
        logger.error(
            "Error: Only one of '--input_dir', '--example', or '--all' should be set. Please choose only one option.",
        )
        sys.exit(1)  # raise click.Exit(code=1)
    else:
        # Construct a message specifying which option is set
        behaviour = list(non_none_behaviours)[0] if non_none_behaviours else None

        if behaviour == "example" or behaviour == "all":
            if behaviour == "example":
                logger.info("Running module on a predefined remote example dataset.")
            if behaviour == "all":
                logger.info("Running module on all available remote datasets.")

            # TODO Check how snakemake storage decorators work, do we have caching locally or just remote?
            # TODO Implement remote execution using remote url from benchmark definition
            logger.error(
                "Error: Remote execution is not supported yet. Workflows can only be run in local mode.",
            )
            sys.exit(1)  # raise click.Exit(code=1)
        else:
            logger.info(f"Running module on a local dataset.")
            benchmark = validate_benchmark(benchmark)

            benchmark_nodes = benchmark.get_nodes_by_module_id(module_id=module)
            is_entrypoint_module = all(
                [node.is_entrypoint() for node in benchmark_nodes]
            )
            if len(benchmark_nodes) > 0:
                logger.info(
                    f"Found {len(benchmark_nodes)} workflow nodes for module {module}."
                )

                if not is_entrypoint_module and len(non_none_behaviours) == 0:
                    logger.error(
                        "Error: At least one option must be specified. Use '--input_dir', '--example', or '--all'.",
                    )
                    sys.exit(1)  # raise click.Exit(code=1)
                elif input_dir is None:
                    input_dir = os.getcwd()

                logger.info("Running module benchmark...")

                # Check if input path exists and is a directory
                if os.path.exists(input_dir) and os.path.isdir(input_dir):
                    benchmark_datasets = benchmark.get_benchmark_datasets()

                    # Check available files in input to figure out what dataset are we processing
                    # if we're given the initial dataset module to process, then we know
                    if module in benchmark_datasets:
                        dataset = module

                    # else we try to figure the dataset based on the files present in the input directory
                    else:
                        files = os.listdir(input_dir)
                        base_names = [file.split(".")[0] for file in files]
                        dataset = next(
                            (d for d in benchmark_datasets if d in base_names), None
                        )

                    if dataset is not None:
                        # Check if input directory contains all necessary input files
                        required_inputs = list(
                            map(lambda node: node.get_inputs(), benchmark_nodes)
                        )
                        required_inputs = list(chain.from_iterable(required_inputs))
                        required_input_files = list(
                            set([os.path.basename(path) for path in required_inputs])
                        )
                        required_input_files = [
                            file.format(dataset=dataset)
                            for file in required_input_files
                        ]

                        input_files = os.listdir(input_dir)
                        missing_files = [
                            file
                            for file in required_input_files
                            if file not in input_files
                        ]

                        if len(missing_files) == 0:
                            from omni.workflow.snakemake import SnakemakeEngine
                            from omni.workflow.workflow import WorkflowEngine

                            workflow: WorkflowEngine = SnakemakeEngine()
                            for benchmark_node in benchmark_nodes:
                                # When running a single module, it doesn't have sense to make parallelism level (cores) configurable
                                success = workflow.run_node_workflow(
                                    node=benchmark_node,
                                    input_dir=Path(input_dir),
                                    dataset=dataset,
                                    cores=1,
                                    update=update,
                                    dryrun=dry,
                                    keep_module_logs=keep_module_logs,
                                    backend=benchmark.get_benchmark_software_backend(),
                                )

                                if success:
                                    logger.info(
                                        "Module run has finished successfully.",
                                    )
                                else:
                                    logger.error(
                                        "Module run has failed.",
                                    )

                                sys.exit(
                                    0 if success else 1
                                )  # raise click.Exit(code=0 if success else 1)

                        else:
                            logger.error(
                                f"Error: The following required input files are missing from the input directory: {missing_files}.",
                            )

                            sys.exit(1)  # raise click.Exit(code=1)

                    else:
                        logger.error(
                            f"Error: Could not infer the appropriate dataset to run the node workflow on based on the files available in `{input_dir}`. None of the available datasets {benchmark_datasets} match the base names of the files.",
                        )

                        sys.exit(1)  # raise click.Exit(code=1)
                else:
                    logger.error(
                        f"Error: Input directory does not exist or is not a valid directory: `{input_dir}`",
                    )

                    sys.exit(1)  # raise click.Exit(code=1)

            else:
                logger.error(
                    f"Error: Could not find module with id `{module}` in benchmark definition",
                )
                sys.exit(1)  # raise click.Exit(code=1)


@run.command(no_args_is_help=True, name="validate")
@click.option(
    "-b",
    "--benchmark",
    help="Path to benchmark yaml file or benchmark id.",
    envvar="OB_BENCHMARK",
    type=click.Path(exists=True),
)
@click.pass_context
def validate_yaml(ctx, benchmark):
    """Validate a benchmark yaml."""
    logger.info("Validating a benchmark yaml.")
    benchmark = validate_benchmark(benchmark)
