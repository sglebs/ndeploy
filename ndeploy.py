import functools
import getpass
import importlib

import click
import json
import toml
import yaml
from jinja2 import BaseLoader
from jinja2.environment import Environment

from nd.core import merge_two_dicts

## define custom tag handler
def join(loader, node):
    seq = loader.construct_sequence(node)
    return ''.join([str(i) for i in seq])

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
        yaml.add_constructor('!join', join) # http://stackoverflow.com/questions/5484016/how-can-i-do-string-concatenation-or-string-replacement-in-yaml
        cfgdata = yaml.load(cfgfile_contents)
    else:
        raise ValueError("Invalid config file format")
    return merge_two_dicts(kwargs, cfgdata)


@click.command()
@click.pass_context
def clean(context, **kwargs):
    #click.echo("Cleaning with params %s and context %s" % (kwargs, context.parent.params))
    cloud_module = importlib.import_module(context.parent.params["cloud"])
    config_as_dict = cloud_module.process_args(context.parent.params)
    cloud_module.clean(config_file_as_dict(**config_as_dict))


@click.command()
@click.pass_context
def deploy(context, **kwargs):
    #click.echo("Deploying with params %s and parent context params %s" % (kwargs, context.parent.params))
    cloud_module = importlib.import_module(context.parent.params["cloud"])
    config_as_dict = cloud_module.process_args(context.parent.params)
    cloud_module.deploy(config_file_as_dict(**config_as_dict))


@click.command()
@click.pass_context
def undeploy(context, **kwargs):
    #click.echo("Undeploying with params %s and context %s" % (kwargs, context.meta))
    cloud_module = importlib.import_module(context.parent.params["cloud"])
    config_as_dict = cloud_module.process_args(context.parent.params)
    cloud_module.undeploy(config_file_as_dict(**config_as_dict))


@click.group()
@click.option('--cloud', default='nd.dokku', help='Cloud PaaS to deploy against (dokku, openshift, tsuru, heroku, etc). Prefix it with nd. to use our implementation.')
@click.option('--deployhost', default='dokku.me', help='Host where to push the code to')
@click.option('--exposehost', default='dokku.me', help='Public name that will form the URL of the exposed microservices')
@click.option('--scenario', default='dev', help='Type of scenario of this deploy (dev, staging, production, integrated, etc)')
@click.option('--area', default=getpass.getuser(), help='Name of the area (workspace?) in the cloud/paas you are using')
@click.option('--cli_dir', default='/usr/local/bin', help='Path to the directory with the cli tool to call (oc, heroku, etc)')
@click.option('--gitworkarea', default='/tmp', help='Path to the directory where the git clones etc will be performed')
@click.option('--cfgfile', type=click.File('r'), help='Path to the config file')
@click.pass_context
def cli(context, **kwargs):
    """Start point for ndeploy."""
    #click.echo("Starting with params %s and context params %s" % (kwargs, context.params))

cli.add_command(clean)
cli.add_command(deploy)
cli.add_command(undeploy)

#click.core.Context
if __name__ == '__main__':
    cli()
