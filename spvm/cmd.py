import click
import os
import os.path
import splogger as log
import spvm.core as core


def get_project(projectname):
    if os.path.isabs(projectname):
        project = core.make_project_object(projectname)
    else:
        project = core.make_project_object(
            os.path.join(os.getcwd(), projectname))

    return project


@click.group()
@click.option("-v", "--verbose", is_flag=True)
def cli(verbose):
    log.set_verbose(verbose)
    log.debug('pwd: ' + os.getcwd())
    core.check_script_version()


@cli.command()
@click.argument('projectname', default=".")
def init(projectname):
    """ Initializes a spvm project, use init projectname to create sub-directory projectname"""
    log.debug('Running init')
    get_project(projectname).init()


@cli.command()
@click.option("-s", "--show", is_flag=True,
              help="Show the problems with the code")
@click.argument('projectname', default=".")
def status(projectname, show):
    """ Print information about the project """
    get_project(projectname).print_project_status(show)


@cli.command()
@click.argument('projectname', default=".")
def update(projectname):
    """ Update the dependencies """
    get_project(projectname).update_dependencies()


@cli.command()
@click.argument('projectname', default=".")
def test(projectname):
    """ Run the tests on the current project """
    get_project(projectname).run_test()


@cli.command()
@click.argument('dependency')
@click.argument('projectname', default=".")
def add(dependency, projectname):
    """ Add and install a dependency to the project """
    get_project(projectname).add_dependency(dependency)


@cli.command()
@click.argument('projectname', default=".")
def repair(projectname):
    """ Force pep8 compliance on project """
    get_project(projectname).repair()


@cli.command()
@click.argument('projectname', default=".")
def patch(projectname):
    """ Start pipeline for patch release (e.g 0.0.1 -> 0.0.2) """
    get_project(projectname).release('patch')


@cli.command()
@click.argument('projectname', default=".")
def major(projectname):
    """ Start pipeline for major release (e.g 0.4.8 -> 1.0.0) """
    get_project(projectname).release('major')


@cli.command()
@click.argument('projectname', default=".")
def minor(projectname):
    """ Start pipeline for minor release (e.g 0.0.73 -> 0.1.0) """
    get_project(projectname).release('minor')


@cli.command()
@click.argument('kind', default=".")
@click.argument('projectname', default=".")
def release(kind, projectname):
    """
    Test build and publish to PyPi and or docker
    The release kind can be:
    - pass: No versin increase
    - major, minior, patch
    - <number>: increase the version index by 1
    """
    get_project(projectname).release(kind)


# @cli.command()
# def blind():
#     """
#     pass


@cli.command()
@click.argument('projectname', default=".")
def build(projectname):
    """ Build the project """
    pass


@cli.command()
@click.argument('projectname', default=".")
def install(projectname):
    """ Install a setup.py """
    get_project(projectname).install_setup(True)


# @cli.command()
# @click.argument('projectname', default=".")
# def run():
#     """ Run scripts defined in .pypm """
#     pass


if __name__ == "__main__":
    cli()
