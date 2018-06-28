import click
import os
import os.path
import splogger as log
import spvm.core as core
import spvm.config as cfg


def get_project(projectname):
    if os.path.isabs(projectname):
        project = core.make_project_object(projectname)
    else:
        project = core.make_project_object(
            os.path.join(os.getcwd(), projectname))

    return project


@click.group()
@click.option("-v", "--verbose", is_flag=True)
@click.option("-m", "--mock", is_flag=True,
              help="Pypi server is test server, git won't push")
@click.option("-s", "--signed", is_flag=True,
              help="Check signatures whan DOWNLOADING packages")
@click.option("-r", "--repair", is_flag=True,
              help="Run autopep8 to make the code pep8 conform")
@click.option("-n", "--nocheck", is_flag=True,
              help="pep8 confirmity problem become non-fatal")
@click.option("-u", "--update", is_flag=True,
              help="Update dependencies before build")
@click.option("-t", "--notest", is_flag=True, help="Skip the test part")
@click.option("-y", "--yes", is_flag=True, help="No confirmation")
def cli(verbose, mock, signed, repair, nocheck, update, notest, yes):
    log.set_verbose(verbose)
    log.debug('pwd: ' + os.getcwd())

    cfg.config['mock'] = mock
    cfg.config['signed'] = signed
    cfg.config['repair'] = repair
    cfg.config['check'] = not nocheck
    cfg.config['update'] = update
    cfg.config['test'] = not notest
    cfg.config['ask'] = not yes
    if mock:
        log.warning('Mock Mode enabled')
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
@click.argument('targets', default="git,pypi,docker")
@click.argument('projectname', default=".")
def publish(targets, projectname):
    """
    Publish the project to the specified targets
    Namely, git, pypi and docker
    By defualt it wil try to publish to the 3
    I you only want a git and pypi publication for instance, use spvm publish git,pypi
    """
    tgts = targets.split(',')
    get_project(projectname).publish(
        git='git' in tgts,
        pypi='pypi' in tgts,
        docker='docker' in tgts)


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
