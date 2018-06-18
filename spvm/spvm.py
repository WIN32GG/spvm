import click
import os
import subprocess
import splogger as log
from time import sleep

@click.group()
@click.option("-v", "--verbose", is_flag=True)
def cli(verbose):
    # TODO check version
    log.success("Tout va bien")
    log.warning("ça va moins bien")
    log.error("ça va plus")
    log.set_verbose(verbose)
    log.debug("test")

@cli.command()
@click.argument('projectname', default=".")
def init(projectname):
    """ Initializes a new pypm project, use init projectname to create sub-directory projectname"""
    click.echo(projectname)

@cli.command()
def install():
    """ Install the dependencies """
    click.echo('Mah man')

@cli.command()
def test():
    """ Run the tests on the current project """
    pass

@cli.command()
def patch():
    """ Start pipeline for patch release (e.g 0.0.1 -> 0.0.2) """
    pass

@cli.command()
def major():
    """ Start pipeline for major release (e.g 0.4.8 -> 1.0.0) """
    pass

@cli.command()
def minor():
    """ Start pipeline for minor release (e.g 0.0.73 -> 0.1.0) """
    pass

@cli.command()
def publish():
    """ Test build and publish to PyPi and or docker """
    pass

# @cli.command()
# def blind():
#     """ 
#     pass

@cli.command()
def build():
    """ Build the project """
    pass

@cli.command()
def run(): 
    """ Run scripts defined in .pypm """
    pass


if __name__ == "__main__":
    cli()