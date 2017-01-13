from core import git_rm_all, app_has_database, app_has_mongo, \
    shared_services, execute_program_with_timeout, execute_program, \
    dir_name_for_repo, current_parent_path, git_clone_all, \
    repo_and_branch_and_app_name_iterator, get_remote_repo_name
import os
import timeout_decorator
import git

def clean(config_as_dict, **kwargs):
    undeploy(config_as_dict, **kwargs)
    git_rm_all(config_as_dict, **kwargs)


def deploy(config_as_dict, **kwargs):
    #@needs(['dokku_create_rabbitmq_services', 'dokku_create_redis_services', 'dokku_remote_git_add',
    #        'dokku_create_configured_apps', 'dokku_just_deploy'])
    git_clone_all(config_as_dict)
    dokku_remote_git_add(config_as_dict, **kwargs)
    dokku_create_rabbitmq_services(config_as_dict, **kwargs)
    dokku_create_redis_services(config_as_dict, **kwargs)


def undeploy(config_as_dict, **kwargs):
    for app_name, app_props in config_as_dict.get("apps", {}).items():
        dokku_rm_database_if_needed(config_as_dict, app_name, app_props, **kwargs)
        dokku_rm_mongo_if_needed(config_as_dict, app_name, app_props, **kwargs)
        os.system("echo %s > confirm.txt" % app_name)
        os.system("ssh dokku@%s apps:destroy %s < confirm.txt" % (kwargs.get("deployhost", "."), app_name))
    dokku_rm_rabbitmq_services(config_as_dict, **kwargs)
    dokku_rm_redis_services(config_as_dict, **kwargs)

# ----------------------------------------------------------------

def dokku_remote_git_add(config_as_dict, **kwargs):
    host = kwargs.get("deployhost", ".")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(config_as_dict):
        repo_dir_name = dir_name_for_repo(repo_url)
        repo_full_path = "%s/%s" % (current_parent_path(), repo_dir_name)
        repo = git.Repo(repo_full_path)
        dokku_remote = "dokku@%s:%s" % (host, app_name)
        dokku_remote_repo_name = get_remote_repo_name(**kwargs)
        remote_names = [remote.name for remote in repo.remotes]
        remote_urls = [remote.url for remote in repo.remotes]
        if dokku_remote in remote_urls:
            print("Already in remote: %s" % dokku_remote)
            continue
        if dokku_remote_repo_name in remote_names:
            repo.delete_remote(dokku_remote_repo_name)
        print("Adding remote '%s' for %s" % (dokku_remote_repo_name, dokku_remote))
        repo.create_remote(get_remote_repo_name(**kwargs), dokku_remote)


def dokku_rm_database_if_needed(config_as_dict, app_name, app_props, **kwargs):
    if not app_has_database(config_as_dict, app_name, app_props):
        return
    print("...Removing database for %s. Stopping app first" % app_name)
    os.system("ssh dokku@%s ps:stop %s" % (kwargs.get("deployhost", "."), app_name))
    os.system("ssh dokku@%s psql:delete %s" % (kwargs.get("deployhost", "."), app_name))
    # Just in case the step above fails, we shoot it hard, below.
    os.system('echo "drop database db_%s; \q" > drop.txt' % app_name.replace("-", "_"))
    os.system("ssh dokku@%s psql:admin_console < drop.txt" % (kwargs.get("deployhost", ".")))


def dokku_rm_mongo_if_needed(config_as_dict, app_name, app_props, **kwargs):
    if not app_has_mongo(config_as_dict, app_name, app_props):
        return
    print("...Removing mongo for %s" % app_name)
    os.system("echo %s > confirm.txt" % app_name)
    os.system("ssh dokku@%s mongo:destroy %s < confirm.txt" % (kwargs.get("deployhost", "."), app_name))
    os.system("ssh dokku@%s mongo:unlink %s %s" % (kwargs.get("deployhost", "."), app_name, app_name))


def dokku_rm_rabbitmq_services(config_as_dict, **kwargs):
    for service_name in shared_services("rabbitmq", config_as_dict):
        os.system("echo %s > confirm.txt" % service_name)
        print("...Removing RabbitMQ Service %s" % service_name)
        os.system("ssh dokku@%s rabbitmq:destroy %s < confirm.txt" % (kwargs.get("deployhost", "."), service_name))


def dokku_rm_redis_services(config_as_dict, **kwargs):
    for service_name in shared_services("redis", config_as_dict):
        os.system("echo %s > confirm.txt" % service_name)
        cmd = "ssh dokku@%s redis:destroy %s < confirm.txt" % (kwargs.get("deployhost", "."), service_name)
        print("...Removing Redis Service %s: %s " % (service_name, cmd))
        os.system(cmd)


def dokku_create_rabbitmq_services(config_as_dict, **kwargs):
    for service_name in shared_services("rabbitmq", config_as_dict):
        # https://github.com/dokku/dokku-rabbitmq/issues/21 lists ports: mq_port cluster_resolution cluster_comms mgmt_port
        print("...Creating RabbitMQ Service %s" % service_name)
        cmd = "ssh dokku@%s rabbitmq:create %s" % (kwargs.get("deployhost", "."), service_name)
        try:
            err, out = execute_program_with_timeout(cmd)
            print(out)
            if len(err) > 0 and "already exists" not in err:
                print(err)
                return False
        except timeout_decorator.TimeoutError:
            pass  # bug in dokku rabbitmq https://github.com/dokku/dokku-rabbitmq/issues/34
        # print("...Exposing RabbitMQ Ports")
        # # expose web port etc https://github.com/dokku/dokku-rabbitmq/issues/21
        # cmd = "ssh dokku@%s rabbitmq:expose %s %s %s %s %s" % (
        #     kwargs.get("deployhost", "."), service_name, mq_port, cluster_resolution_port, cluster_comms_port, mgmt_port)
        # err, out = execute_program(cmd)
        # if len(err) > 0 and "already exposed" not in err:
        #     return False

def dokku_create_redis_services(config_as_dict, **kwargs):
    for service_name in shared_services("redis", config_as_dict):
        cmd = "ssh dokku@%s redis:create %s" % (kwargs.get("deployhost", "."), service_name)
        print("...Creating Redis Service %s: %s" % (service_name, cmd))
        err, out = execute_program(cmd)
        print(out)
        print(err)
        if len(err) > 0 and "not resolve host" in err:
            raise EnvironmentError("Could not configure Redis service %s: %s" % (service_name, err))
