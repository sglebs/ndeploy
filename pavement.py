import sys
from paver.tasks import main
#from paver.easy import task, needs

sys.path.insert(0, ".")
from dokku_tasks import *
from openshift_tasks import *

@task
def undeploy(options):
    if get_system(options) == "openshift":
        openshift_undeploy(options)
    elif get_system(options) == "dokku":
        dokku_undeploy(options)
    else:
        pass


@task
def deploy(options):
    if get_system(options) == "openshift":
        openshift_deploy(options)
    elif get_system(options) == "dokku":
        dokku_deploy(options)
    else:
        pass

@task
def clean(options):
    if get_system(options) == "openshift":
        openshift_clean(options)
    elif get_system(options) == "dokku":
        dokku_clean(options)
    else:
        pass


if __name__ == '__main__':
    rc = main()
    sys.exit(rc)

