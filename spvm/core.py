import splogger as log
import os.path
from os.path import join
import json
from colorama import Fore
import urllib.request
import subprocess
from time import sleep
from shutil import rmtree
from subprocess import CalledProcessError
import spvm

from . import ioutils
from . import metautils
from . import config


class PYVSProject(object):
    """
    A project object at the current cwd
    """

    def __init__(self, location=os.getcwd()):
        self.location = location  # directory for project
        if os.path.isdir(location):
            os.chdir(location)
            log.debug("cwd switched: " + location)
        log.debug("New  project instance @ " + self.location)
        log.debug("Project status is: " + str(self.get_project_status()))
        self.projectMetaFile = join(self.location, config.metaFileName)
        self.maybe_load_meta()


    def init(self):
        """
        Create the spvm project folder and init a base project structure
        Guess project meta and asks for correction, write in metaFile
        """
        os.makedirs(join(self.location, 'test'), exist_ok=True)
        os.makedirs(
            join(
                self.location,
                os.path.basename(
                    self.location)),
            exist_ok=True)
        self.meta = metautils.detect_project_meta(self.location)
        # self.print_project_meta()
        while True:
            metautils.prompt_project_info(self.location, self.meta)
            self.print_project_meta()

            if metautils.input_with_default(
                    f'{Fore.CYAN}Is this correct? {Fore.RESET}[y/n]') in ('y', 'Y', '1', 'yes', 'Yes'):
                break

        self.save_project_info()

        log.success('Project initialized')

    def print_project_meta(self):
        print(Fore.GREEN + '      Project Metadata' + Fore.RESET)
        print(json.dumps(self.meta, indent=4))

    def get_project_status(self):
        """
        Get the status, is the project initialized, not present?
        """

        if not os.path.isdir(self.location):
            # The project folder does not exist
            return config.STATUS_PROJECT_DOES_NOT_EXIST
        if not os.path.isfile(os.path.join(
                self.location, config.metaFileName)):
            # The project exists but the spvm project is not initiated
            return config.STATUS_PROJECT_NOT_INITIALIZED
        return config.STATUS_PROJECT_INITIALIZED        # The spvm project is initiated

    def check_code(self):
        """
        Run pyflakes and pycodestyle to check ode validity and pep8 conformity
        Reported problems are in the 2 returned arrays
        """

        flakes, pep = ioutils.call_check(
            self.location, ignore=self.meta['project_vcs']['ignored_errors'])

        flakes = flakes.split('\n')[:-1]
        pep = pep.split('\n')[:-1]

        return flakes, pep

    def run_test(self):
        """
        Run the tests with pytest
        """
        try:
            ioutils.call_pytest(self.location)
        except CalledProcessError as ex:
            if ex.returncode == 5:
                log.warning('No tests were found')
                log.warning(
                    'This is not considered fatal but is VERY STRONGLY discouraged')
                log.warning('Resuming in 2 seconds')
                sleep(2)
                return
            log.error('Tests Failed')
            exit(1)
        log.success('Tests passed')

    def save_project_info(self):
        """
        Write the current project info to the metaFile
        """
        with open(self.projectMetaFile, 'w+') as fh:
            fh.write(json.dumps(self.meta, indent=4))
        log.debug('Saved project meta')

    @log.auto()
    def add_dependency(self, dep):
        """
        Add a dependency to the project:
        Pip handles different sources:
        - PyPI (and other indexes) using requirement specifiers.
        - VCS project urls.
        - Local project directories.
        - Local or remote source archives.
        """
        if self.get_project_status() != config.STATUS_PROJECT_INITIALIZED:
            log.error(
                "The project is not initialized, call spvm init first before adding dependencies")
            return

        supp_args = ""

        if os.path.isdir(dep):
            log.warning(
                "Adding local dependency, this may break when releasing the project")

        if os.path.isfile(dep):
            log.warning(
                "Got a file as dependency name, using as requirements.txt")
            supp_args = '-r '

        try:
            ioutils.call_pip('install ' + supp_args + '' + dep)
        except CalledProcessError as ex:
            log.error("Pip call failed with code " + str(ex.returncode))
            log.error("Does the dependency exist or is something broken?")
            return

    def maybe_load_meta(self):
        """
        If a metaFile exists, it will be loaded
        """

        if os.path.isfile(self.projectMetaFile):
            try:
                with open(self.projectMetaFile, 'r') as fh:
                    self.meta = json.loads(fh.read())
                    log.debug('Loaded project meta')
            except json.JSONDecodeError as e:
                log.error(repr(e))
                log.error(config.metaFileName + " is invalid")
                exit(1)
        else:
            log.debug('No meta to load')

    def remove_dependency(self, dep):
        # TODO
        log.error('Not implemented')

    @log.element('Setup install')
    def install_setup(self, force=False):
        """
        Install the template setup.py
        """

        already_present = os.path.isfile(join(self.location, 'setup.py'))
        if already_present and not force:
            log.warning('setup.py already present, it will not be replaced')
            log.warning('Run spvm install to force setup.py replacement')
            return

        if already_present:
            log.fine('Creating setup.py.backup')
            ioutils.copy(
                join(
                    self.location,
                    'setup.py'),
                join(
                    self.location,
                    'setup.py.backup'))

        log.success('Copying seyup.py from template')
        ioutils.copy(
            join(
                os.path.dirname(__file__),
                'res',
                'setup.py'),
            join(
                self.location,
                'setup.py'))

    @log.no_spinner()
    @log.element('Update project dependencies', log_entry=True)
    def update_dependencies(self):
        """
        Run a pip upgrade of the dependency list
        """
        ioutils.call_pip(
            'install ' +
            " ".join(
                self.meta['project_requirements']['python_packages']) +
            " --upgrade")

    def up_version(self, kind):  # FIXME other to 0
        """
        Increase the version in the project meta base on the 'kind' instruction:
        kind can be a str or a number
        if a number, it is treated like an index for the version increment
        if a string, it can be major, minor or patch
        """

        log.fine('Increasing version (' + str(kind) + ')')
        v = self.meta['project_vcs']['version']
        v_ = [int(i) for i in v.split('.')]
        while len(v_) < 3:
            v_.insert(0, '0')
        log.debug("Current version comphrension: " + str(v_))

        if kind.isdigit():
            kind = int(kind)
            if kind < 0 or kind >= len(v_):
                log.error('Unrecognized version changer: ' + str(kind))
            v_[int(kind)] += 1
        else:
            kind = kind.lower()
            if kind == 'patch':
                index = len(v_) - 1
            elif kind == 'major':
                index = 0
            elif kind == 'minor':
                index = len(v_) - 2
            elif kind == 'pass':
                log.success('Version not changed')
                return
            else:
                log.error('Unrecognized version changer: ' + str(kind))
                exit(1)

            v_[index] += 1
            v_ = [v_[i] if i <= index else 0 for i in range(len(v_))]

        self.meta['project_vcs']['version'] = '.'.join([str(i) for i in v_])
        self.save_project_info()
        log.success(v + ' -> ' + self.get_version())

    def release(self, kind='pass', update=True, publish=True,
                check=True, test=True, repair=True):
        """
        Starts a release pipeline
        """

        pipeline = []
        log.fine('Calculating release pipeline')

        if update:
            pipeline.append(self.update_dependencies)
        if repair:
            pipeline.append(self.repair)
        if check:
            pipeline.append(self.check_project)
        if test:
            pipeline.append(self.run_test)

        pipeline.append(self.up_version)
        pipeline.append(self.install_setup)

        if publish:
            pipeline.append(self.publish)

        log.success('Release pipeline is: ' +
                    " ".join([f.__name__ for f in pipeline]))

        for f in pipeline:
            if f.__name__ == 'wrapper':
                continue

            log.success('> ' + f.__name__)
            if f.__name__ == 'up_version':  # the only one to give parameters to
                f(kind)
            else:
                f.__call__()

    def check_project(self):
        """ Check code and exit if not conform """
        pf, pe = self.check_code()

        if len(pf) + len(pe) > 0:
            log.error('Project is not conform or has errors, run spvm status -s')
            exit(1)

    @log.element('🔧 Code repair')
    def repair(self):
        ioutils.call_python('autopep8', '-ra --in-place .')

    @log.element('Building', log_entry=True)
    def build(self):
        log.success('Building package in ./build')
        try:
            ioutils.call_python(
                '', 'setup.py sdist -d build/dist bdist_wheel -d build/dist', stdout=subprocess.PIPE)
        except CalledProcessError as ex:
            log.error('Unable to build the package')
            log.error(repr(ex))
            exit(1)

    @log.element('Cleaning up', log_entry=True)
    def clear_build(self):
        # remove ./build ./<name>.egg-info
        rmtree('./build', True)
        rmtree('./'+self.get_name()+'.egg-info', True)

    @log.element('Publishing')
    def publish(self, git=False, pypi=True, docker=True):
        if git:
            self._release_git()
        if pypi:
            self._release_pypi()
        if docker:
            self._release_docker()

    @log.element('Git Publishing', log_entry=True)
    def _release_git(self):
        # Commit version
        commit_message = self.meta['project_vcs']['release']['commit_template'].replace(
            '%s', self.meta['project_vcs']['version']).replace('"', '\\"')
        log.debug('Commit message: ' + commit_message)
        ioutils.call_git('add .')
        ioutils.call_commit(commit_message)  # FIXME signed

        # Tag version
        tag = self.meta['project_vcs']['release']['tag_template'].replace(
            '%s', self.meta['project_vcs']['version'])
        ioutils.call_git('tag -s ' + tag)  # FIXME -u

        # Push
        ioutils.call_git('push --signed=if-asked')
        ioutils.call_git('push --tags --signed=if-asked')

    @log.element('Package Publishing', log_entry=True)
    def _release_pypi(self, sign=True):
        # 🔒 🔐 🔏 🔓
        self.clear_build()
        self.build()
        if sign:
            self._sign_package()
        self._pypi_upload()
        self.clear_build()

    @log.clear()
    def _pypi_upload(self, mock=False):
        # Upload

        if True:
            rep = "https://test.pypi.org/legacy/" # FIXME put in config
        else:
            rep = self.meta['project_vcs']['pypi_repository']
        log.success('Uploading to '+rep)
        ioutils.call_twine('upload -s --repository-url '+rep+' ./build/dist/*')

    @log.element('Package Signing')
    def _sign_package(self):
        """
        Add the signatures to the package before upload
        """
        meta_key = self.meta['project_vcs']['release']['package_signing_key']
        if meta_key == '':
            log.error(Fore.RED +
                      config.OPEN_PADLOCK +
                      ' No key provided for package signing' +
                      Fore.RESET)
            return

        log.success('Signing the package with the key: ' + meta_key)

        try:
            for place in os.walk(join('.', 'build', 'dist')):
                for f in place[2]:
                    self._sign_file(join(place[0], f), meta_key)
        except CalledProcessError as ex:
            log.error(
                Fore.RED +
                config.OPEN_PADLOCK +
                ' Could not sign the package' +
                Fore.RESET)
            log.error(
                'The program will now stop, you can resume with: spvm publish pypi')
            log.error('When the issues are fixed')
            log.error(repr(ex))
            exit(1)
            return

        log.success(
            Fore.GREEN +
            config.PADLOCK +
            ' Package Signed with key: ' +
            meta_key +
            Fore.RESET)

    def _sign_file(self, file, meta_key):
        ioutils.call_gpg(
            ('-u ' + meta_key + ' ' if meta_key != '' else '') +
            '-b --yes -a -o ' + file + '.asc ' + file)

    def _release_docker(self):
        # TODO
        log.error('Not implemented')

    def print_version_status(self):
        """
        Print information about the version of the project
        And code versioning related
        """
        p = nice_print_value

        p('     Version Info', kc=Fore.GREEN)
        if not os.path.isdir(join(self.location, '.git')
                             ) or ioutils.call_git('branch') == '':
            print(
                Fore.RED +
                'No git repo initialized, versioning info not available' +
                Fore.RESET)
            p('')
            return

        tags = ioutils.call_git('tag --sort=-creatordate') + '\n' + 'None'

        p('Current Version:', self.get_version())
        p('Current branch:', ioutils.call_git('branch --no-color').split()[1])
        p('Current commit:', ioutils.call_git('rev-parse --short HEAD').strip())
        p('Commit count:', ioutils.call_git('rev-list --all --count').strip())
        p('Last Tag:', tags.split()[0])
        p('')

    def print_code_status(self, show=False):
        flakes, pep = self.check_code()
        p = nice_print_value

        p('\r     Code Status   ', kc=Fore.GREEN)

        vcf = Fore.LIGHTGREEN_EX if len(flakes) == 0 else Fore.LIGHTRED_EX
        vcp = Fore.LIGHTGREEN_EX if len(pep) == 0 else Fore.LIGHTRED_EX

        p('Errors & Warnings:', str(len(flakes)), vc=vcf)
        p('Conformity Problems:', str(len(pep)), vc=vcp)
        p('')
        if show:
            p('Errors & Warnings', kc=Fore.LIGHTYELLOW_EX)
            if len(flakes) == 0:
                print(Fore.GREEN + ' Nothing to display')
            for ew in flakes:
                print('> ' + Fore.RED + ew + Fore.RESET)
            p('')
            p('Conformity issues', kc=Fore.LIGHTYELLOW_EX)
            if len(pep) == 0:
                print(Fore.GREEN + ' Nothing to display')
            for ew in pep:
                print('> ' + Fore.RED + ew + Fore.RESET)

    def print_dependencies(self):
        p = nice_print_value

        p('     Project Dependencies', '(' +
          str(len(self.meta['project_requirements']['python_packages'])) +
            ')', kc=Fore.GREEN)
        for name in self.meta['project_requirements']['python_packages']:
            print(name)
        p('')

    @log.element(action='Calculating size...')
    def get_project_size(self):
        total_size = 0
        for dirpath, _, filenames in os.walk(self.location):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return sizeof_fmt(total_size)

    @log.clear()
    def print_project_status(self, show=False):
        """
        Print information about the project
        """
        p = nice_print_value
        sts = self.get_project_status()

        if sts != config.STATUS_PROJECT_INITIALIZED:
            print(
                Fore.RED +
                'Enable SPVM to print project status\nspvm init' +
                Fore.RESET)
            return

        nice_print_value('      Project Info', kc=Fore.GREEN)
        p('~~~~~~~~~~~~~~~~~~~~~~~~~~')
        p('Project Name:', self.get_name())
        p('Project Version:', self.get_version())
        p('Project Size:', self.get_project_size())
        p('Project SPVM Status:', sts)
        p('')
        p('~~~~~~~~~~~~~~~~~~~~~~~~~~')

        self.print_version_status()
        p('~~~~~~~~~~~~~~~~~~~~~~~~~~')
        self.print_code_status(show)
        p('~~~~~~~~~~~~~~~~~~~~~~~~~~')
        self.print_dependencies()
        p('~~~~~~~~~~~~~~~~~~~~~~~~~~')
        # self.print_project_meta()
        # print_docker_status()
        # print_

    # Userfull getters

    def get_version(self):
        return self.meta['project_vcs']['version']

    def get_name(self):
        return self.meta['project_info']['name']


def nice_print_value(key, value='', kc=Fore.BLUE, vc=Fore.LIGHTBLUE_EX):
    print(f'{kc}{key} {vc}{value}{Fore.RESET}')


def make_project_object(location):
    return PYVSProject(location)


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def check_script_version():
    version = spvm.__version__
    log.debug("SPVM version " + str(version))
    if config.scriptVersionCheckURL is None:
        log.warning("Nowhere to check last version")
        return

    lastver = urllib.request.urlopen(config.scriptVersionCheckURL).read()

    if version != lastver:
        log.warning("A new version of spvm is available (" +
                    lastver + ") you have version " + version)
        log.warning("Run pip install spvm --upgrade")
