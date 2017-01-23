from core import git_rm_all, remote_git_add, app_has_database, deploy_via_git_push, \
    shared_services, app_has_redis, dir_name_for_repo, execute_program, \
    git_clone_all, \
    repo_and_branch_and_app_name_iterator, \
    execute_program_and_print_output, \
    repo_and_branch_and_app_name_and_app_props_iterator
import os
from time import sleep
import re

def process_args(args_as_dict):
    args_as_dict["exposehost"] = "herokuapps.com"  # override regardless of what was passed
    args_as_dict["deployhost"] = "git.heroku.com"  # override regardless of what was passed
    return args_as_dict

def clean(config_as_dict):
    undeploy(config_as_dict)
    git_rm_all(config_as_dict)


def undeploy(config_as_dict):
    for app_name, app_props in config_as_dict.get("apps", {}).items():
        os.system("echo %s > confirm.txt" % app_name)
        os.system("%s apps:destroy %s < confirm.txt" % (get_cli_command(config_as_dict), app_name))


def deploy(config_as_dict):
    git_clone_all(config_as_dict)
    heroku_remote_git_add(config_as_dict)
    heroku_create_empty_apps(config_as_dict)
    heroku_create_databases(config_as_dict)
    heroku_create_redis(config_as_dict)
    heroku_configure_apps(config_as_dict)
    deploy_via_git_push(config_as_dict)

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
        created = False
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
        print("Created redis %s as env var %s in app %s" % (redis_name, redis_env_var, app_name))


def heroku_configure_apps(config_as_dict):
    app_names_by_repo_dir_name = {}
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        app_names_by_repo_dir_name[dir_name_for_repo(repo_url)] = app_name
        #dokku_inject_redis_service_if_needed(config_as_dict, app_name, app_props)
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