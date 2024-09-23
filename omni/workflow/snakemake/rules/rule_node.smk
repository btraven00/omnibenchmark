import os
from pathlib import Path

from omni_schema.datamodel.omni_schema import SoftwareBackendEnum

from omni.benchmark import Validator
from omni.workflow.snakemake import scripts
from omni.workflow.snakemake.format import formatter

def create_node_rule(node, benchmark):
    if node.is_initial():
        return _create_initial_node(benchmark, node)
    else:
        return _create_intermediate_node(benchmark, node)


def _create_initial_node(benchmark, node):
    stage_id = node.stage_id
    module_id = node.module_id
    param_id = node.param_id

    repository = node.get_repository()
    repository_url = repository.url if repository else None
    commit_hash = repository.commit if repository else None

    backend = benchmark.get_benchmark_software_backend()

    print(_get_environment_path(benchmark, node))

    rule:
        name: f"{{stage}}_{{module}}_{{param}}".format(stage=stage_id,module=module_id,param=param_id)
        wildcard_constraints:
            stage=stage_id,
            module=module_id,
            params=param_id,
            dataset=module_id
        output:
            formatter.format_output_templates_to_be_expanded(node),
        conda:
            _get_environment_path(benchmark, node) if backend == SoftwareBackendEnum.conda else None
        envmodules:
            _get_environment_path(benchmark,node) if backend == SoftwareBackendEnum.envmodules else None
        container:
            _get_environment_path(benchmark,node) if backend == (SoftwareBackendEnum.apptainer or SoftwareBackendEnum.docker) else None
        params:
            repository_url = repository_url,
            commit_hash = commit_hash,
            parameters = node.get_parameters(),
            dataset = module_id
        script: os.path.join(os.path.dirname(os.path.realpath(scripts.__file__)), 'run_module.py')


def _create_intermediate_node(benchmark, node):
    stage_id = node.stage_id
    module_id = node.module_id
    param_id = node.param_id

    outputs = node.get_outputs()

    post = stage_id + '/' + module_id
    if any(['{params}' in o for o in outputs]):
        post += '/' + param_id

    repository = node.get_repository()
    repository_url = repository.url if repository else None
    commit_hash = repository.commit if repository else None

    backend = benchmark.get_benchmark_software_backend()
    inputs_map = lambda wildcards: formatter.format_input_templates_to_be_expanded(benchmark, wildcards, return_as_dict=True)

    rule:
        name: f"{{stage}}_{{module}}_{{param}}".format(stage=stage_id,module=module_id,param=param_id)
        wildcard_constraints:
            post=post,
            stage=stage_id,
            module=module_id
        input:
            lambda wildcards: formatter.format_input_templates_to_be_expanded(benchmark, wildcards)
        output:
            formatter.format_output_templates_to_be_expanded(node)
        conda:
            _get_environment_path(benchmark, node) if backend == SoftwareBackendEnum.conda else None
        envmodules:
            _get_environment_path(benchmark,node) if backend == SoftwareBackendEnum.envmodules else None
        container:
            _get_environment_path(benchmark,node) if backend == (SoftwareBackendEnum.apptainer or SoftwareBackendEnum.docker) else None
        params:
            inputs_map = inputs_map,
            repository_url = repository_url,
            commit_hash = commit_hash,
            parameters = node.get_parameters()
        script: os.path.join(os.path.dirname(os.path.realpath(scripts.__file__)), 'run_module.py')


def create_standalone_node_rule(node, config):
    stage_id = node.stage_id
    module_id = node.module_id
    param_id = node.param_id

    repository = node.get_repository()
    repository_url = repository.url if repository else None
    commit_hash = repository.commit if repository else None

    if node.is_initial():
        rule:
            name: f"{{stage}}_{{module}}_{{param}}".format(stage=stage_id,module=module_id,param=param_id)
            wildcard_constraints:
                dataset=config['dataset']
            output:
                node.get_output_paths(config)
            params:
                repository_url = repository_url,
                commit_hash = commit_hash,
                parameters=node.get_parameters(),
                dataset=config['dataset']
            script: os.path.join(os.path.dirname(os.path.realpath(scripts.__file__)),'run_module.py')
    else:
        rule:
            name: f"{{stage}}_{{module}}_{{param}}".format(stage=stage_id,module=module_id,param=param_id)
            input:
                node.get_input_paths(config)
            output:
                node.get_output_paths(config)
            params:
                inputs_map = node.get_input_paths(config, return_as_dict=True),
                repository_url = repository_url,
                commit_hash = commit_hash,
                parameters=node.get_parameters(),
                dataset=config['dataset']
            script: os.path.join(os.path.dirname(os.path.realpath(scripts.__file__)),'run_module.py')


def _get_environment_path(benchmark, node):
    benchmark_dir = benchmark.directory
    software_backend = benchmark.get_benchmark_software_backend()
    environment = benchmark.get_benchmark_software_environments()[node.get_software_environment()]

    environment_path = None
    if (software_backend == SoftwareBackendEnum.apptainer or software_backend == SoftwareBackendEnum.docker):
        environment_path = Validator.get_environment_path(benchmark_dir, environment.apptainer)

    elif software_backend == SoftwareBackendEnum.envmodules:
        ## it's not a path, just an env name
        ## environment_path = Validator.get_environment_path(benchmark_dir,environment.envmodule)
        environment_path = environment.envmodule
    elif software_backend == SoftwareBackendEnum.conda:
        environment_path = Validator.get_environment_path(benchmark_dir, environment.conda)

    return environment_path
