import os
import re

import timeout_decorator

from core import git_rm_all, remote_git_add, app_has_database, app_has_mongo, \
    shared_services, execute_program_with_timeout, execute_program, \
    dir_name_for_repo, git_clone_all, \
    repo_and_branch_and_app_name_iterator, execute_program_and_print_output, \
    repo_and_branch_and_app_name_and_app_props_iterator, docker_options_iterator, \
    app_shared_services, get_repo_full_path_for_repo_url, templated_file_lines_iterator, deploy_via_git_push

def process_args(args_as_dict):
    return args_as_dict

def clean(config_as_dict):
    undeploy(config_as_dict)
    git_rm_all(config_as_dict)


def deploy(config_as_dict):
    git_clone_all(config_as_dict)
    dokku_remote_git_add(config_as_dict)
    dokku_create_empty_apps(config_as_dict)
    dokku_start_postgres(config_as_dict)
    dokku_create_databases(config_as_dict)
    dokku_create_rabbitmq_services(config_as_dict)
    dokku_create_redis_services(config_as_dict)
    dokku_configure_apps(config_as_dict)
    deploy_via_git_push(config_as_dict)

def undeploy(config_as_dict):
    for repo, branch, app_name, app_props in reversed(list(repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict))):
        dokku_rm_database_if_needed(config_as_dict, app_name, app_props)
        dokku_rm_mongo_if_needed(config_as_dict, app_name, app_props)
        os.system("echo %s > confirm.txt" % app_name)
        os.system("ssh dokku@%s apps:destroy %s < confirm.txt" % (config_as_dict.get("deployhost", "."), app_name))
    dokku_rm_rabbitmq_services(config_as_dict)
    dokku_rm_redis_services(config_as_dict)

# ----------------------------------------------------------------

def dokku_remote_git_add(config_as_dict):
    remote_git_add(config_as_dict, "dokku@{host}:{app_name}", config_as_dict.get("deployhost", "."))


def dokku_rm_database_if_needed(config_as_dict, app_name, app_props):
    if not app_has_database(config_as_dict, app_name, app_props):
        return
    print("...Removing database for %s. Stopping app first" % app_name)
    os.system("ssh dokku@%s ps:stop %s" % (config_as_dict.get("deployhost", "."), app_name))
    os.system("ssh dokku@%s psql:delete %s" % (config_as_dict.get("deployhost", "."), app_name))
    # Just in case the step above fails, we shoot it hard, below.
    os.system('echo "drop database db_%s; \q" > drop.txt' % app_name.replace("-", "_"))
    os.system("ssh dokku@%s psql:admin_console < drop.txt" % (config_as_dict.get("deployhost", ".")))


def dokku_rm_mongo_if_needed(config_as_dict, app_name, app_props):
    if not app_has_mongo(config_as_dict, app_name, app_props):
        return
    print("...Removing mongo for %s" % app_name)
    os.system("echo %s > confirm.txt" % app_name)
    os.system("ssh dokku@%s mongo:destroy %s < confirm.txt" % (config_as_dict.get("deployhost", "."), app_name))
    os.system("ssh dokku@%s mongo:unlink %s %s" % (config_as_dict.get("deployhost", "."), app_name, app_name))


def dokku_rm_rabbitmq_services(config_as_dict):
    for service_name in shared_services("rabbitmq", config_as_dict):
        os.system("echo %s > confirm.txt" % service_name)
        print("...Removing RabbitMQ Service %s" % service_name)
        os.system("ssh dokku@%s rabbitmq:destroy %s < confirm.txt" % (config_as_dict.get("deployhost", "."), service_name))


def dokku_rm_redis_services(config_as_dict):
    for service_name in shared_services("redis", config_as_dict):
        os.system("echo %s > confirm.txt" % service_name)
        cmd = "ssh dokku@%s redis:destroy %s < confirm.txt" % (config_as_dict.get("deployhost", "."), service_name)
        print("...Removing Redis Service %s: %s " % (service_name, cmd))
        os.system(cmd)


def dokku_create_rabbitmq_services(config_as_dict):
    for service_name in shared_services("rabbitmq", config_as_dict):
        # https://github.com/dokku/dokku-rabbitmq/issues/21 lists ports: mq_port cluster_resolution cluster_comms mgmt_port
        print("...Creating RabbitMQ Service %s" % service_name)
        cmd = "ssh dokku@%s rabbitmq:create %s" % (config_as_dict.get("deployhost", "."), service_name)
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

def dokku_create_redis_services(config_as_dict):
    for service_name in shared_services("redis", config_as_dict):
        cmd = "ssh dokku@%s redis:create %s" % (config_as_dict.get("deployhost", "."), service_name)
        print("...Creating Redis Service %s: %s" % (service_name, cmd))
        err, out = execute_program(cmd)
        print(out)
        print(err)
        if len(err) > 0 and "not resolve host" in err:
            raise EnvironmentError("Could not configure Redis service %s: %s" % (service_name, err))

def dokku_create_empty_apps(config_as_dict):
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(config_as_dict):
        cmd = "ssh dokku@%s apps:create %s" % (config_as_dict.get("deployhost", "."), app_name)
        err, out = execute_program(cmd)
        if len(err) > 0 and 'already taken' not in err:  # some other error
            print(err)
            return False
        else:
            print(out)


def dokku_start_postgres(config_as_dict):
    cmd = "ssh dokku@%s psql:start" % (config_as_dict.get("deployhost", "."))
    print("...Starting database service:  %s" % cmd)
    execute_program_and_print_output(cmd)


def dokku_create_databases(config_as_dict):
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        if not app_has_database(config_as_dict, app_name, app_props):
            continue
        print("...Configuring database for %s" % app_name)
        cmd = "ssh dokku@%s psql:create %s" % (config_as_dict.get("deployhost", "."), app_name)
        ok = execute_program_and_print_output(cmd)
        if not ok:
            return False


def dokku_configure_apps(config_as_dict):
    app_names_by_repo_dir_name = {}
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        app_names_by_repo_dir_name[dir_name_for_repo(repo_url)] = app_name
        dokku_set_docker_options_if_needed(app_name, app_props, config_as_dict)
        #dokku_inject_rabbitmq_service_if_needed(config_as_dict, repo_url, app_name)
        dokku_inject_redis_service_if_needed(config_as_dict, app_name, app_props)
        dokku_create_apps_env_vars_if_needed(config_as_dict, app_name, app_props)  # env vars AFTER because some slam DATABASE_URL
        dokku_configure_domains(config_as_dict, app_name, app_props)
    # for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
    #     dokku_inject_requiremets_app(config_as_dict, app_name, app_props, repo_url, app_names_by_repo_dir_name)

def dokku_inject_redis_service_if_needed(config_as_dict, app_name, app_props):
    for service_name in app_shared_services("redis", config_as_dict, app_name, app_props):
        cmd = "ssh dokku@%s redis:link %s %s" % (config_as_dict.get("deployhost", "."), service_name, app_name)
        print("...Injecting Redis service %s into app %s: %s" % (service_name, app_name, cmd))
        err, out = execute_program(cmd)
        if len(err) > 0:
            print(err)
            raise EnvironmentError("Could not configure Redis (link it to app %s): %s" % (app_name, err))
        else:
            print(out)
        #TODO: get URL of service and make it publicly available
        url_regex = "redis://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        urls = re.findall(url_regex, out)
        injected_redis_url = urls[0]
        print("...URLing Redis service %s with url %s in an env var" % (service_name, injected_redis_url))
        cmd = 'ssh dokku@%s config:set --no-restart %s %s_URL="%s"' % \
                (config_as_dict.get("deployhost", "."),
                 app_name,
                 service_name.upper().replace("-", "_"),
                 injected_redis_url)
        os.system(cmd)
        #os.system("ssh dokku@%s redis:promote %s %s" % (get_deploy_host(options), service_name, app_name))

def dokku_create_apps_env_vars_if_needed(config_as_dict, app_name, app_props):
    if "envs" in app_props:
        print("...Configuring env vars for %s" % app_name)
        key_values = ['%s="%s"' % (key, str(value).replace(" ", "\\ ").replace('"', '\\"')) for key, value in
                      app_props["envs"].items()]
        all_vars = " ".join(key_values)
        cmd = "ssh dokku@%s config:set --no-restart %s %s" % (config_as_dict.get("deployhost", "."), app_name, all_vars)
        print(cmd)
        os.system(cmd)
    else:
        print("WARNING: NO ENV VARS for %s" % app_name)

def dokku_configure_domains(config_as_dict, app_name, app_props):
    if not "domains" in app_props:
        return
    domains = " ".join(app_props["domains"])
    cmd = "ssh dokku@%s domains:add %s %s" % (config_as_dict.get("deployhost", "."), app_name, domains)
    print("...Configuring domain names for app %s: %s" % (app_name, cmd))
    os.system(cmd)
    #now ssl
    os.system("openssl genrsa -out server.key 2048")
    for domain_name in app_props["domains"]:
        os.system("openssl req -new -x509 -key server.key -out server.crt -days 3650 -subj /CN=%s" % domain_name)
        os.system("tar cvf server.tar server.crt server.key")
        cmd = "ssh dokku@%s certs:add %s < %s" % (config_as_dict.get("deployhost", "."), app_name, "server.tar")
        print("...Configuring https for domain %s: %s" % (domain_name, cmd))
        os.system(cmd)

def get_dokku_app_host(config_as_dict, app_name):
    return "%s.%s" % (app_name, config_as_dict.get("exposehost", "."))

# def dokku_inject_requiremets_app(config_as_dict, app_name, app_props, repo_url, app_names_by_repo_dir_name):
#     requirements_app = "%s/requirements.app" % get_repo_full_path_for_repo_url(repo_url)
#     for line in templated_file_lines_iterator(config_as_dict, requirements_app):
#         required_app_repo_dir_name = line.strip()
#         required_app_name = app_names_by_repo_dir_name.get(required_app_repo_dir_name, None)
#         if required_app_name is None:
#             print("\n*** SEVERE WARNING: Configuring %s , "
#                   "'%s' is listed as requirement but no app was deployed for this dir/git" %
#                   (app_name, required_app_repo_dir_name))
#             print(" \t Mapping: %s" % app_names_by_repo_dir_name)
#             continue  # TO DO: Generate warmning? Halt teh deploy?
#         required_app_url = "http://%s" % get_dokku_app_host(config_as_dict, required_app_name)
#         cmd = 'ssh dokku@%s config:set --no-restart %s %s_URL="%s"' % \
#                 (config_as_dict.get("deployhost", "."),
#                  app_name,
#                  required_app_repo_dir_name.upper().replace("-", "_"),
#                  required_app_url)
#         print("...Configuring required app for %s: %s" % (app_name, cmd))
#         os.system(cmd)

def dokku_set_docker_options_if_needed(app_name, app_props, config_as_dict):
    for phase, phase_options in docker_options_iterator(app_props):
        cmd = 'ssh dokku@%s docker-options:add %s %s "%s"' % (
            config_as_dict.get("deployhost", "."), app_name, phase, phase_options)
        print(cmd)
        os.system(cmd)

