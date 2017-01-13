import os
import shutil
import git
import timeout_decorator
import subprocess
import shlex


def execute_program(cmd):
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    err = err.decode().strip()
    out = out.decode().strip()
    return err, out


@timeout_decorator.timeout(10)
def execute_program_with_timeout(cmd):
    return execute_program(cmd)



class Progress(git.RemoteProgress):
    def line_dropped(self, line):
        print(self._cur_line)

    def update(self, *args):
        print(self._cur_line)


def current_path():
    return os.getcwd()


def parent_dir_path_for(a_path):
    return os.path.dirname(a_path)


def current_parent_path():
    return parent_dir_path_for(current_path())


def dir_name_for_repo(repo_url):
    return repo_url.split("/")[-1].split(".")[0]


def get_repo_full_path_for_repo_dir_name(repo_dir_name):
    repo_full_path = "%s/%s" % (current_parent_path(), repo_dir_name)
    return repo_full_path


def get_repo_full_path_for_repo_url(repo_url):
    return get_repo_full_path_for_repo_dir_name(dir_name_for_repo(repo_url))


def git_rm_all(config_as_dict, **kwargs):
    for app_name, app_props in config_as_dict.get("apps", {}).items():
        repo_url = app_props.get("git", None)
        repo_dir_name = dir_name_for_repo(repo_url)
        repo_full_path = "%s/%s" % (current_parent_path(), repo_dir_name)
        print("Removing %s at %s" % (app_name , repo_full_path))
        shutil.rmtree(repo_full_path, ignore_errors=True)

def git_clone_all(config_as_dict):
    progress = Progress()
    for app_name, app_props in config_as_dict.get("apps", {}).items():
        repo_url = app_props.get("git", None)
        branch = app_props.get("branch", None)
        repo_full_path = get_repo_full_path_for_repo_url(repo_url)
        if os.path.exists(repo_full_path):
            print("Already cloned %s from %s" % (app_name, repo_url))
            repo = git.Repo(repo_full_path)
            if repo.active_branch.name != branch:
                print("Your local checkout is in a different branch (%s) from the branch you want to deploy (%s). Aborting: %s" % (repo.active_branch.name, branch, repo_url))
                return False
        else:
            os.makedirs(repo_full_path)
            try:
                repo = git.Repo.clone_from(repo_url, repo_full_path, branch=branch, progress=progress)
                print("Cloned: %s" % repo)
            except git.GitCommandError as e:
                print(e)
                return False


def get_remote_repo_name(**kwargs):
    return "%s_%s" % (kwargs["cloud"], kwargs["scenario"])

def repo_and_branch_iterator(config_as_dict):
    for app_name, app_props in config_as_dict.get("apps", {}).items():
        repo_url = app_props.get("git", None)
        repo_branch = app_props.get("branch", None)
        yield repo_url, repo_branch


def repo_and_branch_and_app_name_iterator(config_as_dict):
    for app_name, app_props in config_as_dict.get("apps", {}).items():
        repo_url = app_props.get("git", None)
        repo_branch = app_props.get("branch", None)
        yield repo_url, repo_branch, app_name


# def git_clone_all(config_as_dict):
#     progress = Progress()
#     for repo_url, branch in repo_and_branch_iterator(config_as_dict):
#         repo_full_path = get_repo_full_path_for_repo_url(repo_url)
#         if os.path.exists(repo_full_path):
#             print("Already cloned: %s" % repo_url)
#             repo = git.Repo(repo_full_path)
#             if repo.active_branch.name != branch:
#                 print("Your local checkout is in a different branch (%s) from the branch you want to deploy (%s). Aborting: %s" % (repo.active_branch.name, branch, repo_url))
#                 return False
#         else:
#             os.makedirs(repo_full_path)
#             try:
#                 repo = git.Repo.clone_from(repo_url, repo_full_path, branch=branch, progress=progress)
#                 print("Cloned: %s" % repo)
#             except git.GitCommandError as e:
#                 print(e)
#                 return False
#         print("\r\n-------------------------------------------------------------\r\n")
#
#

def get_deploy_host(options):
    return options.get("deployhost", "")


def shared_services(shared_service_type, config_as_dict):
    return config_as_dict.get("shared_services", {}).get(shared_service_type, [])


def app_shared_services(shared_service_type, config_as_dict, app_name, app_props):
    all_shared_services = shared_services(shared_service_type, config_as_dict)
    app_services = app_props.get("services_used", [])
    return set(all_shared_services).intersection(set(app_services))


def app_has_shared_service(shared_service_type, config_as_dict, app_name, app_props):
    return len(app_shared_services(shared_service_type, config_as_dict, app_name, app_props)) > 0


def app_has_database(config_as_dict, app_name, app_props):
    return app_has_shared_service("postgres", config_as_dict, app_name, app_props)


def app_has_mongo(config_as_dict, app_name, app_props):
    return app_has_shared_service("mongo", config_as_dict, app_name, app_props)

