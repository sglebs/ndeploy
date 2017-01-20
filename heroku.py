from core import git_rm_all, remote_git_add, app_has_database, deploy_via_git_push, \
    shared_services, execute_program, dir_name_for_repo, \
    git_clone_all, \
    repo_and_branch_and_app_name_iterator, \
    execute_program_and_print_output, \
    repo_and_branch_and_app_name_and_app_props_iterator
import os


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
    #heroku_create_redis_services(config_as_dict)
    #heroku_configure_apps(config_as_dict)
    deploy_via_git_push(config_as_dict)

# ------------------------------------------------------------


def get_cli_command(config_as_dict):
    return "%s/heroku" % config_as_dict["cli_dir"]


def heroku_remote_git_add(config_as_dict):
    remote_git_add(config_as_dict, "https://{host}/{app_name}.git", "git.heroku.com")


def heroku_create_empty_apps(config_as_dict):
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(config_as_dict):
        cmd = "%s apps:create %s" % (get_cli_command(config_as_dict), app_name)
        err, out = execute_program(cmd)
        if len(err) > 0 and 'already taken' not in err:  # some other error
            print(err)
            return False
        else:
            print(out)


def heroku_create_databases(config_as_dict):
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        if not app_has_database(config_as_dict, app_name, app_props):
            continue
        print("...Configuring database for %s" % app_name)
        cmd = "%s addons:create heroku-postgresql:hobby-dev -a %s" % (get_cli_command(config_as_dict), app_name)
        ok = execute_program_and_print_output(cmd)
        if not ok:
            return False


def heroku_create_redis_services(config_as_dict):
    for service_name in shared_services("redis", config_as_dict):
        cmd = "%s addons:create heroku-redis:hobby-dev %s" % (get_cli_command(config_as_dict), service_name)
        print("...Creating Redis Service %s: %s" % (service_name, cmd))
        err, out = execute_program(cmd)
        print(out)
        print(err)
        if len(err) > 0 and "not resolve host" in err:
            raise EnvironmentError("Could not configure Redis service %s: %s" % (service_name, err))

def heroku_configure_apps(config_as_dict):
    app_names_by_repo_dir_name = {}
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        app_names_by_repo_dir_name[dir_name_for_repo(repo_url)] = app_name
        #dokku_inject_redis_service_if_needed(config_as_dict, app_name, app_props)
        #dokku_create_apps_env_vars_if_needed(config_as_dict, app_name, app_props)  # env vars AFTER because some slam DATABASE_URL
        heroku_configure_domains(config_as_dict, app_name, app_props)

def heroku_configure_domains(config_as_dict, app_name, app_props):
    if not "domains" in app_props:
        return
    for domain_name in app_props["domains"]:
        cmd = "%s domains:add %s -a %s" % (get_cli_command(config_as_dict), domain_name, app_name)
        print("...Configuring domain name %s for app %s" % (domain_name, app_name))
        os.system(cmd)
