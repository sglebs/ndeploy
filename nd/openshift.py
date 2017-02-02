import getpass
import os
import socket

import timeout_decorator

from nd.core import git_rm_all, app_has_database, \
    execute_program_with_timeout, execute_program, \
    dir_name_for_repo, git_clone_all, \
    repo_and_branch_and_app_name_iterator, \
    execute_program_and_print_output, \
    repo_and_branch_and_app_name_and_app_props_iterator, \
    get_repo_full_path_for_repo_url, templated_file_lines_iterator, \
    templated_file_contents, procfile_iterator


def process_args(args_as_dict):
    return args_as_dict

def clean(config_as_dict):
    undeploy(config_as_dict)
    git_rm_all(config_as_dict)


def undeploy(config_as_dict):
    openshift_login(config_as_dict)
    for repo_url, branch, app_name, app_props in reversed(list(repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict))):
        for label, cmd_line in procfile_iterator(config_as_dict, dir_name_for_repo(repo_url)):
            if label == "web":
                label = ""  # default label, should not be used as suffix
            print("Removing app %s%s" % (app_name, label))
            os.system("%s delete all -l app=%s%s" % (get_cli_command(config_as_dict),app_name, label))
        openshift_rm_database_if_needed(config_as_dict, repo_url, app_name, app_props)
    #    openshift_rm_mongo_if_needed(config_as_dict, repo_url, app_name)
    #openshift_rm_rabbitmq_if_needed(config_as_dict)

def deploy(config_as_dict):
    git_clone_all(config_as_dict)
    openshift_login(config_as_dict)
    openshift_create_project_area(config_as_dict)
    openshift_create_empty_apps(config_as_dict)
    openshift_configure_created_apps(config_as_dict)


# ------------------------------------------------------------

def get_cli_command(config_as_dict):
    return "%s/oc" % config_as_dict["cli_dir"]

def openshift_create_project_area(config_as_dict):
    os.system("%s new-project %s" % (get_cli_command(config_as_dict), get_openshift_area_name(config_as_dict)))
    os.system("%s project %s" % (get_cli_command(config_as_dict), get_openshift_area_name(config_as_dict)))
    os.system("%s secrets new scmsecret ssh-privatekey=$HOME/.ssh/id_rsa" % get_cli_command(config_as_dict)) # See https://blog.openshift.com/deploying-from-private-git-repositories/
    os.system("%s secrets add serviceaccount/builder secrets/scmsecret" % get_cli_command(config_as_dict))

def openshift_create_empty_apps(config_as_dict):
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        # labels_and_cmdlines = [ ["", None] ]  # by default, not a procfile-based
        # if app_has_procfile(options, dir_name_for_repo(repo_url)) and app_has_custom_run_script_path(options, dir_name_for_repo(repo_url)):
        #     labels_and_cmdlines = [[label, cmd_line] for label, cmd_line in procfile_iterator(options,dir_name_for_repo(repo_url))]
        for label, cmd_line in procfile_iterator(config_as_dict,dir_name_for_repo(repo_url)):
            suffix_from_label = label
            if label == "web":
                suffix_from_label = ""  # default label, should not be used as suffix
            cmd = '{cli} new-app --name={appname}{suffixfromlabel}' \
                   ' {repourl}#{branch} -e PORT=8080' \
                   ' -e PROCFILE_TARGET={procfilelabel}'.format(cli=get_cli_command(config_as_dict), appname=app_name,
                                                     repourl=get_http_repo_url(repo_url),
                                                     branch=branch,
                                                     repofullpath=get_repo_full_path_for_repo_url(repo_url),
                                                     suffixfromlabel=suffix_from_label,
                                                     procfilelabel=label,
                                                     cmdline=cmd_line)
            if "openshift-template" in app_props.get("paas_tweaks", {}):
                openshift_template_contents = app_props["paas_tweaks"]["openshift-template"]
                if len(openshift_template_contents.strip()) > 0:
                    cmd = "%s new-app %s" % (get_cli_command(config_as_dict), openshift_template_contents.format(template=openshift_template_contents,
                                                                                appname=app_name,
                                                                                repourl=get_http_repo_url(repo_url),
                                                                                branch=branch,
                                                                                repofullpath=get_repo_full_path_for_repo_url(repo_url),
                                                                                suffixfromlabel=suffix_from_label,
                                                                                procfilelabel=label,
                                                                                cmdline=cmd_line))
            print("\n\n**Creating app %s:%s: %s \n\n" % (app_name, label, cmd))
            err, out = execute_program(cmd)
            if len(err) > 0:  # some other error
                print(err)
            else:
                print(out)
            os.system("%s patch bc %s%s -p '{\"spec\":{\"source\":{\"sourceSecret\":{\"name\":\"scmsecret\"}}}}'" % (get_cli_command(config_as_dict), app_name,suffix_from_label))
            if suffix_from_label == "": #main target, exposed
                cmd = "%s expose service/%s --hostname=%s" % (get_cli_command(config_as_dict), app_name, get_openshift_app_host(config_as_dict, app_name))
                print("Creating app route for %s :  %s" % (app_name, cmd))
                err, out = execute_program(cmd)
                if len(err) > 0:  # some other error
                    print(err)
                else:
                    print(out)


def openshift_configure_created_apps(config_as_dict):
    app_names_by_repo_dir_name = {}
    for repo_url, branch, app_name, app_props in repo_and_branch_and_app_name_and_app_props_iterator(config_as_dict):
        app_names_by_repo_dir_name[dir_name_for_repo(repo_url)] = app_name
        openshift_create_database_if_needed(config_as_dict, repo_url, app_name, app_props)
        #openshift_create_mongo_if_needed(config_as_dict, repo_url, app_name)
        #openshift_inject_rabbitmq_service_if_needed(config_as_dict, repo_url, app_name)
        openshift_create_apps_env_vars_if_needed(config_as_dict, repo_url, app_name, app_props)  # env vars AFTER because some slam DATABASE_URL
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(config_as_dict):
        openshift_inject_requiremets_app(config_as_dict, repo_url, app_name, app_names_by_repo_dir_name)


def get_openshift_app_host(config_as_dict, app_name):
    return "%s-%s.%s" % (app_name, get_openshift_area_name(config_as_dict), config_as_dict.get("exposehost", "."))


def openshift_inject_requiremets_app(config_as_dict, repo_url, app_name, app_names_by_repo_dir_name):
    requirements_app = "%s/requirements.app" % get_repo_full_path_for_repo_url(repo_url)
    for line in templated_file_lines_iterator(config_as_dict, requirements_app):
        required_app_repo_dir_name = line.strip()
        required_app_name = app_names_by_repo_dir_name.get(required_app_repo_dir_name, None)
        if required_app_name is None:
            print("\n*** SEVERE WARNING: Configuring %s , "
                  "'%s' is listed as requirement but no app was deployed for this dir/git" %
                  (app_name, required_app_repo_dir_name))
            print(" \t Mapping: %s" % app_names_by_repo_dir_name)
            continue  # TO DO: Generate warmning? Halt teh deploy?
        required_app_url = "https://%s" % get_openshift_app_host(config_as_dict, required_app_name)
        cmd = '%s env dc/%s -e %s_URL=%s' % \
              (get_cli_command(config_as_dict), app_name, required_app_repo_dir_name.upper().replace("-", "_"), required_app_url)
        print("Configuring required app for %s: %s" % (app_name, cmd))
        os.system(cmd)


def openshift_create_apps_env_vars_if_needed(config_as_dict, repo_url, app_name, app_props):
    if "envs" in app_props:
        key_values = ['%s="%s"' % (key, str(value).replace(" ", "\\ ").replace('"', '\\"')) for key, value in
                      app_props["envs"].items()]
        if len(key_values) > 0:
            for label, cmd_line in procfile_iterator(config_as_dict, dir_name_for_repo(repo_url)):
                if label == "web":
                    label = ""  # default label, should not be used as suffix
                all_vars = " ".join(key_values)
                cmd = '%s env dc/%s%s -e %s' % (get_cli_command(config_as_dict), app_name, label, all_vars)
                print("\n\n\n**** Configuring env vars for %s%s: %s \n" % (app_name, label, cmd))
                os.system(cmd)
        else:
            print("WARNING: NO ENV VARS for %s (empty env file)" % app_name)
    else:
        print("WARNING: NO ENV VARS for %s (no env file)" % app_name)


def openshift_create_database_if_needed(config_as_dict, repo_url, app_name, app_props):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_database(config_as_dict, original_app_name, app_props):
        return
    cmd = "{cli} new-app postgresql --name=pg-{shortenedappname} " \
          "-e POSTGRESQL_DATABASE=db_{dbname} " \
          "-e POSTGRESQL_USER=user_{dbname} " \
          "-e POSTGRESQL_PASSWORD=pass_{dbname} " \
          "-e POSTGRESQL_ADMIN_PASSWORD=admin_{dbname}".format(cli=get_cli_command(config_as_dict), shortenedappname=get_openshift_short_app_name(app_name),
                                                               dbname=get_openshift_db_name_from_app_name(app_name))
    print("Configuring database for %s :  %s " % (app_name, cmd))
    ok = execute_program_and_print_output(cmd)
    if not ok:
        return False
    db_url = "postgresql://user_{dbname}:pass_{dbname}@pg-{shortenedappname}:5432/db_{dbname}".format(
        shortenedappname=get_openshift_short_app_name(app_name),
        dbname=get_openshift_db_name_from_app_name(app_name),
        deployhost=config_as_dict.get("deployhost", "."))
    print("Setting DATABASE_URL=%s   in %s" % (db_url, app_name))
    cmd = '%s env dc/%s -e DATABASE_URL=%s' % (get_cli_command(config_as_dict), app_name, db_url)
    ok = execute_program_and_print_output(cmd)
    if not ok:
        return False

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
    cmd = "%s whoami" % get_cli_command(config_as_dict)
    needs_login = True
    attempts = 0
    while needs_login:
        attempts += 1
        if attempts > 5:
            break
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
            os.system("%s login https://%s:8443" % (get_cli_command(config_as_dict), ip))


def openshift_rm_database_if_needed(config_as_dict, repo_url, app_name, app_props):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_database(config_as_dict, original_app_name, app_props):
        return
    print("Removing database for %s." % app_name)
    cmd = "%s delete all -l app=pg-%s" % (get_cli_command(config_as_dict), get_openshift_short_app_name(app_name))
    ok = execute_program_and_print_output(cmd)
    if not ok:
        return False #FIXME : exceptions?