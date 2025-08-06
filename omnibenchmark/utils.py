"""General utils functions"""

import os
import subprocess
from pathlib import Path
from typing import List, Union, Any
import yaml
import warnings

# Import moved to function to avoid circular import


def try_avail_envmodule(module_name: str) -> bool:
    env = {}
    env.update(os.environ)

    command = f"""
    . "$LMOD_PKG"/init/profile ;
    module purge ;
    module avail {module_name}"""
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
        env=env,
    )

    return "No module(s) or extension(s) found!" not in result.stderr


def as_list(input: Union[List, Any]):
    return input if isinstance(input, List) else [input]


def parse_instance(path: Path, target_class) -> Any:
    """
    DEPRECATED: Use Benchmark.from_yaml() instead.

    Load a model of target_class from a file.
    """
    warnings.warn(
        "parse_instance is deprecated. Use Benchmark.from_yaml() or the appropriate model's from_yaml() method instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Import here to avoid circular imports and to make deprecation clearer
    from omnibenchmark.model import Benchmark

    # For backwards compatibility, if target_class is the old omni_schema.Benchmark,
    # use the new Benchmark.from_yaml() method
    if hasattr(target_class, "__module__") and "omni_schema" in target_class.__module__:
        return Benchmark.from_yaml(path)

    # Otherwise, try to load with yaml and instantiate
    with path.open("r") as file:
        data = yaml.load(file, yaml.SafeLoader)
        return target_class(**data) if callable(target_class) else data


def merge_dict_list(list_of_dicts):
    """Merge a list of dictionaries into a single dictionary."""
    merged_dict = {
        key: value for d in list_of_dicts if d is not None for key, value in d.items()
    }

    return merged_dict


def format_mc_output(output, out_dir: Path, collector_id: str):
    """Format metric collector output path.

    Args:
        output: IOFile object
        out_dir: Output directory path
        collector_id: Collector identifier
    """
    if output.path:
        o = output.path.replace("{input}", str(out_dir))
        o = o.replace("{name}", collector_id)
        return o
    else:
        return str(out_dir / output.id)
