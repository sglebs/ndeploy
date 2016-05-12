from core_tasks import *
from paver.easy import task, needs
import socket
import timeout_decorator
import getpass

RABBITMQ_PORT = 5662
RABBITMQ_ADMIN_PORT = 15662
RABBITMQ_USER = "admin"
RABBITMQ_PASSWORD = "123456"

_RABBITMQ_SETUP_CMD = \
    'curl -i -u %s:%s -H "content-type:application/json" -X POST --data @%s http://%s:15673/api/definitions'


def get_openshift_area_name(options):
    default = getpass.getuser()
    return options.get("area", default)


def get_openshift_template_contents(options, openshift_template_path):
    return templated_file_contents(options, openshift_template_path).strip()


def get_http_repo_url(repo_url):
    adapted_repo_url = repo_url.replace(":", "/").replace("git@", "https://") if repo_url.startswith(
        "git") else repo_url
    return adapted_repo_url


def get_openshift_short_app_name(app_name):
    return app_name[:20]


def get_openshift_db_name_from_app_name(app_name):
    return get_openshift_short_app_name(app_name).replace("-", "_")


@task
def openshift_login(options):
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
            ip = socket.gethostbyname(get_deploy_host(options))
            os.system("oc login https://%s:8443" % ip)


@task
def openshift_create_project_area(options):
    os.system("oc new-project %s" % get_openshift_area_name(options))
    os.system("oc project %s" % get_openshift_area_name(options))
    # now we use https
    # os.system("oc secrets new scmsecret ssh-privatekey=$HOME/.ssh/id_rsa")
    # os.system("oc secrets add serviceaccount/builder secrets/scmsecret")


def get_openshift_app_host(options, app_name):
    return "%s-%s.%s" % (app_name, get_openshift_area_name(options), get_expose_host(options))


@task
def openshift_create_empty_apps(options):
    print("------------------------------------------------------------")
    print("CREATING APPS")
    print("------------------------------------------------------------")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        # labels_and_cmdlines = [ ["", None] ]  # by default, not a procfile-based
        # if app_has_procfile(options, dir_name_for_repo(repo_url)) and app_has_custom_run_script_path(options, dir_name_for_repo(repo_url)):
        #     labels_and_cmdlines = [[label, cmd_line] for label, cmd_line in procfile_iterator(options,dir_name_for_repo(repo_url))]
        for label, cmd_line in procfile_iterator(options,dir_name_for_repo(repo_url)):
            if label == "web":
                label = ""  # default label, should not be used as suffix
            openshift_template_path = "%s/%s.txt" % (get_template_dir(options), dir_name_for_repo(repo_url))
            cmd = 'oc new-app --name={appname}{procfilelabel}' \
                   ' {repourl}#{branch} -e PORT=8080' \
                   ' -e EXEC_CMD="{cmdline}"'.format (appname=app_name,
                                                     repourl=get_http_repo_url(repo_url),
                                                     branch=branch,
                                                     repofullpath=get_repo_full_path_for_repo_url(repo_url),
                                                     procfilelabel=label,
                                                     cmdline=cmd_line)
            if os.path.exists(openshift_template_path):
                openshift_template_contents = get_openshift_template_contents(options, openshift_template_path)
                if len(openshift_template_contents.strip()) > 0:
                    cmd = "oc new-app %s" % (openshift_template_contents.format(template=openshift_template_contents,
                                                                                appname=app_name,
                                                                                repourl=get_http_repo_url(repo_url),
                                                                                branch=branch,
                                                                                repofullpath=get_repo_full_path_for_repo_url(repo_url),
                                                                                procfilelabel=label,
                                                                                cmdline=cmd_line))
            print("\n\n*****Creating app %s: %s \n\n" % (app_name, cmd))
            err, out = execute_program(cmd)
            if len(err) > 0:  # some other error
                print(err)
            else:
                print(out)
            if label == "":
                cmd = "oc expose service/%s --hostname=%s" % (app_name, get_openshift_app_host(options, app_name))
                print("...Creating app route for %s :  %s" % (app_name, cmd))
                err, out = execute_program(cmd)
                if len(err) > 0:  # some other error
                    print(err)
                else:
                    print(out)


@task
@needs(['openshift_create_empty_apps'])
def openshift_create_apps_env_vars(options):
    print("------------------------------------------------------------")
    print("ENV VARS CONFIG")
    print("------------------------------------------------------------")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        openshift_create_apps_env_vars_if_needed(options, repo_url, app_name)


def openshift_create_apps_env_vars_if_needed(options, repo_url, app_name):
    options_as_dict = options_to_dict(options)
    original_app_name = dir_name_for_repo(repo_url)
    if app_has_env_vars(options, original_app_name):
        key_values = ['%s="%s"' % (key, value.format(**options_as_dict)) for key, value in
                      env_vars_iterator(options, original_app_name, appname=app_name)]
        if len(key_values) > 0:
            for label, cmd_line in procfile_iterator(options, dir_name_for_repo(repo_url)):
                if label == "web":
                    label = ""  # default label, should not be used as suffix
                all_vars = " ".join(key_values)
                cmd = 'oc env dc/%s%s -e %s' % (app_name, label, all_vars)
                print("\n\n\n**** Configuring env vars for %s%s: %s \n" % (app_name, label, cmd))
                os.system(cmd)
        else:
            print("WARNING: NO ENV VARS for %s (empty env file)" % app_name)
    else:
        print("WARNING: NO ENV VARS for %s (no env file)" % app_name)


def openshift_inject_requiremets_app(options, repo_url, app_name, app_names_by_repo_dir_name):
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
        required_app_url = "https://%s" % get_openshift_app_host(options, required_app_name)
        cmd = 'oc env dc/%s -e %s_URL=%s' % \
              (app_name, required_app_repo_dir_name.upper().replace("-", "_"), required_app_url)
        print("...Configuring required app for %s: %s" % (app_name, cmd))
        os.system(cmd)


@task
@needs(['openshift_create_empty_apps'])
def openshift_create_configured_apps(options):
    app_names_by_repo_dir_name = {}
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        app_names_by_repo_dir_name[dir_name_for_repo(repo_url)] = app_name
        openshift_create_database_if_needed(options, repo_url, app_name)
        openshift_create_mongo_if_needed(options, repo_url, app_name)
        openshift_inject_rabbitmq_service_if_needed(options, repo_url, app_name)
        openshift_create_apps_env_vars_if_needed(options, repo_url, app_name)  # env vars AFTER because some slam DATABASE_URL
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        openshift_inject_requiremets_app(options, repo_url, app_name, app_names_by_repo_dir_name)


def openshift_inject_rabbitmq_service_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_rabbitmq(options, original_app_name):
        return
    for service_name in rabbitmqs_servicenames_iterator(options, original_app_name):
        rabbit_mq_url = "amqp://{rabbitadminuser}:{rabbitadminpassword}@" \
                        "rb-{service_name}:{rabbitmqport}/{service_name}".format(
                            appname=app_name, service_name=service_name, rabbitadminuser=RABBITMQ_USER,
                            rabbitadminpassword=RABBITMQ_PASSWORD, rabbitmqport=RABBITMQ_PORT)
        cmd = 'oc env dc/{appname} -e RABBITMQ_URL="{rabbitmqurl}"'.format(appname=app_name, rabbitmqurl=rabbit_mq_url)
        print("...Configuring RABBITMQ_URL for app %s : %s" % (app_name, cmd))
        os.system(cmd)
        rabbitmq_config_json_path = rabbit_mq_initialization_file_path(options, original_app_name)
        if not os.path.exists(rabbitmq_config_json_path):
            continue
        cmd = _RABBITMQ_SETUP_CMD % (RABBITMQ_USER,
                                     RABBITMQ_PASSWORD,
                                     rabbitmq_config_json_path,
                                     get_openshift_app_host(options, "rb-%s" % service_name),
                                     )
        print("Initializing queues: %s" % cmd)
        os.system(cmd)


@task
@needs(['openshift_create_empty_apps'])
def openshift_create_databases(options):
    print("------------------------------------------------------------")
    print("DATABASE SETUP")
    print("------------------------------------------------------------")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        ok = openshift_create_database_if_needed(options, repo_url, app_name)
        if not ok:
            return False


def openshift_create_database_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_database(options, original_app_name):
        return
    cmd = "oc new-app postgresql --name=pg-{shortenedappname} " \
          "-e POSTGRESQL_DATABASE=db_{dbname} " \
          "-e POSTGRESQL_USER=user_{dbname} " \
          "-e POSTGRESQL_PASSWORD=pass_{dbname} " \
          "-e POSTGRESQL_ADMIN_PASSWORD=admin_{dbname}".format(shortenedappname=get_openshift_short_app_name(app_name),
                                                               dbname=get_openshift_db_name_from_app_name(app_name))
    print("...Configuring database for %s :  %s " % (app_name, cmd))
    ok = execute_program_and_print_output(cmd)
    if not ok:
        return False
    db_url = "postgresql://user_{dbname}:pass_{dbname}@pg-{shortenedappname}:5432/db_{dbname}".format(
        shortenedappname=get_openshift_short_app_name(app_name),
        dbname=get_openshift_db_name_from_app_name(app_name),
        deployhost=get_deploy_host(options))
    print("...Setting DATABASE_URL=%s   in %s" % (db_url, app_name))
    cmd = 'oc env dc/%s -e DATABASE_URL=%s' % (app_name, db_url)
    ok = execute_program_and_print_output(cmd)
    if not ok:
        return False


def openshift_rm_database_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_database(options, original_app_name):
        return
    print("...Removing database for %s." % app_name)
    cmd = "oc delete all -l app=pg-%s" % get_openshift_short_app_name(app_name)
    ok = execute_program_and_print_output(cmd)
    if not ok:
        return False


@task
def openshift_create_rabbitmq_services(options):
    print("------------------------------------------------------------")
    print("RABBITMQ SETUP")
    print("------------------------------------------------------------")

    if not platform_needs_rabbitmq_as_a_service(options):
        return

    cmd = "oc create -f %s" % rabbitmq_template_path(options)
    print("...Importing RabbitMQ Template: %s" % cmd)
    err, out = execute_program_with_timeout(cmd)
    print(out)
    if len(err) > 0 and "already exists" not in err:
        print(err)
        return False
    for line in rabbitmqs_services_iterator(options):
        service_name, mq_port, cluster_resolution_port, mgmt_port, cluster_comms_port = line.strip().split(",")
        cmd = "oc new-app {templatename} -p " \
              "RABBITMQ_SERVICE_NAME=rb-{service_name}," \
              "RABBITMQ_USER={rabbitadminuser}," \
              "RABBITMQ_PASSWORD={rabbitadminpassword} -l app=rb-{service_name}".format(
                 service_name=service_name, templatename="rabbitmq-ephemeral",
                 rabbitadminuser=RABBITMQ_USER, rabbitadminpassword=RABBITMQ_PASSWORD,
                 rabbitmqport=RABBITMQ_PORT, rabbitmqadminport=RABBITMQ_ADMIN_PORT)
        print("...Creating RabbitMQ Service: %s" % cmd)
        try:
            err, out = execute_program_with_timeout(cmd)
            print(err)
            print(out)
            if len(err) > 0 and "error" in err:
                return False
        except timeout_decorator.TimeoutError:
            pass  # bug in dokku rabbitmq https://github.com/dokku/dokku-rabbitmq/issues/34


def openshift_rm_rabbitmq_if_needed(options):
    for line in rabbitmqs_services_iterator(options):
        service_name, mq_port, cluster_resolution_port, mgmt_port, cluster_comms_port = line.strip().split(",")
        cmd = "oc delete all -l name=rb-{service_name}".format(service_name=service_name)
        print("...Removing RabbitMQ Service: %s" % cmd)
        execute_program_and_print_output(cmd)


@task
@needs(['openshift_create_empty_apps'])
def openshift_create_mongos(options):
    print("------------------------------------------------------------")
    print("MONGO SETUP")
    print("------------------------------------------------------------")
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        openshift_create_mongo_if_needed(options, repo_url, app_name)


def openshift_create_mongo_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_mongo(options, original_app_name):
        return
    cmd = "oc new-app mongodb-persistent -p " \
          "VOLUME_CAPACITY=128Mi," \
          "DATABASE_SERVICE_NAME=mg-{shortenedappname}," \
          "MONGODB_DATABASE=db_{dbname}," \
          "MONGODB_USER=user_{dbname}," \
          "MONGODB_PASSWORD=pass_{dbname}," \
          "MONGODB_ADMIN_PASSWORD=admin_{dbname} -l app=mg-{shortenedappname}".format(
            shortenedappname=get_openshift_short_app_name(app_name),
            dbname=get_openshift_db_name_from_app_name(app_name))
    print("...Configuring mongo for %s :  %s " % (app_name, cmd))
    execute_program_and_print_output(cmd)
    db_url = "mongodb://user_{dbname}:pass_{dbname}@mg-{shortenedappname}:27017/db_{dbname}".format(
        shortenedappname=get_openshift_short_app_name(app_name),
        dbname=get_openshift_db_name_from_app_name(app_name),
        deployhost=get_deploy_host(options))
    print("...Setting MONGO_URL=%s   in %s" % (db_url, app_name))
    cmd = 'oc env dc/%s -e MONGO_URL=%s' % (app_name, db_url)
    print("...Configuring mongo ENV VAR for %s :  %s " % (app_name, cmd))
    execute_program_and_print_output(cmd)


def openshift_rm_mongo_if_needed(options, repo_url, app_name):
    original_app_name = dir_name_for_repo(repo_url)
    if not app_has_mongo(options, original_app_name):
        return
    cmd = "oc delete all -l app=mg-%s" % get_openshift_short_app_name(app_name)
    print("...Removing mongo for %s : %s" % (app_name, cmd))
    ok = execute_program_and_print_output(cmd)
    if not ok:
        return False


@task
@needs(['openshift_login'])
def openshift_undeploy(options):
    for repo_url, branch, app_name in repo_and_branch_and_app_name_iterator(options):
        for label, cmd_line in procfile_iterator(options, dir_name_for_repo(repo_url)):
            if label == "web":
                label = ""  # default label, should not be used as suffix
            print("...Removing app %s%s" % (app_name,label))
            os.system("oc delete all -l app=%s%s" % (app_name, label))
        openshift_rm_database_if_needed(options, repo_url, app_name)
        openshift_rm_mongo_if_needed(options, repo_url, app_name)
    openshift_rm_rabbitmq_if_needed(options)


@task
@needs(['git_clone_all', 'openshift_login', 'openshift_create_project_area',
        'openshift_create_rabbitmq_services', 'openshift_create_configured_apps'])
def openshift_deploy(options):
    print(options)


@task
@needs(['openshift_undeploy', 'git_rm_all'])
def openshift_clean():
    print("Cleaned OpenShift apps and git repos")
