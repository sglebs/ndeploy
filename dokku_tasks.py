from core_tasks import *
from paver.easy import task, needs
import timeout_decorator
#from urllib.parse import urlparse

_RABBITMQ_SETUP_CMD = \
      'curl -i -u %s:%s -H "content-type:application/json" -X POST --data @%s http://%s:%s/api/definitions'


def get_dokku_remote_repo_name(options):
    default = "dokku"  # ""dokku%s" % get_deploy_host(options).partition(".")[0].partition("-")[0]
    return options.get("dokkuremote", default)


def get_dokku_app_env_var_value(options, app_name, env_var):
    cmd = "ssh dokku@%s config %s" % (get_deploy_host(options), app_name)
    err, out = execute_program(cmd)
    for line in out.splitlines():
        key, _, value = line.strip().partition(":")
        if key == env_var:
            return value
    return ""


@task
@needs(['git_clone_all'])
def dokku_remote_git_add(options):
    host = get_deploy_host(options)
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        repo_dir_name = dir_name_for_repo(repo_url)
        repo_full_path = "%s/%s" % (current_parent_path(), repo_dir_name)
        repo = git.Repo(repo_full_path)
        dokku_remote = "dokku@%s:%s" % (host, app_name)
        remote_names = [remote.name for remote in repo.remotes]
        remote_urls = [remote.url for remote in repo.remotes]
        if dokku_remote in remote_urls:
            print("Already in remote: %s" % dokku_remote)
            continue
        if "dokku" in remote_names:
            repo.delete_remote("dokku")
        print("Adding remote %s" % dokku_remote)
        repo.create_remote(get_dokku_remote_repo_name(options), dokku_remote)


@task
def dokku_create_empty_apps(options):
    print("------------------------------------------------------------")
    print("CREATING APPS")
    print("------------------------------------------------------------")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        cmd = "ssh dokku@%s apps:create %s" % (get_deploy_host(options), app_name)
        err, out = execute_program(cmd)
        if len(err) > 0 and 'already taken' not in err:  # some other error
            print(err)
            return False
        else:
            print(out)


@task
@needs(['dokku_create_empty_apps'])
def dokku_create_apps_env_vars(options):
    print("------------------------------------------------------------")
    print("ENV VARS CONFIG")
    print("------------------------------------------------------------")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        dokku_create_apps_env_vars_if_needed(options, repo_url, app_name)


def dokku_create_apps_env_vars_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if app_has_env_vars(options, original_app_name):
        print("...Configuring env vars for %s" % app_name)
        key_values = ['%s="%s"' % (key, value.replace(" ", "\\ ").replace('"', '\\"')) for key, value in
                      env_vars_iterator(options, original_app_name, appname=app_name)]
        all_vars = " ".join(key_values)
        cmd = "ssh dokku@%s config:set --no-restart %s %s" % (get_deploy_host(options), app_name, all_vars)
        print(cmd)
        os.system(cmd)
    else:
        print("WARNING: NO ENV VARS for %s" % app_name)


@task
@needs(['dokku_create_empty_apps'])
def dokku_set_docker_options(options):
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        dokku_set_docker_options_if_needed(options, repo_url, app_name)


def dokku_set_docker_options_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_docker_options(options, original_app_name):
        return
    print("...Configuring docker options for %s" % app_name)
    for phase, phase_options in docker_options_iterator(options, original_app_name):
        cmd = 'ssh dokku@%s docker-options:add %s %s "%s"' % (
            get_deploy_host(options), app_name, phase, phase_options)
        print(cmd)
        os.system(cmd)

@task
def dokku_start_postgres(options):
    cmd = "ssh dokku@%s psql:start" % (get_deploy_host(options))
    print("...Starting database service:  %s" % cmd)
    execute_program_and_print_output(cmd)

@task
@needs(['dokku_create_empty_apps', 'dokku_start_postgres'])
def dokku_create_databases(options):
    print("------------------------------------------------------------")
    print("DATABASE SETUP")
    print("------------------------------------------------------------")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        ok = dokku_create_database_if_needed(options, repo_url, app_name)
        if not ok:
            return False


def dokku_create_database_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_database(options, original_app_name):
        return
    print("...Configuring database for %s" % app_name)
    cmd = "ssh dokku@%s psql:create %s" % (get_deploy_host(options), app_name)
    ok = execute_program_and_print_output(cmd)
    if not ok:
        return False


@task
@needs(['dokku_create_empty_apps'])
def dokku_create_mongos(options):
    print("------------------------------------------------------------")
    print("MONGO SETUP")
    print("------------------------------------------------------------")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        dokku_create_mongo_if_needed(options, repo_url, app_name)


def dokku_create_mongo_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_mongo(options, original_app_name):
        return
    print("...Configuring mongo for %s" % app_name)
    os.system("ssh dokku@%s mongo:create %s" % (get_deploy_host(options), app_name))
    os.system("ssh dokku@%s mongo:link %s %s" % (get_deploy_host(options), app_name, app_name))


@task
def dokku_create_rabbitmq_services(options):
    print("------------------------------------------------------------")
    print("RABBITMQ SETUP")
    print("------------------------------------------------------------")
    if not platform_needs_rabbitmq_as_a_service(options):
        return
    options["_rabbitmqs_"] = {}
    for line in rabbitmqs_services_iterator(options):
        # https://github.com/dokku/dokku-rabbitmq/issues/21 lists ports: mq_port cluster_resolution cluster_comms mgmt_port
        service_name, mq_port, cluster_resolution_port, cluster_comms_port, mgmt_port = line.strip().split(",")
        options["_rabbitmqs_"][service_name] = [mq_port, cluster_resolution_port, cluster_comms_port, mgmt_port ]
        print("...Creating RabbitMQ Service %s" % service_name)
        cmd = "ssh dokku@%s rabbitmq:create %s" % (get_deploy_host(options), service_name)
        try:
            err, out = execute_program_with_timeout(cmd)
            print(out)
            if len(err) > 0 and "already exists" not in err:
                print(err)
                return False
        except timeout_decorator.TimeoutError:
            pass  # bug in dokku rabbitmq https://github.com/dokku/dokku-rabbitmq/issues/34
        print("...Exposing RabbitMQ Ports")
        # expose web port etc https://github.com/dokku/dokku-rabbitmq/issues/21
        cmd = "ssh dokku@%s rabbitmq:expose %s %s %s %s %s" % (
            get_deploy_host(options), service_name, mq_port, cluster_resolution_port, cluster_comms_port, mgmt_port)
        err, out = execute_program(cmd)
        if len(err) > 0 and "already exposed" not in err:
            return False

@task
def dokku_create_redis_services(options):
    print("------------------------------------------------------------")
    print("REDIS SETUP")
    print("------------------------------------------------------------")
    if not platform_needs_redis_as_a_service(options):
        return
    for service_name in redis_services_iterator(options):
        cmd = "ssh dokku@%s redis:create %s" % (get_deploy_host(options), service_name)
        print("...Creating Redis Service %s: %s" % (service_name, cmd))
        err, out = execute_program(cmd)
        print(out)
        print(err)
        if len(err) > 0 and "not resolve host" in err:
            return False

@task
@needs(['dokku_create_empty_apps'])
def dokku_inject_rabbitmq_services(options):
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        dokku_inject_rabbitmq_service_if_needed(options, repo_url, app_name)

@task
@needs(['dokku_create_empty_apps'])
def dokku_inject_rabbitmq_services(options):
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        dokku_inject_rabbitmq_service_if_needed(options, repo_url, app_name)


def dokku_inject_rabbitmq_service_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_rabbitmq(options, original_app_name):
        return
    for service_name in rabbitmqs_services_needed_by_app_iterator(options, original_app_name):
        print("...Configuring RabbitMQ service %s for app %s" % (service_name, app_name))
        os.system("ssh dokku@%s rabbitmq:link %s %s" % (get_deploy_host(options), service_name, app_name))
        rabbitmq_config_json_path = rabbit_mq_initialization_file_path(options, original_app_name)
        if not os.path.exists(rabbitmq_config_json_path):
            continue
        rabbit_url_string = get_dokku_app_env_var_value(options, app_name, "RABBITMQ_URL")
        if len(rabbit_url_string) == 0:
            print("ERROR initializing %s with the contents of %s" % (rabbit_url_string, rabbitmq_config_json_path))
        print("Extracting password from %s" % rabbit_url_string)
        #rabbit_url = urlparse(rabbit_url_string)
        #password = rabbit_url.password
        password = rabbit_url_string.split(":")[2].split("@")[0]
        mq_port, cluster_resolution_port, cluster_comms_port, mgmt_port = options["_rabbitmqs_"][service_name]
        cmd = _RABBITMQ_SETUP_CMD % (service_name, password, rabbitmq_config_json_path, get_deploy_host(options), mgmt_port)
        print("Initializing queues: %s" % cmd)
        os.system(cmd)


def dokku_inject_redis_service_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_redis(options, original_app_name):
        return
    for service_name in redis_servicenames_iterator(options, original_app_name):
        cmd = "ssh dokku@%s redis:link %s %s" % (get_deploy_host(options), service_name, app_name)
        print("...Configuring Redis service %s for app %s: %s" % (service_name, app_name, cmd))
        os.system(cmd)
        #os.system("ssh dokku@%s redis:promote %s %s" % (get_deploy_host(options), service_name, app_name))

def get_dokku_app_host(options, app_name):
    return "%s.%s" % (app_name, get_expose_host(options))

def dokku_inject_requiremets_app(options, repo_url, app_name, app_names_by_repo_dir_name):
    requirements_app = "%s/requirements.app" % get_repo_full_path_for_repo_url(repo_url)
    for line in templated_file_lines_iterator(options, requirements_app):
        required_app_repo_dir_name = line.strip()
        required_app_name = app_names_by_repo_dir_name.get(required_app_repo_dir_name, None)
        if required_app_name is None:
            print("\n*** SEVERE WARNING: Configuring %s , "
                  "'%s' is listed as requirement but no app was deployed for this dir/git" %
                  (app_name, required_app_repo_dir_name))
            print(" \t Mapping: %s" % app_names_by_repo_dir_name)
            continue  # TO DO: Generate warmning? Halt teh deploy?
        required_app_url = "http://%s" % get_dokku_app_host(options, required_app_name)
        cmd = 'ssh dokku@%s config:set --no-restart %s %s_URL="%s"' % \
                (get_deploy_host(options),
                 app_name,
                 required_app_repo_dir_name.upper().replace("-", "_"),
                 required_app_url)
        print("...Configuring required app for %s: %s" % (app_name, cmd))
        os.system(cmd)

@task
@needs(['dokku_create_empty_apps', 'dokku_start_postgres'])
def dokku_create_configured_apps(options):
    app_names_by_repo_dir_name = {}
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        app_names_by_repo_dir_name[dir_name_for_repo(repo_url)] = app_name
        dokku_set_docker_options_if_needed(options, repo_url, app_name)
        dokku_create_database_if_needed(options, repo_url, app_name)
        dokku_create_mongo_if_needed(options, repo_url, app_name)
        dokku_inject_rabbitmq_service_if_needed(options, repo_url, app_name)
        dokku_inject_redis_service_if_needed(options, repo_url, app_name)
        dokku_create_apps_env_vars_if_needed(options, repo_url, app_name)  # env vars AFTER because some slam DATABASE_URL
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        dokku_inject_requiremets_app(options, repo_url, app_name, app_names_by_repo_dir_name)

@task
def dokku_just_deploy(options):
    progress = Progress()
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        repo_dir_name = dir_name_for_repo(repo_url)
        repo_full_path = "%s/%s" % (current_parent_path(), repo_dir_name)
        repo = git.Repo(repo_full_path)
        dokku_remote = repo.remote(get_dokku_remote_repo_name(options))
        ref_spec = "%s:%s" % (branch, "master")
        push_infos = dokku_remote.push(ref_spec, progress=progress)
        push_info = push_infos[0]
        print("Push result flags: %s (%s)" % (push_info.flags, push_info.summary))
        if push_info.flags & 16:  # remote push rejected
            # see # https://gitpython.readthedocs.org/en/0.3.3/reference.html#git.remote.PushInfo
            print("...Failed dokku push for %s (%s)" % (app_name, repo_dir_name))
            return False
        print("\r\n-------------------------------------------------------------\r\n")


def dokku_rm_database_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_database(options, original_app_name):
        return
    print("...Removing database for %s. Stopping app first" % app_name)
    os.system("ssh dokku@%s ps:stop %s" % (get_deploy_host(options), app_name))
    os.system("ssh dokku@%s psql:delete %s" % (get_deploy_host(options), app_name))
    # Just in case the step above fails, we shoot it hard, below.
    os.system('echo "drop database db_%s; \q" > drop.txt' % app_name.replace("-", "_"))
    os.system("ssh dokku@%s psql:admin_console < drop.txt" % (get_deploy_host(options)))


def dokku_rm_mongo_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_mongo(options, original_app_name):
        return
    print("...Removing mongo for %s" % app_name)
    os.system("echo %s > confirm.txt" % app_name)
    os.system("ssh dokku@%s mongo:destroy %s < confirm.txt" % (get_deploy_host(options), app_name))
    os.system("ssh dokku@%s mongo:unlink %s %s" % (get_deploy_host(options), app_name, app_name))


def dokku_rm_rabbitmq_services(options):
    for line in rabbitmqs_services_iterator(options):
        service_name, mq_port, cluster_resolution_port, mgmt_port, cluster_comms_port = line.strip().split(",")
        service_name = line.strip().split(",")[0]
        os.system("echo %s > confirm.txt" % service_name)
        print("...Removing RabbitMQ Service %s" % service_name)
        os.system("ssh dokku@%s rabbitmq:destroy %s < confirm.txt" % (get_deploy_host(options), service_name))

def dokku_rm_redis_services(options):
    for service_name in redis_services_iterator(options):
        os.system("echo %s > confirm.txt" % service_name)
        cmd = "ssh dokku@%s redis:destroy %s < confirm.txt" % (get_deploy_host(options), service_name)
        print("...Removing Redis Service %s: %s " % (service_name, cmd))
        os.system(cmd)

@task
@needs(['dokku_create_rabbitmq_services', 'dokku_create_redis_services', 'dokku_remote_git_add', 'dokku_create_configured_apps', 'dokku_just_deploy'])
def dokku_deploy(options):
    print(options)


@task
def dokku_undeploy(options):
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        dokku_rm_database_if_needed(options, repo_url, app_name)
        dokku_rm_mongo_if_needed(options, repo_url, app_name)
        os.system("echo %s > confirm.txt" % app_name)
        os.system("ssh dokku@%s apps:destroy %s < confirm.txt" % (get_deploy_host(options), app_name))
    dokku_rm_rabbitmq_services(options)
    dokku_rm_redis_services(options)


@task
@needs(['dokku_undeploy', 'git_rm_all'])
def dokku_clean():
    print("Cleaned dokku apps and git repos")
