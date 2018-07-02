import splogger as log
import os.path
from os.path import join
import json
from colorama import Fore
import subprocess
from time import sleep
from shutil import rmtree
import docker
from threading import Thread
import re
from subprocess import CalledProcessError
import spvm

from . import config
from . import ioutils
from . import metautils


class PYVSProject(object):
    """
    A project object at the current cwd on which various actions are possible
    """

    def __init__(self, location=os.getcwd()):
        self.location = os.path.normpath(location)  # directory for project
        if os.path.isdir(self.location):
            os.chdir(self.location)
            log.debug("cwd switched: " + self.location)
        log.debug("New  project instance @ " + self.location)
        log.debug("Project status is: " + str(self.get_project_status()))
        self.projectMetaFile = join(self.location, config.metaFileName)
        self.maybe_load_meta()
        if self.meta is not None:
            metautils.check_project_meta(self.meta)
            self.save_project_info()

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
                    self.location).lower()),
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

        # if os.path.isdir(dep):
        #     log.warning(
        #         "Adding local dependency, this may break when releasing the project")

        # if os.path.isfile(dep):
        #     log.warning(
        #         "Got a file as dependency name, using as requirements.txt")
        #     supp_args = '-r '

        try:
            ioutils.install_packages('dep', True)
        except CalledProcessError as ex:
            log.error("Pip call failed with code " + str(ex.returncode))
            log.error("Does the dependency exist or is something broken?")
            return

        self.meta['project_requirements']['python_packages'].append(dep)

    def maybe_load_meta(self):
        """
        If a metaFile exists, it will be loaded
        """
        self.meta = None
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
        log.error('Not implemented: remove dependency')

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
        # ioutils.call_pip(
        #     'install ' +
        #     " ".join(
        #         self.meta['project_requirements']['python_packages']) +
        #     " --upgrade")

        ioutils.install_packages(
            " ".join(
                self.meta['project_requirements']['python_packages']))

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

    @log.element('🔧 Code repair', log_entry=True)
    def repair(self):
        ioutils.call_python('autopep8', '-ra --in-place .')

    def populate_init(self):
        """ Populate the <proj>/__init__.py with meta info """
        log.debug('Populating the __init__')
        init_path = join(self.get_name().lower(), '__init__.py')

        with open(init_path, 'r') as fh:
            init_file = fh.read()

        def replace_or_create(key, value):
            nonlocal init_file
            pattern = "^" + key + " ?= ?.*"  # key at the beginning of the line
            preg = re.compile(pattern, re.M)

            if len(preg.findall(init_file)) == 0:
                init_file += '\n' + key + ' = "' + value + '"'
                log.debug(key + ' not found in init')
            else:
                init_file = preg.sub(key + ' = "' + value + '"', init_file)
                log.debug('Found ' + key + ' and replaced with ' + value)

        replace_or_create('__name__', self.meta['project_info']['name'])
        replace_or_create('__version__', self.meta['project_vcs']['version'])
        replace_or_create(
            '__author__',
            self.meta['project_authors'][0]['name'])
        replace_or_create('__url__', self.meta['project_info']['url'])
        replace_or_create(
            '__email__',
            self.meta['project_authors'][0]['email'])

        os.remove(init_path)
        with open(init_path, 'w+') as fh:
            fh.write(init_file)

        log.success('Populated __init__.py')

    # RELEASE #

    def detect_publish_context(self):
        """
        Indicates where the code will be pushed
        Inspects the config map and project's meta
        """

        context = [False,  # Git
                   False,  # pypi
                   False]  # docker

        mock = config.config['mock']
        has_pypi_rep = self.meta['project_vcs']['pypi_repository'] != ''
        has_docker_rep = self.meta['project_vcs']['docker_repository'] != ''
        has_dockerfile = os.path.isfile(join(self.location, 'Dockerfile'))

        if not mock:
            context[0] = True

        if has_pypi_rep:
            context[1] = True

        if has_docker_rep and has_dockerfile:
            context[2] = True

        return context

    def release(self, kind='pass'):
        """
        Starts a release pipeline
        """

        if self.get_project_status() != config.STATUS_PROJECT_INITIALIZED:
            log.error('The project is not initialized')
            log.error('Run spvm init first')
            exit(1)

        pipeline = []
        log.fine('Calculating release pipeline')

        pipeline.append(self.clear_build)
        if config.config['update']:
            pipeline.append(self.update_dependencies)
        if config.config['repair']:
            pipeline.append(self.repair)
        pipeline.append(self.check_project)
        if config.config['test']:
            pipeline.append(self.run_test)
        pipeline.append(self.up_version)
        pipeline.append(self.populate_init)
        pipeline.append(self.install_setup)
        pipeline.append(self.publish)

        NO = Fore.RED + 'NO' + Fore.RESET
        MOCK = (
            '' if not config.config['mock'] else ' ' +
            Fore.LIGHTYELLOW_EX +
            '(MOCK)' +
            Fore.RESET)
        YES = Fore.GREEN + 'YES' + Fore.RESET + MOCK

        publish_context = self.detect_publish_context()
        pipeline.append(Fore.CYAN + "     - Git Publish: " +
                        (YES if publish_context[0] else NO))
        pipeline.append(Fore.CYAN + "     - PyPi Publish: " +
                        (YES if publish_context[1] else NO))
        pipeline.append(Fore.CYAN +
                        "     - Docker Publish: " +
                        (YES if publish_context[2] else NO))

        log.success('Release pipeline is: ')
        for f in pipeline:
            if isinstance(f, str):
                log.success(f)
                continue
            log.success(" -> " + f.__name__)
        if not config.config['mock']:
            log.warning(
                Fore.YELLOW +
                'The mock mode is not activated, this is for real !' +
                Fore.RESET)
        if config.config['ask']:
            input('Press Enter to continue')
        for f in pipeline:
            if isinstance(f, str) or f.__name__ == 'wrapper':
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
            if config.config['check']:
                log.error(
                    Fore.RED +
                    'This error is fatal, to make it non-fatal, use -n')
                exit(1)

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
        rmtree('./' + self.get_name() + '.egg-info', True)

    @log.element('Publishing')
    def publish(self, git=True, pypi=True, docker=True):
        context = self.detect_publish_context()
        git = git and context[0]
        pypi = pypi and context[1]
        docker = docker and context[2]

        if git and not config.config['mock']:
            self._release_git()
        if pypi:
            self._release_pypi()
        if docker:
            self._release_docker()

    @log.element('Git Publishing', log_entry=True)
    def _release_git(self):
        # Commit version
        commit_message = self.meta['project_vcs']['release']['commit_template'].replace(
            '%s', self.meta['project_vcs']['version']).replace('"', '\\"').strip()
        log.debug('Commit message: ' + commit_message)
        ioutils.call_git('add .')

        key = self.meta['project_vcs']['release']['git_signing_key']
        if key != '':
            log.success(
                Fore.GREEN +
                config.PADLOCK +
                'Commit will be signed with ' +
                key)

        ioutils.call_commit(commit_message, key=key)

        # Tag version
        tag = self.meta['project_vcs']['release']['tag_template'].replace(
            '%s', self.meta['project_vcs']['version'])
        ioutils.call_git('tag ' + ('' if key == '' else '-u ' + key + ' ') +
                         '-m ' + tag + ' ' + tag)
        log.success('Tagged: ' + tag)

        # Push
        log.success(
            'Pushing to ' +
            self.meta['project_vcs']['code_repository'])
        ioutils.call_git('push --signed=if-asked')
        log.success('Pushing tags')
        ioutils.call_git('push --tags --signed=if-asked')

    @log.element('Package Release', log_entry=True)
    def _release_pypi(self, sign=True):
        # 🔒 🔐 🔏 🔓
        if self.meta['project_vcs']['pypi_repository'] == '':
            log.success('Nothing to push to pypi')
            return
        self.clear_build()
        self.build()
        if sign:
            self._sign_package()
        self._pypi_upload()
        self.clear_build()

    @log.clear()
    def _pypi_upload(self):
        mock = config.config['mock']

        # Upload
        if mock:
            rep = "https://test.pypi.org/legacy/"  # FIXME put in config
        else:
            rep = self.meta['project_vcs']['pypi_repository']
        log.success('Uploading to ' + rep)
        ioutils.call_twine(
            'upload --repository-url ' +
            rep +
            ' ./build/dist/*')

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

    @log.element('Docker Publishing', log_entry=True)
    def _release_docker(self):
        log.success('Building Docker Image')
        client = docker.from_env()
        log.debug(json.dumps(client.version(), indent=4))

        status = {}

        def _show_docker_progress(obj):
            nonlocal status

            if 'errorDetail' in obj:
                log.error(Fore.RED +
                          'Error: ' +
                          str(obj['errorDetail']['message']) +
                          Fore.RESET)
                raise docker.errors.DockerException(
                    obj['errorDetail']['message'])

            if 'stream' in obj:
                for line in obj['stream'].split('\n'):
                    if line == '':
                        continue
                    log.success(line.strip())
                status.clear()
                return

            if 'status' in obj:
                if 'id' not in obj:
                    log.success(obj['status'])
                    return

                s = obj['id'].strip() + ' ' + obj['status'] + '\t'
                if 'progress' in obj:
                    s += obj['progress']

                if obj['id'] not in status:
                    status[obj['id']] = {'index': len(status) + 1, 'str': s}
                    print(s)
                    return

                status[obj['id']]['str'] = s
                print('\033[F' * (len(status) + 1))
                for e in status:
                    print('\033[K' + status[e]['str'])
                # print('\n'*i, end = '')

        # FIXME choose dockerfile
        rep = self.meta['project_vcs']['docker_repository']
        log.success('Image repo: ' + rep)
        g = client.build(tag=rep, path='.', dockerfile='Dockerfile')
        for line in g:
            _show_docker_progress(json.loads(line.decode()))

        if config.config['mock']:
            log.warning(Fore.YELLOW + 'Mock mode: not pushing' + Fore.RESET)
            return
        log.success('Pushing image')
        for line in client.push(rep, stream=True):
            _show_docker_progress(json.loads(line.decode()))

    # PRINT INFOS #

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


def nice_print_value(key, value='', kc=Fore.WHITE, vc=Fore.LIGHTBLUE_EX):
    print(f'{kc}{key} {vc}{value}{Fore.RESET}')


def make_project_object(location):
    return PYVSProject(location)


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

# version checking


def check_script_version():

    def _retreive_version():
        try:
            version = spvm.__version__
            log.debug("SPVM version " + str(version))
            lastver = ioutils.query_get(
                "https://pypi.org/pypi/spvm/json")['info']['version']
            log.debug('Last version is ' + lastver)
            if version != lastver:
                log.warning("A new version of spvm is available (" +
                            lastver + ") you have version " + version)
                log.warning("Run pip install spvm --upgrade")
        except BaseException:
            log.warning('Could not get last version')

    Thread(target=_retreive_version, daemon=True).start()
