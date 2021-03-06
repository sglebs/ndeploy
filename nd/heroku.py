import os
import re
from time import sleep

from nd.core import git_rm_all, remote_git_add, app_has_database, app_shared_services, app_has_redis, dir_name_for_repo, execute_program, \
    git_clone_all, apps_with_given_shared_service, get_repo_full_path_for_repo_dir_name, \
    repo_and_branch_and_app_name_iterator, GitProgress, \
    execute_program_and_print_output, deploy_single_app_via_git_push, \
    repo_and_branch_and_app_name_and_app_props_iterator, app_has_dockerfile, procfile_iterator, app_has_procfile


def process_args(config_as_dict):
    config_as_dict["exposehost"] = "herokuapp.com"  # override regardless of what was passed
    config_as_dict["deployhost"] = "git.heroku.com"  # override regardless of what was passed
    return config_as_dict

def clean(config_as_dict):
    undeploy(config_as_dict)
    git_rm_all(config_as_dict)


def undeploy(config_as_dict):
    for repo, branch, app_name, app_props in reversed(list(repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict))):
        os.system("%s apps:destroy %s --confirm %s" % (get_cli_command(config_as_dict), app_name, app_name))


def deploy(config_as_dict):
    git_clone_all(config_as_dict)
    heroku_remote_git_add(config_as_dict)
    heroku_create_empty_apps(config_as_dict)
    heroku_create_databases(config_as_dict)
    heroku_create_redis(config_as_dict)
    heroku_configure_apps(config_as_dict)
    heroku_deploy_apps(config_as_dict)

# ------------------------------------------------------------


def get_cli_command(config_as_dict):
    return "%s/heroku" % config_as_dict["cli_dir"]


def heroku_remote_git_add(config_as_dict):
    remote_git_add(config_as_dict, "https://{host}/{app_name}.git", config_as_dict.get("deployhost", "."))


def heroku_create_empty_apps(config_as_dict):
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(config_as_dict):
        cmd = "%s apps:create %s" % (get_cli_command(config_as_dict), app_name)
        ok = execute_program_and_print_output(cmd)



def heroku_create_databases(config_as_dict):
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        if not app_has_database(config_as_dict, app_name, app_props):
            continue
        print("Configuring database for %s" % app_name)
        cmd = "%s addons:create heroku-postgresql:hobby-dev -a %s" % (get_cli_command(config_as_dict), app_name)
        ok = execute_program_and_print_output(cmd)

def heroku_create_redis(config_as_dict):
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        if not app_has_redis(config_as_dict, app_name, app_props):
            continue
        print("Configuring redis for %s" % app_name)
        cmd = "%s addons:create heroku-redis:hobby-dev -a %s" % (get_cli_command(config_as_dict), app_name)
        err, out = execute_program(cmd)
        print(out)
        print(err)
        cmd = "%s redis:info -a %s" % (get_cli_command(config_as_dict), app_name)
        redis_name_and_env_var_regex = r'===\s+(\S+)\s+[(]([^)]+)[)]'
        redis_name = ""
        redis_env_var = None
        while redis_env_var is None:
            sleep(1)
            err, out = execute_program(cmd)
            if "creating" in out:
                continue # wait some more
            #=== redis-encircled-10074 (REDIS_URL)
            redis_name_and_env_var = re.findall(redis_name_and_env_var_regex, out)
            if len(redis_name_and_env_var) < 1:
                continue # wait some more (env var not created yet)
            if len(redis_name_and_env_var[0]) <= 1:
                continue # wait some more (env var not created yet)
            redis_name = redis_name_and_env_var[0][0]
            redis_env_var = redis_name_and_env_var[0][1]
        cmd = "%s config:get %s -a %s" % (get_cli_command(config_as_dict), redis_env_var, app_name)
        err, redis_env_var_value = execute_program(cmd)
        print("Created redis %s as env var %s in app %s with value %s" % (redis_name, redis_env_var, app_name, redis_env_var_value))
        app_shared_redis = list(app_shared_services("redis", config_as_dict, app_name, app_props))
        if len(app_shared_redis) == 1: # we own it, so we need to propagate this env var
            redis_url_key_name = "%s_URL" % app_shared_redis[0].upper().replace("-", "_")
            #redis_env_var_value
            for dependent_app in apps_with_given_shared_service("redis", config_as_dict, app_shared_redis[0]):
                if dependent_app != app_name: # we can safely skip ourselves
                    print("Injecting redis env var %s in dependent app %s with value %s" % (redis_url_key_name, dependent_app, redis_env_var_value))
                    cmd = "%s config:set %s=%s -a %s" % (get_cli_command(config_as_dict), redis_url_key_name, redis_env_var_value, dependent_app)
                    ok = execute_program_and_print_output(cmd)


def heroku_configure_apps(config_as_dict):
    app_names_by_repo_dir_name = {}
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        app_names_by_repo_dir_name[dir_name_for_repo(repo_url)] = app_name
        heroku_create_apps_env_vars_if_needed(config_as_dict, app_name, app_props)  # env vars AFTER because some slam DATABASE_URL
        heroku_configure_domains(config_as_dict, app_name, app_props)


def heroku_configure_domains(config_as_dict, app_name, app_props):
    if not "domains" in app_props:
        return
    for domain_name in app_props["domains"]:
        cmd = "%s domains:add %s -a %s" % (get_cli_command(config_as_dict), domain_name, app_name)
        print("...Configuring domain name %s for app %s" % (domain_name, app_name))
        ok = execute_program_and_print_output(cmd)


def heroku_create_apps_env_vars_if_needed(config_as_dict, app_name, app_props):
    if "envs" in app_props:
        print("Configuring env vars for %s" % app_name)
        key_values = ['%s="%s"' % (key, str(value).replace(" ", "\\ ").replace('"', '\\"')) for key, value in
                      app_props["envs"].items()]
        all_vars = " ".join(key_values)
        cmd = "%s config:set -a %s %s" % (get_cli_command(config_as_dict), app_name, all_vars)
        print(cmd)
        os.system(cmd)
    else:
        print("WARNING: NO ENV VARS for %s" % app_name)

def heroku_deploy_apps (config_as_dict):
    git_progress = GitProgress()
    performed_container_login = False
    strategy = config_as_dict.get("strategy")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(config_as_dict):
        if app_has_dockerfile(config_as_dict, dir_name_for_repo(repo_url)) and \
                app_has_procfile(config_as_dict, dir_name_for_repo(repo_url)) and \
                (strategy == "auto" or strategy == "docker"):
            if not performed_container_login:
                cmd = "%s container:login" % (get_cli_command(config_as_dict))
                print(cmd)
                os.system(cmd)
                performed_container_login = True
            for label, cmd_line in procfile_iterator(config_as_dict, dir_name_for_repo(repo_url)):
                cmd = "%s container:push -a %s %s" % (get_cli_command(config_as_dict), app_name, label)
                print(cmd)
                execute_program_and_print_output(cmd, dir_where_to_run=get_repo_full_path_for_repo_dir_name(dir_name_for_repo(repo_url), config_as_dict))
        else:
            deploy_single_app_via_git_push(app_name, branch, config_as_dict, git_progress, repo_url)
