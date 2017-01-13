from core import git_rm_all, app_has_database, app_has_mongo, shared_services
import os

def clean(config_as_dict, **kwargs):
    undeploy(config_as_dict, **kwargs)
    git_rm_all(config_as_dict, **kwargs)


def deploy(config_as_dict, **kwargs):
    pass


def undeploy(config_as_dict, **kwargs):
    for app_name, app_props in config_as_dict.get("apps", {}).items():
        dokku_rm_database_if_needed(config_as_dict, app_name, app_props, **kwargs)
        dokku_rm_mongo_if_needed(config_as_dict, app_name, app_props, **kwargs)
        os.system("echo %s > confirm.txt" % app_name)
        os.system("ssh dokku@%s apps:destroy %s < confirm.txt" % (kwargs.get("deployhost", "."), app_name))
    dokku_rm_rabbitmq_services(config_as_dict, **kwargs)
    dokku_rm_redis_services(config_as_dict, **kwargs)

# ----------------------------------------------------------------

def dokku_rm_database_if_needed(config_as_dict, app_name, app_props, **kwargs):
    if not app_has_database(config_as_dict, app_name, app_props):
        return
    print("...Removing database for %s. Stopping app first" % app_name)
    os.system("ssh dokku@%s ps:stop %s" % (kwargs.get("deployhost", "."), app_name))
    os.system("ssh dokku@%s psql:delete %s" % (kwargs.get("deployhost", "."), app_name))
    # Just in case the step above fails, we shoot it hard, below.
    os.system('echo "drop database db_%s; \q" > drop.txt' % app_name.replace("-", "_"))
    os.system("ssh dokku@%s psql:admin_console < drop.txt" % (kwargs.get("deployhost", ".")))


def dokku_rm_mongo_if_needed(config_as_dict, app_name, app_props, **kwargs):
    if not app_has_mongo(config_as_dict, app_name, app_props):
        return
    print("...Removing mongo for %s" % app_name)
    os.system("echo %s > confirm.txt" % app_name)
    os.system("ssh dokku@%s mongo:destroy %s < confirm.txt" % (kwargs.get("deployhost", "."), app_name))
    os.system("ssh dokku@%s mongo:unlink %s %s" % (kwargs.get("deployhost", "."), app_name, app_name))


def dokku_rm_rabbitmq_services(config_as_dict, **kwargs):
    for service_name in shared_services("rabbitmq", config_as_dict):
        os.system("echo %s > confirm.txt" % service_name)
        print("...Removing RabbitMQ Service %s" % service_name)
        os.system("ssh dokku@%s rabbitmq:destroy %s < confirm.txt" % (kwargs.get("deployhost", "."), service_name))


def dokku_rm_redis_services(config_as_dict, **kwargs):
    for service_name in shared_services("rabbitmq", config_as_dict):
        os.system("echo %s > confirm.txt" % service_name)
        cmd = "ssh dokku@%s redis:destroy %s < confirm.txt" % (kwargs.get("deployhost", "."), service_name)
        print("...Removing Redis Service %s: %s " % (service_name, cmd))
        os.system(cmd)


