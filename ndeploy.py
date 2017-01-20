import click
import functools
import toml
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
    return merge_two_dicts(kwargs, toml.loads(templated_file_contents(kwargs, kwargs["cfgfile"])))


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
    cloud_module.clean(config_file_as_dict(**kwargs))


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
    cloud_module.deploy(config_file_as_dict(**kwargs))


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
    cloud_module.undeploy(config_file_as_dict(**kwargs))


@click.group()
def cli(**kwargs):
    """Start point for ndeploy."""
    pass

cli.add_command(clean)
cli.add_command(deploy)
cli.add_command(undeploy)

if __name__ == '__main__':
    deploy()
