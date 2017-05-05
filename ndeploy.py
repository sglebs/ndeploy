import functools
import getpass
import importlib
import os
import click
import json
import toml
import yaml
from jinja2 import FileSystemLoader
from jinja2.environment import Environment
import copy
from nd.core import merge_two_dicts
from nd.URLLoader import URLloader
import requests
from requests_file import FileAdapter



## define custom tag handler - see http://stackoverflow.com/questions/5484016/how-can-i-do-string-concatenation-or-string-replacement-in-yaml
def join(loader, node):
    seq = loader.construct_sequence(node)
    return ''.join([str(i) for i in seq])

def templated_file_contents(options, configfile):
    paths = options["searchpath"].split(",") # CSV of PATHs
    if os.path.isdir(paths[0]):
        loader = FileSystemLoader(paths)
    else:
        loader = URLloader(paths)
    env = Environment(loader=loader)
    contents, config_full_path, _a_lambda_ = loader.get_source(env, configfile)
    template = env.from_string(contents, globals=options)
    return template.render(options)


@functools.lru_cache(maxsize=2)
def config_file_as_dict(**kwargs):
    cfgfile = kwargs["cfgfile"]
    cfgfile_contents = templated_file_contents(kwargs, kwargs["cfgfile"])
#    print (cfgfile_contents)
    cfg_data = {}
    if cfgfile.endswith(".json"):
        cfgdata = json.loads(cfgfile_contents)
    elif cfgfile.endswith(".toml"):
        cfgdata = toml.loads(cfgfile_contents)
    elif cfgfile.endswith(".yaml"):
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
@click.option('--privatekey', default='$HOME/.ssh/id_rsa', help='Path to the private key')
@click.option('--gitpull', type=click.BOOL, default=True, help='Whether ndeploy should perform git pull if a git clone is found at --gitworkarea')
@click.option('--cfgfile', default="solution.yaml", help='Name of the config file to search for in --searchpath')
@click.option('--searchpath', default=".", help='A CSV of locations where the cfgfile and its includes will be searched for')
@click.option('--strategy', default='auto', help='Kind of strategy to use. Cloud-specific. auto, docker, buildpack, etc.')
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
