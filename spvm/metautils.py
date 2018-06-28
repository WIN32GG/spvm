import splogger as log
from .config import metaFileName, NoFailReadOnlyDict, metaFileLocation
from .ioutils import input_with_default, call_git
from colorama import Fore
import getpass
import os
import json
from os.path import join


def get_default_template():
    """
    Get the default metaFile to be used
    """
    with open(metaFileLocation, 'r') as f:
        template = f.read()
    return json.loads(template)


@log.element('Check meta')
def check_project_meta(meta):
    """
    Check the given meta so it matchs the template, adding  elements
    """

    def rec_check_meta(meta_elem, template_elem):
        if type(meta_elem) not in [dict, list]:
            return
        for t_elem in template_elem:
            if t_elem not in meta_elem:
                meta_elem[t_elem] = template_elem[t_elem]
                log.warning(
                    'Added ' +
                    t_elem +
                    ' to your project meta with default value')
            else:
                if isinstance(template_elem[t_elem], type({})):
                    rec_check_meta(meta_elem[t_elem], template_elem[t_elem])
                if isinstance(template_elem[t_elem], type([])):
                    if len(template_elem[t_elem]) > 0:
                        for e in meta_elem[t_elem]:
                            rec_check_meta(e, template_elem[t_elem][0])

    rec_check_meta(meta, get_default_template())
    log.debug('Checked project meta')


@log.auto()
def detect_project_meta(location):
    assert os.path.isdir(location)
    meta = get_default_template()

    # detect metaFile
    if os.path.isfile(join(location, metaFileName)):
        log.success('Found ' + metaFileName)
        with open(join(location, metaFileName), 'r') as f:
            lines = f.read()
        return json.loads(lines)

    # detect setup.py
    if os.path.isfile(join(location, 'setup.py')):
        log.success("Found setup.py")
        setup_info = detect_from_setup(join(location, 'setup.py'))
        log.debug('Setup detection yield: ' + setup_info)

        meta['project_info']['name'] = setup_info['name']
        meta['project_info']['description'] = setup_info['description']
        meta['project_info']['license'] = setup_info['license']
        meta['project_info']['url'] = setup_info['url']

        meta['project_authors'][0]['name'] = setup_info['author']
        meta['project_authors'][0]['email'] = setup_info['author_email']

        meta['project_vcs']['version'] = setup_info['version']

        meta['project_requirements']['python_packages'] = setup_info['install_requires']
        meta['project_requirements']['python_version'] = setup_info['python_requires']

    # detect .git
    if os.path.isdir(join(location, '.git')):
        log.success("Found git structure")
        remote = call_git('remote').split(' ')[0].strip()
        if remote != '':
            log.fine("Found remote " + remote)
            meta['project_vcs']['code_repository'] = call_git(
                'remote get-url ' + remote).strip()

        if meta['project_authors'][0]['email'] == '':
            log.fine('Using git to detect email')
            meta['project_authors'][0]['email'] = call_git(
                'config user.email').split()[0]

    # Find project name if not detected
    if meta['project_info']['name'] == '':
        meta['project_info']['name'] = os.path.basename(location)
        log.fine('Using default name: ' + meta['project_info']['name'])

    # detect __version__  (sort of common declaration)
    if meta['project_vcs']['version'] == '':
        meta['project_vcs']['version'] = load_version_from_file(
            location, meta['project_info']['name'])

    # other methods
    if meta['project_authors'][0]['name'] == '':
        meta['project_authors'][0]['name'] = getpass.getuser()
        log.fine('Using username as project author')

    if meta['project_vcs']['code_repository'] == '':
        log.fine('Using github private repo as code_repo')
        meta['project_vcs']['code_repository'] = "https://github.com/" + \
            getpass.getuser() + "/" + meta['project_info']['name']

    return meta


@log.clear()
def prompt_project_info(location, meta=get_default_template()):
    """
    Prompt the user for project information
    """

    print(f'\n{Fore.GREEN}~~~~ Project Setup ~~~~{Fore.RESET}')
    print(f'{Fore.LIGHTGREEN_EX}Project Location: {location}{Fore.RESET}')
    print(
        f'Enter {Fore.RED}null{Fore.RESET} or {Fore.RED}none{Fore.RESET} to leave a field blank\n')

    print(f'{Fore.CYAN}1/4:{Fore.LIGHTBLUE_EX} Project Info {Fore.RESET}')
    meta['project_info']['name'] = input_with_default(
        'Project Name', meta['project_info']['name'])
    meta['project_info']['description'] = input_with_default(
        'Project Description', meta['project_info']['description'])
    meta['project_info']['license'] = input_with_default(
        'Project License', meta['project_info']['license'])
    meta['project_info']['url'] = input_with_default(
        'Project URL', meta['project_info']['url'])

    print(f'{Fore.CYAN}2/4:{Fore.LIGHTBLUE_EX} Project Author {Fore.RESET}')
    meta['project_authors'][0]['name'] = input_with_default(
        'Name', meta['project_authors'][0]['name'])
    meta['project_authors'][0]['url'] = input_with_default(
        'URL', meta['project_authors'][0]['url'])
    meta['project_authors'][0]['email'] = input_with_default(
        'Email', meta['project_authors'][0]['email'])
    print(f'{Fore.LIGHTGREEN_EX}Note that you can add more authors in the project {metaFileName} later{Fore.RESET}')

    print(f'{Fore.CYAN}3/4:{Fore.LIGHTBLUE_EX} Project Version Control {Fore.RESET}')
    meta['project_vcs']['code_repository'] = input_with_default(
        'Code Repo', meta['project_vcs']['code_repository'])
    print(f'{Fore.GREEN}SPVM does not upload to Docker by default, add a repository to upload to\nand spvm will generate a generic Dockerfile{Fore.RESET}')
    meta['project_vcs']['docker_repository'] = input_with_default(
        'Docker Repo',
        meta['project_vcs']['docker_repository'])  # f'{getpass.getuser()}/{meta.project_info.name}'
    print(f'{Fore.GREEN}SPVM does not upload to PyPi by default use: {Fore.CYAN}https://upload.pypi.org/legacy/{Fore.GREEN} as a pypi_repo to enable it (or use your own ;) ){Fore.RESET}')
    meta['project_vcs']['pypi_repository'] = input_with_default(
        'PyPi Repo', meta['project_vcs']['pypi_repository'])
    meta['project_vcs']['version'] = input_with_default(
        'Current Version', meta['project_vcs']['version'])

    print(f'{Fore.CYAN}4/4:{Fore.LIGHTBLUE_EX}Project Requirements{Fore.RESET}')
    meta['project_requirements']['python_version'] = input_with_default(
        'Python Version', meta['project_requirements']['python_version'])
    dep = meta['project_requirements']['python_packages']
    print(f'{Fore.GREEN}Current dependencies: {" ".join(dep)}{Fore.RESET}')
    print(f'{Fore.GREEN}Add 1 dependency at a time and press Enter\nLeave blank to finish{Fore.RESET}')
    while True:
        tmp = input_with_default('Dependency', '')
        if tmp == '':
            break
        dep.append(tmp)
    meta['project_requirements']['python_packages'] = dep

    return meta


@log.auto()
def detect_from_setup(setup_file):
    setup_info = {}

    def fake_setup(**kwargs):
        nonlocal setup_info
        setup_info = kwargs

    import setuptools
    original_setup = setuptools.setup
    setuptools.setup = fake_setup

    try:
        with open(setup_file, 'r') as fh:
            setup_code = fh.read()

        exec(setup_code, globals())
        return NoFailReadOnlyDict(setup_info)
    except BaseException:
        log.error('Could not detect project config from setup.py')
        return None
    finally:
        setuptools.setup = original_setup


@log.auto()
def load_version_from_file(location, project_name):
    default_version = ''
    try:
        versionfile = join(location, project_name, '__version__.py')
        if os.path.isfile(versionfile):
            loaded_vfile = {}
            with open(versionfile, 'r') as vfile:
                content = vfile.read()
            exec(content, loaded_vfile)
            if loaded_vfile['__version__']:
                default_version = loaded_vfile['__version__']
                log.success(
                    "Found version " +
                    default_version +
                    " for project " +
                    project_name)
    except BaseException as ex:
        log.error('Could not load file version: ' + ex.__class__.__name__)

    return default_version


__all__ = [
    'load_version_from_file',
    'detect_from_setup',
    'prompt_project_info',
    'detect_project_meta',
    'get_default_template']
