import git
import os
from paver.easy import task
import shutil
import subprocess
import shlex
import timeout_decorator
from jinja2 import FileSystemLoader
from jinja2.environment import Environment

DEPLOY_HOST_PARAM_NAME = "deployhost"
EXPOSE_HOST_PARAM_NAME = "exposehost"
DEPLOY_SYSTEM_PARAM_NAME = "system"


def get_configdir(options):
    return options.get("configdir", current_path())


def get_repos_file(options):
    return options.get("reposfile", "%s/%s" % (get_configdir(options), "repos-to-clone.txt"))


def get_system(options):
    result = options.get(DEPLOY_SYSTEM_PARAM_NAME, None)
    if result is not None:
        return result
    elif "openshift" in get_deploy_host(options):
        return "openshift"
    elif "dokku" in get_deploy_host(options):
        return "dokku"
    elif "10.0.0.2" in get_deploy_host(options):
        return "dokku"  # vagrant
    elif "10.2.2.2" in get_deploy_host(options):
        return "openshift"  # vagrant
    else:
        return "dokku"


def get_deploy_host(options):
    return options.get(DEPLOY_HOST_PARAM_NAME, "127.0.0.1.nip.io")


def get_expose_host(options):
    return options.get(EXPOSE_HOST_PARAM_NAME, get_deploy_host(options))


def dir_name_for_repo(repo_url):
    return repo_url.split("/")[-1].split(".")[0]


def app_name_for_repo(repo_url):
    return dir_name_for_repo(repo_url)  # [:24] # for OpenSift compatibility, up to 24 chars only


def options_to_dict(options):
    result = {key: value for key, value in options.items()}
    result[DEPLOY_HOST_PARAM_NAME] = get_deploy_host(options)  # make sure it is present
    result[EXPOSE_HOST_PARAM_NAME] = get_expose_host(options)  # make sure it is present
    result[DEPLOY_SYSTEM_PARAM_NAME] = get_system(options)  # make sure it is present
    return result


def current_path():
    return os.path.dirname(os.path.realpath(__file__))


def parent_dir_path_for(a_path):
    return os.path.dirname(a_path)


def current_parent_path():
    return parent_dir_path_for(current_path())

def merge_two_dicts(x, y):
    '''Given two dicts, merge them into a new dict as a shallow copy.'''
    result = x.copy()
    result.update(y)
    return result

def templated_file_contents(options, file_path, **kwargs):
    if os.path.exists(file_path):
        env = Environment()
        env.loader = FileSystemLoader(os.path.dirname(file_path))
        template = env.get_template(os.path.basename(file_path))
        return template.render(merge_two_dicts(kwargs, options_to_dict(options)))
    else:
        return ""


def templated_file_lines_iterator(options, file_path, **kwargs):
    for line in templated_file_contents(options, file_path, **kwargs).splitlines():
        trimmed_line = line.strip()
        if len(trimmed_line) > 0 and not line.startswith("#"):
            yield trimmed_line


def repo_and_branch_and_app_name_iterator(options):
    for line in templated_file_lines_iterator(options, get_repos_file(options)):
        columns = line.strip().split(",")
        if len(columns) == 2:  # if app name is missing, we inject one
            yield [columns[0], columns[1], app_name_for_repo(columns[0])]
        else:
            yield columns


def repo_and_branch_iterator(options):
    for line in templated_file_lines_iterator(options, get_repos_file(options)):
        columns = line.strip().split(",")
        if len(columns) > 2:  # if app name is present, we remove it
            yield [columns[0], columns[1]]
        else:
            yield columns


def docker_options_config_file_path(options, original_app_dir_name):
    return "%s/dokku_docker-options/%s.txt" % (get_configdir(options), original_app_dir_name)


def app_has_docker_options(options, original_app_dir_name):
    return os.path.exists(docker_options_config_file_path(options, original_app_dir_name))


def docker_options_iterator(options, original_app_dir_name):
    for line in templated_file_lines_iterator(options, docker_options_config_file_path(options, original_app_dir_name)):
        key, _, value = line.strip().partition("=")
        yield [key, value]


def env_vars_config_file_path(options, original_app_dir_name):
    return "%s/envs/%s.env" % (get_configdir(options), original_app_dir_name)


def app_has_env_vars(options, original_app_dir_name):
    return os.path.exists(env_vars_config_file_path(options, original_app_dir_name))


def env_vars_iterator(options, original_app_dir_name, **kwargs):
    for line in templated_file_lines_iterator(options, env_vars_config_file_path(options, original_app_dir_name), **kwargs):
        key, _, value = line.strip().partition("=")
        yield [key, value]


def platform_needs_redis_as_a_service(options):
    redis_services_config_path = "%s/redis/services.txt" % (get_configdir(options))
    return os.path.exists(redis_services_config_path)


def redis_services_iterator(options):
    redis_services_config_path = "%s/redis/services.txt" % (get_configdir(options))
    for line in templated_file_lines_iterator(options, redis_services_config_path):
        yield line.strip()


def redis_config_file_path(options, original_app_dir_name):
    return "%s/redis/%s.txt" % (get_configdir(options), original_app_dir_name)


def app_has_redis(options, original_app_dir_name):
    return os.path.exists(redis_config_file_path(options, original_app_dir_name))


def redis_servicenames_iterator(options, original_app_dir_name):
    for line in templated_file_lines_iterator(options, redis_config_file_path(options, original_app_dir_name)):
        yield line.strip()


def platform_needs_rabbitmq_as_a_service(options):
    rabbitmq_services_config_path = "%s/rabbitmqs/services.txt" % (get_configdir(options))
    return os.path.exists(rabbitmq_services_config_path)


def rabbit_mq_config_file_path(options, original_app_dir_name):
    return "%s/rabbitmqs/%s.txt" % (get_configdir(options), original_app_dir_name)


def rabbit_mq_initialization_file_path(options, original_app_dir_name):
    return "%s/rabbitmqs/%s.json" % (get_configdir(options), original_app_dir_name)


def app_has_rabbitmq(options, original_app_dir_name):
    return os.path.exists(rabbit_mq_config_file_path(options, original_app_dir_name))


def rabbitmqs_servicenames_iterator(options, original_app_dir_name):
    for line in templated_file_lines_iterator(options, rabbit_mq_config_file_path(options, original_app_dir_name)):
        yield line.strip()


def rabbitmqs_services_iterator(options):
    rabbitmq_config_path = "%s/rabbitmqs/services.txt" % (get_configdir(options))
    for line in templated_file_lines_iterator(options, rabbitmq_config_path):
        yield line.strip()


def rabbitmq_template_path(options):
    return "%s/rabbitmq.json" % get_template_dir(options)


def mongo_config_file_path(options, original_app_dir_name):
    return "%s/mongos/%s.txt" % (get_configdir(options), original_app_dir_name)


def app_has_mongo(options, original_app_dir_name):
    return os.path.exists(mongo_config_file_path(options, original_app_dir_name))


def database_config_file_path(options, original_app_dir_name):
    return "%s/databases/%s.sql" % (get_configdir(options), original_app_dir_name)


def app_has_database(options, original_app_dir_name):
    return os.path.exists(database_config_file_path(options, original_app_dir_name))


def get_template_dir(options):
    return "%s/%s_templates" % (get_configdir(options), get_system(options))


class Progress(git.RemoteProgress):
    def line_dropped(self, line):
        print(self._cur_line)

    def update(self, *args):
        print(self._cur_line)


def execute_program(cmd):
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    err = err.decode().strip()
    out = out.decode().strip()
    return err, out


@timeout_decorator.timeout(10)
def execute_program_with_timeout(cmd):
    return execute_program(cmd)


def execute_program_and_print_output(cmd):
    err, out = execute_program(cmd)
    if len(err) > 0:
        print(err)
        return False
    else:
        print(out)
        return True


@timeout_decorator.timeout(10)
def execute_program_with_timeout_and_print_output(cmd):
    return execute_program_and_print_output(cmd)


def get_repo_full_path(repo_url):
    repo_dir_name = dir_name_for_repo(repo_url)
    repo_full_path = "%s/%s" % (current_parent_path(), repo_dir_name)
    return repo_full_path


@task
def git_clone_all(options):
    progress = Progress()
    for repo_url, branch in repo_and_branch_iterator(options):
        repo_full_path = get_repo_full_path(repo_url)
        if os.path.exists(repo_full_path):
            print("Already cloned: %s" % repo_url)
            continue
        os.makedirs(repo_full_path)
        try:
            repo = git.Repo.clone_from(repo_url, repo_full_path, branch=branch, progress=progress)
            print("Cloned: %s" % repo)
        except git.GitCommandError as e:
            print(e)
            return False
        print("\r\n-------------------------------------------------------------\r\n")


@task
def git_rm_all(options):
    for repo_url, branch in repo_and_branch_iterator(options):
        repo_dir_name = dir_name_for_repo(repo_url)
        repo_full_path = "%s/%s" % (current_parent_path(), repo_dir_name)
        print("Removing %s" % repo_full_path)
        shutil.rmtree(repo_full_path, ignore_errors=True)
