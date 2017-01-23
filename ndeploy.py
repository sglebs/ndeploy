import click
import functools
import toml, json, yaml
import importlib
from jinja2 import BaseLoader
from jinja2.environment import Environment
import getpass
from core import merge_two_dicts

def templated_file_contents(options, configfile):
    env = Environment(loader=BaseLoader)
    template = env.from_string(configfile.read())
    return template.render(options)


@functools.lru_cache(maxsize=2)
def config_file_as_dict(**kwargs):
    cfgfile = kwargs["cfgfile"]
    cfgfile_contents = templated_file_contents(kwargs, kwargs["cfgfile"])
    cfg_data = {}
    if cfgfile.name.endswith(".json"):
        cfgdata = json.loads(cfgfile_contents)
    elif cfgfile.name.endswith(".toml"):
        cfgdata = toml.loads(cfgfile_contents)
    elif cfgfile.name.endswith(".yaml"):
        cfgdata = yaml.load(cfgfile_contents)
    else:
        raise ValueError("Invalid config file format")
    return merge_two_dicts(kwargs, cfgdata)


@click.command()
@click.argument('cfgfile', type=click.File('r'))
@click.option('--cloud', default='dokku', help='Cloud PaaS to deploy against (dokku, openshift, tsuru, heroku, etc')
@click.option('--deployhost', default='dokku.me', help='Host where to push the code to')
@click.option('--exposehost', default='dokku.me', help='Public name that will form the URL of the exposed microservices')
@click.option('--scenario', default='dev', help='Type of scenario of this deploy (dev, staging, production, integrated, etc)')
@click.option('--area', default=getpass.getuser(), help='Name of teh area (workspace?) in the cloud/paas you are using')
@click.option('--cli_dir', default='/usr/local/bin', help='Path to the directory with the cli tool to call (oc, heroku, etc)')
def clean(**kwargs):
    cloud_module = importlib.import_module(kwargs["cloud"])
    processed_args = cloud_module.process_args(kwargs)
    cloud_module.clean(config_file_as_dict(**processed_args))


@click.command()
@click.argument('cfgfile', type=click.File('r'))
@click.option('--cloud', default='dokku', help='Cloud PaaS to deploy against (dokku, openshift, tsuru, heroku, etc')
@click.option('--deployhost', default='dokku.me', help='Host where to push the code to')
@click.option('--exposehost', default='dokku.me', help='Public name that will form the URL of the exposed microservices')
@click.option('--scenario', default='dev', help='Type of scenario of this deploy (dev, staging, production, integrated, etc)')
@click.option('--area', default=getpass.getuser(), help='Name of teh area (workspace?) in the cloud/paas you are using')
@click.option('--cli_dir', default='/usr/local/bin', help='Path to the directory with the cli tool to call (oc, heroku, etc)')
def deploy(**kwargs):
    cloud_module = importlib.import_module(kwargs["cloud"])
    processed_args = cloud_module.process_args(kwargs)
    cloud_module.deploy(config_file_as_dict(**processed_args))


@click.command()
@click.argument('cfgfile', type=click.File('r'))
@click.option('--cloud', default='dokku', help='Cloud PaaS to deploy against (dokku, openshift, tsuru, heroku, etc')
@click.option('--deployhost', default='dokku.me', help='Host where to push the code to')
@click.option('--exposehost', default='dokku.me', help='Public name that will form the URL of the exposed microservices')
@click.option('--scenario', default='dev', help='Type of scenario of this deploy (dev, staging, production, integrated, etc)')
@click.option('--area', default=getpass.getuser(), help='Name of the area (workspace?) in the cloud/paas you are using')
@click.option('--cli_dir', default='/usr/local/bin', help='Path to the directory with the cli tool to call (oc, heroku, etc)')
def undeploy(**kwargs):
    cloud_module = importlib.import_module(kwargs["cloud"])
    processed_args = cloud_module.process_args(kwargs)
    cloud_module.undeploy(config_file_as_dict(**processed_args))


@click.group()
def cli(**kwargs):
    """Start point for ndeploy."""
    pass

cli.add_command(clean)
cli.add_command(deploy)
cli.add_command(undeploy)

if __name__ == '__main__':
    deploy()
