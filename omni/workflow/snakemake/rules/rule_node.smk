import os

from omni_schema.datamodel.omni_schema import SoftwareBackendEnum

from omni.benchmark import Validator
from omni.workflow.snakemake import scripts
from omni.workflow.snakemake.format import formatter

def create_node_rule(node, benchmark, config):
    if node.is_initial():
        return _create_initial_node(benchmark, node, config)
    else:
        return _create_intermediate_node(benchmark, node, config)


def _create_initial_node(benchmark, node, config):
    stage_id = node.stage_id
    module_id = node.module_id
    param_id = node.param_id

    repository = node.get_repository()
    repository_url = repository.url if repository else None
    commit_hash = repository.commit if repository else None

    rule:
        name: f"{{stage}}_{{module}}_{{param}}".format(stage=stage_id,module=module_id,param=param_id)
        wildcard_constraints:
            stage=stage_id,
            module=module_id,
            params=param_id,
            dataset=module_id
        output:
            formatter.format_output_templates_to_be_expanded(node)

        # Snakemake 8.25.2 introduced changes that no longer allow None for environment values
        # Hence we provide alternatives for `conda`, `envmodules`, `container` which do not exist, although it will not affect the normal flow
        # See https://github.com/snakemake/snakemake/releases/tag/v8.25.2
        conda:
            _get_environment_path(benchmark, node, SoftwareBackendEnum.conda) or "conda_not_provided.yml"
        envmodules:
            _get_environment_path(benchmark, node, SoftwareBackendEnum.envmodules) or "module/not_provided/0.0.0"
        container:
            _get_environment_path(benchmark, node, SoftwareBackendEnum.apptainer) or "container_not_provided.sif"
        params:
            repository_url = repository_url,
            commit_hash = commit_hash,
            parameters = node.get_parameters(),
            dataset = module_id,
            keep_module_logs=config['keep_module_logs']
        script: os.path.join(os.path.dirname(os.path.realpath(scripts.__file__)), 'run_module.py')


def _create_intermediate_node(benchmark, node, config):
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

        # Snakemake 8.25.2 introduced changes that no longer allow None for environment values
        # Hence we provide alternatives for `conda`, `envmodules`, `container` which do not exist, although it will not affect the normal flow
        # See https://github.com/snakemake/snakemake/releases/tag/v8.25.2
        conda:
            _get_environment_path(benchmark, node, SoftwareBackendEnum.conda) or "conda_not_provided.yml"
        envmodules:
            _get_environment_path(benchmark, node, SoftwareBackendEnum.envmodules) or "module/not_provided/0.0.0"
        container:
            _get_environment_path(benchmark, node, SoftwareBackendEnum.apptainer) or "container_not_provided.sif"
        params:
            inputs_map = inputs_map,
            repository_url = repository_url,
            commit_hash = commit_hash,
            parameters = node.get_parameters(),
            keep_module_logs=config['keep_module_logs']
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
                dataset=config['dataset'],
                keep_module_logs=config['keep_module_logs']
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
                dataset=config['dataset'],
                keep_module_logs=config['keep_module_logs']
            script: os.path.join(os.path.dirname(os.path.realpath(scripts.__file__)),'run_module.py')


def _get_environment_path(benchmark, node, software_backend):
    benchmark_dir = benchmark.directory
    environment = benchmark.get_benchmark_software_environments()[node.get_software_environment()]
    environment_path = Validator.get_environment_path(software_backend, environment, benchmark_dir)

    return environment_path
