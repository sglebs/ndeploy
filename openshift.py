from core import git_rm_all, app_has_database, app_has_mongo, \
    shared_services, execute_program_with_timeout, execute_program, \
    dir_name_for_repo, current_parent_path, git_clone_all, \
    repo_and_branch_and_app_name_iterator, get_remote_repo_name, \
    execute_program_and_print_output, Progress, \
    repo_and_branch_and_app_name_and_app_props_iterator, docker_options_iterator, \
    app_shared_services, get_repo_full_path_for_repo_url, templated_file_lines_iterator, \
    templated_file_contents, procfile_iterator
import os
import timeout_decorator
import git
import re
import getpass
import socket


def clean(config_as_dict):
    undeploy(config_as_dict)
    git_rm_all(config_as_dict)


def undeploy(config_as_dict):
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        for label, cmd_line in procfile_iterator(config_as_dict, dir_name_for_repo(repo_url)):
            if label == "web":
                label = ""  # default label, should not be used as suffix
            print("...Removing app %s%s" % (app_name, label))
            os.system("oc delete all -l app=%s%s" % (app_name, label))
        openshift_rm_database_if_needed(config_as_dict, repo_url, app_name, app_props)
    #    openshift_rm_mongo_if_needed(config_as_dict, repo_url, app_name)
    #openshift_rm_rabbitmq_if_needed(config_as_dict)

def get_openshift_area_name(config_as_dict):
    default = getpass.getuser()
    return config_as_dict.get("area", default).replace(".", "")


def get_openshift_template_contents(config_as_dict, openshift_template_path):
    return templated_file_contents(config_as_dict, openshift_template_path).strip()


def get_http_repo_url(repo_url):
    adapted_repo_url = repo_url.replace(":", "/").replace("git@", "https://") if repo_url.startswith(
        "git") else repo_url
    return adapted_repo_url


def get_openshift_short_app_name(app_name):
    return app_name[:20]


def get_openshift_db_name_from_app_name(app_name):
    return get_openshift_short_app_name(app_name).replace("-", "_")


def openshift_login(config_as_dict):
    cmd = "oc whoami"
    needs_login = True
    while needs_login:
        try:
            err, out = execute_program_with_timeout(cmd)
            print(err)
            print(out)
            if "system:anonymous" in err or "provide credentials" in err:
                needs_login = True
            else:
                needs_login = False
        except timeout_decorator.TimeoutError:
            needs_login = True
        if needs_login:
            # login has to be by IP because of teh https/ssl signed certificate
            ip = socket.gethostbyname(config_as_dict.get("deployhost", "."))
            os.system("oc login https://%s:8443" % ip)


def openshift_rm_database_if_needed(config_as_dict, repo_url, app_name, app_props):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_database(config_as_dict, original_app_name, app_props):
        return
    print("...Removing database for %s." % app_name)
    cmd = "oc delete all -l app=pg-%s" % get_openshift_short_app_name(app_name)
    ok = execute_program_and_print_output(cmd)
    if not ok:
        return False #FIXME : exceptions?