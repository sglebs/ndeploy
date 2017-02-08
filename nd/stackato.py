import os
import re

# See http://docs.stackato.com/user/reference/client-ref.html

from nd.core import git_rm_all, app_has_database, \
    execute_program, \
    dir_name_for_repo, git_clone_all, get_area_name, \
    get_http_repo_url, \
    execute_program_and_print_output, get_repo_full_path_for_repo_dir_name, \
    repo_and_branch_and_app_name_and_app_props_iterator, \
    get_repo_full_path_for_repo_url, \
    procfile_iterator, shared_services, app_shared_services


def process_args(config_as_dict):
    return config_as_dict

def clean(config_as_dict):
    undeploy(config_as_dict)
    git_rm_all(config_as_dict)


def undeploy(config_as_dict):
    stackato_login(config_as_dict)
    for repo_url, branch, app_name, app_props in reversed(list(repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict))):
        for label, cmd_line in procfile_iterator(config_as_dict, dir_name_for_repo(repo_url)):
            if label == "web":
                label = ""  # default label, should not be used as suffix
            print("Removing app %s%s" % (app_name, label))
            os.system("%s delete all -l app=%s%s" % (get_cli_command(config_as_dict),app_name, label))
            #stackato_rm_database_if_needed(config_as_dict, repo_url, app_name, app_props)
    #    openshift_rm_mongo_if_needed(config_as_dict, repo_url, app_name)
    #openshift_rm_rabbitmq_if_needed(config_as_dict)


def deploy(config_as_dict):
    git_clone_all(config_as_dict)
    stackato_login(config_as_dict)
    stackato_create_project_area(config_as_dict)
    stackato_create_empty_apps(config_as_dict)
    stackato_create_redis_services(config_as_dict)
    stackato_configure_created_apps(config_as_dict)
    stackato_deploy_apps(config_as_dict)

# ------------------------------------------------------------

def stackato_create_empty_apps(config_as_dict):
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        cmd = '{cli} -n create-app {appname} '.format(cli=get_cli_command(config_as_dict),
                                                    appname=app_name,
                                                    repourl=get_http_repo_url(repo_url),
                                                    branch=branch,
                                                    repofullpath=get_repo_full_path_for_repo_url(repo_url, config_as_dict))
        print("Creating app %s: %s \n\n" % (app_name, cmd))
        execute_program_and_print_output(cmd, dir_where_to_run=get_repo_full_path_for_repo_dir_name(
            dir_name_for_repo(repo_url), config_as_dict))

def stackato_create_project_area(config_as_dict):
    cmd = "%s create-space %s" % (get_cli_command(config_as_dict), get_area_name(config_as_dict))
    print ("Creating prj area: %s" % cmd)
    os.system(cmd)


def get_cli_command(config_as_dict):
    return "%s/stackato" % config_as_dict["cli_dir"]


def stackato_login(config_as_dict):
    cmd = "%s target https://api.%s" % (get_cli_command(config_as_dict), config_as_dict.get("deployhost", "."))
    err, out = execute_program(cmd)
    print(out)
    print(err)
    if "<none>" in out or "<none>" in err: # undefined area etc
        cmd = "%s login" % (get_cli_command(config_as_dict))
        execute_program_and_print_output(cmd)


def stackato_deploy_apps(config_as_dict):
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        buildpack_url = app_props["envs"].get("BUILDPACK_URL", "") if "envs" in app_props else ""
        if len (buildpack_url) > 0:
            buildpack_cmdline = " --buildpack=%s " % buildpack_url
        else:
            buildpack_cmdline = ""
        repo_full_path = get_repo_full_path_for_repo_dir_name(dir_name_for_repo(repo_url), config_as_dict)
        cmd = "%s push -n --as %s %s --path=%s" % (get_cli_command(config_as_dict), app_name, buildpack_cmdline, repo_full_path)
        print("Pushing code: %s" % cmd)
        os.system(cmd)
        cmd = "%s start %s" % (get_cli_command(config_as_dict), app_name)
        print("Starting app: %s" % cmd)
        os.system(cmd)

def stackato_configure_created_apps(config_as_dict):
    app_names_by_repo_dir_name = {}
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        app_names_by_repo_dir_name[dir_name_for_repo(repo_url)] = app_name
        stackato_create_apps_env_vars_if_needed(config_as_dict, app_name, app_props)  # env vars AFTER because some slam DATABASE_URL
        stackato_inject_redis_service_if_needed(config_as_dict, app_name, app_props)
        #stackato_configure_domains(config_as_dict, app_name, app_props)

def stackato_create_apps_env_vars_if_needed(config_as_dict, app_name, app_props):
    if "envs" in app_props:
        print("Configuring env vars for %s" % app_name)
        for key, value in app_props["envs"].items():
            cmd = "%s env-add %s %s \"%s\" " % (get_cli_command(config_as_dict), app_name, key, value)
            print(cmd)
            os.system(cmd)
    else:
        print("WARNING: NO ENV VARS for %s" % app_name)

def stackato_create_redis_services(config_as_dict):
    for service_name in shared_services("redis", config_as_dict):
        cmd = "%s create-service redis %s" % (get_cli_command(config_as_dict), service_name)
        print("...Creating Redis Service %s: %s" % (service_name, cmd))
        os.system(cmd)

def stackato_inject_redis_service_if_needed(config_as_dict, app_name, app_props):
    for service_name in app_shared_services("redis", config_as_dict, app_name, app_props):
        cmd = "%s bind-service %s %s" % (get_cli_command(config_as_dict), service_name, app_name)
        print("...Injecting Redis service %s into app %s: %s" % (service_name, app_name, cmd))
        err, out = execute_program(cmd)
        print(err)
        print(out)
        if "Setting config vars" not in out:
            raise EnvironmentError("Could not configure Redis (link it to app %s): %s" % (app_name, err))
        #TODO: get URL of service and make it publicly available
        url_regex = "redis://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        urls = re.findall(url_regex, out)
        injected_redis_url = urls[0]
        print("...URLing Redis service %s with url %s in an env var" % (service_name, injected_redis_url))
        cmd = "%s env-add %s %s_URL \"%s\" " % (get_cli_command(config_as_dict), app_name, service_name.upper().replace("-", "_"), injected_redis_url)
        os.system(cmd)
