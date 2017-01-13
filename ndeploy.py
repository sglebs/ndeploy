import click
import functools
import toml
import importlib
from jinja2 import BaseLoader
from jinja2.environment import Environment

def templated_file_contents(options, configfile):
    env = Environment(loader=BaseLoader)
    template = env.from_string(configfile.read())
    return template.render(options)

@functools.lru_cache(maxsize=2)
def config_file_as_dict(configfile, cloud, scenario):
    options = {"cloud": cloud, "scenario": scenario}
    return toml.loads(templated_file_contents(options, configfile))


@click.command()
@click.argument('cfgfile', type=click.File('r'))
@click.option('--cloud', default='dokku', help='Cloud PaaS to deploy against (dokku, openshift, tsuru, heroku, etc')
@click.option('--scenario', default='dev', help='Type of scenario of this deploy (dev, staging, production, integrated, etc)')
def clean(cfgfile, cloud, scenario):
    pass_module = importlib.import_module(cloud)
    pass_module.clean(config_file_as_dict(cfgfile, cloud, scenario))


@click.command()
@click.argument('cfgfile', type=click.File('r'))
@click.option('--cloud', default='dokku', help='Cloud PaaS to deploy against (dokku, openshift, tsuru, heroku, etc')
@click.option('--scenario', default='dev', help='Type of scenario of this deploy (dev, staging, production, integrated, etc)')
def deploy(cfgfile, cloud, scenario):
    pass_module = importlib.import_module(cloud)
    pass_module.deploy(config_file_as_dict(cfgfile, cloud, scenario))

@click.command()
@click.argument('cfgfile', type=click.File('r'))
@click.option('--cloud', default='dokku', help='Cloud PaaS to deploy against (dokku, openshift, tsuru, heroku, etc')
@click.option('--scenario', default='dev', help='Type of scenario of this deploy (dev, staging, production, integrated, etc)')
def undeploy(cfgfile, cloud, scenario):
    pass_module = importlib.import_module(cloud)
    pass_module.undeploy(config_file_as_dict(cfgfile, cloud, scenario))


@click.group()
@click.argument('cfgfile', type=click.File('r'))
@click.option('--cloud', default='dokku', help='Cloud PaaS to deploy against (dokku, openshift, tsuru, heroku, etc')
@click.option('--scenario', default='dev', help='Type of scenario of this deploy (dev, staging, production, integrated, etc)')
def cli(cfgfile, cloud, scenario):
    """Start point for ndeploy."""
    pass

cli.add_command(clean)
cli.add_command(deploy)
cli.add_command(undeploy)

