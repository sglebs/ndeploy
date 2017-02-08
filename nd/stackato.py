import os
import timeout_decorator

from nd.core import git_rm_all, app_has_database, \
    execute_program_with_timeout, execute_program, \
    dir_name_for_repo, git_clone_all, get_area_name, \
    repo_and_branch_and_app_name_iterator, get_http_repo_url, \
    execute_program_and_print_output, get_repo_full_path_for_repo_dir_name, \
    repo_and_branch_and_app_name_and_app_props_iterator, \
    get_repo_full_path_for_repo_url, templated_file_lines_iterator, \
    templated_file_contents, procfile_iterator, app_has_dockerfile


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
    #stackato_configure_created_apps(config_as_dict)
    stackato_deploy_apps(config_as_dict)

# ------------------------------------------------------------

def stackato_create_empty_apps(config_as_dict):
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        for label, cmd_line in procfile_iterator(config_as_dict,dir_name_for_repo(repo_url)):
            suffix_from_label = label
            if label == "web":
                suffix_from_label = ""  # default label, should not be used as suffix
            cmd = '{cli} -n create-app {appname}{suffixfromlabel} '.format(cli=get_cli_command(config_as_dict),
                                                        appname=app_name,
                                                        repourl=get_http_repo_url(repo_url),
                                                        branch=branch,
                                                        repofullpath=get_repo_full_path_for_repo_url(repo_url, config_as_dict),
                                                        suffixfromlabel=suffix_from_label,
                                                        procfilelabel=label,
                                                        cmdline=cmd_line)
            print("Creating app %s:%s: %s \n\n" % (app_name, label, cmd))
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
    if "<none>" in out or "<none>" in err: # undefined area etc
        cmd = "%s login" % (get_cli_command(config_as_dict))
        execute_program_and_print_output(cmd)
    print (out)
    print (err)


def stackato_deploy_apps(config_as_dict):
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(config_as_dict):
        for label, cmd_line in procfile_iterator(config_as_dict,dir_name_for_repo(repo_url)):
            suffix_from_label = label
            if label == "web":
                suffix_from_label = ""  # default label, should not be used as suffix
            cmd = "%s push -n %s%s" % (get_cli_command(config_as_dict), app_name, suffix_from_label)
            print ("Pushing code: %s" % cmd)
            execute_program_and_print_output(cmd, dir_where_to_run=get_repo_full_path_for_repo_dir_name(
                dir_name_for_repo(repo_url), config_as_dict))