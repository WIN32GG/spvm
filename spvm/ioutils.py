import splogger as log
from subprocess import Popen, PIPE, CalledProcessError
import sys
import os
import shutil
import pytest
import requests
from colorama import Fore
import hashlib
from os.path import join
import fnmatch
import gnupg
import json
import getpass
from .config import NoFailReadOnlyDict
from datetime import datetime

from . import config

FNULL = open(os.devnull, 'w')


def call_with_stdout(args, ignore_err=False,
                     stdout=PIPE, inp=None, stderr=PIPE):
    with Popen(args.split(' ') if type(args) == str else args, stdout=stdout, stdin=PIPE if inp is not None else None, stderr=stderr) as proc:
        out, err = proc.communicate(input=inp)
        if proc.poll() != 0 and not ignore_err:
            if log.get_verbose():
                log.error('Error from subprocess')
                if err is not None and err != '':
                    print('err: ' + str(err), file=sys.stderr)
                if out is not None and out != '':
                    print('out: ' + str(out), file=sys.stderr)
            raise CalledProcessError(proc.poll(), args, out, err)

        if log.get_verbose():
            log.debug('Output of '+repr(args))
            if out is not None:
                print(out.decode())
            if err is not None:
                print(err.decode())

        if out is not None:
            return out.decode()

def read_logins():
    if os.path.isfile('.logins'):
        log.success(Fore.GREEN+config.PADLOCK+" Found crypted logins file"+Fore.RESET)
        gpg = gnupg.GPG()

        cr = None
        with open('.logins', 'r') as fh:
            cr = fh.read()

        cr = json.loads(gpg.decrypt(cr).data)
        log.success('Logins creation time: '+cr['creation_date'])
        log.success(Fore.GREEN+config.OPEN_PADLOCK+' Got logins for '+', '.join(cr['data'])+Fore.RESET)
        
        return NoFailReadOnlyDict(cr['data'], default = None)
    return None

def get_date(): 
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ask_logins():
    if os.path.isfile('.logins'):
        log.warning(Fore.YELLOW+'The logins file already exist, overwrite it ?'+Fore.RESET)
        yes = input('Enter \'yes\' to overwrite: ')
        if yes != 'yes':
            return

    cr = {
        'creation_date': get_date(),
        'data': {}
    }

    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    print(Fore.YELLOW+'\tLogins configuration\n'+Fore.RESET)
    print(Fore.GREEN+'You are going to be asked you credentials for this project\n'
          +'They will be stored under .logins crypted with AES and .logins append to .gitignore'+Fore.RESET)
          
    yes = input('Do you wish to continue? (Enter "yes" to continue): ')
    if yes != 'yes':
        log.error('Cancelled')
        return
    print('')

    def ask_login(arr, component):
        print(Fore.LIGHTGREEN_EX+'\nNow configuring login for: '+Fore.GREEN+component)
        print(Fore.RED+"Leave blank if Not Applicable"+Fore.RESET)
        login = input('Login: ')
        if login == '':
            return
        password = getpass.getpass()
        arr[component] = {'login': login, 'password': password}
    
    
    # print(Fore.RED+'Git login: '+Fore.CYAN+' Git login will no be asked, you are expected to use a credential helper for git '
    # +'if you wish to automatically push'+Fore.RESET)
    # print(Fore.GREEN+'This setup can launch the git credential helper for you <3'
    # +'\n'+Fore.YELLOW+'WARNING: The credentials are stored in clear text'+Fore.RESET)
    # yes = input('Save git credentials? (Enter "yes" to continue): ')
    # if yes == 'yes':
    #     call_git('config credential.helper store')
    #     call_git('push')

    ask_login(cr['data'], 'git')
    ask_login(cr['data'], 'pypi')
    ask_login(cr['data'], 'docker')

    gpg = gnupg.GPG()
    gpg.encrypt(json.dumps(cr), (), symmetric=True, output='.logins')

    try:
        call_git('check-ignore .logins')
    except CalledProcessError:
        with open('.gitignore', 'a') as fh:
            fh.write('\.logins')
        log.success('Appened .logins to .gitignore')

def call_python(module, args, stdout=None, stderr=None):
    mod = [] if module == '' else ['-m', module]
    return call_with_stdout(
        [sys.executable, *mod, *args.split(' ')], stdout=stdout, stderr=stderr)


def copy(a, b):
    assert os.path.isfile(a)
    with open(a, 'r') as ffh:
        with open(b, 'w+') as tfh:
            tfh.write(ffh.read())


def query_get(url, make_json=True):
    req = requests.get(url)
    if not req.ok:
        raise ValueError('Request Failed with code: ' + str(req.status_code))
    if make_json:
        return req.json()
    return req.content


def install_packages(args, check_signatures=None):
    if check_signatures is None:
        check_signatures = config.config['signed']

    if not check_signatures:
        call_pip('install ' + args, verbose=True)
        return

    piptmp = 'piptmp'

    @log.element('Download Packages', log_entry=True)
    def download():
        for pack in args.split(' '):
            log.set_additional_info(pack)
            call_pip('download -d ' + piptmp + ' ' + pack)

    @log.element('Checking Packages')
    def check_packages(base_url='https://pypi.python.org/pypi/'):
        log.fine('Checking packages in: ' + piptmp)
        unchecked = 0
        for f in os.listdir(piptmp):
            try:
                log.set_additional_info(f)
                f_ = piptmp + os.sep + f
                if not os.path.isfile(f_):
                    continue

                splited = f.split('-')
                log.debug('Checking ' + splited[0])
                package_info = query_get(base_url + splited[0] + '/' + splited[1] + '/json')

                for f_info in package_info['releases'][splited[1]]:
                    if not os.path.isfile(os.path.join(piptmp, f_info['filename'])):
                        continue

                    if md5(f_) != f_info['md5_digest']:
                        log.error('Hash do not match')
                        exit(1)
                    # log.success(Fore.GREEN+'Hash checked for '+f)

                    if not f_info['has_sig']:
                        log.debug(Fore.YELLOW + 'No signature provided for ' + f_info['filename'])  # FIXME throw?
                        unchecked += 1
                        continue

                    sig = query_get(f_info['url'] + '.asc', False)
                    log.debug('File: ' + f_info['filename'] + ' has signature:\n ' + sig.decode())

                    # Check
                    q = '' if log.get_verbose() else ' --quiet'
                    try:
                        call_gpg('--no-default-keyring --keyring tmp.gpg' + q + ' --auto-key-retrieve --verify - ' + f_, inp=sig)  # FIXME Only use known keys?
                    except CalledProcessError as er:
                        if er.returncode == 1:
                            log.error(Fore.RED + config.OPEN_PADLOCK + ' Invalid signature for ' + f)
                            exit(1)

                        log.error('Could not check signature for ' + f + ' (' + repr(er) + ')')
                        unchecked += 1
                        continue

                    log.success(Fore.GREEN + config.PADLOCK + ' File ' + f + ' is verified')

            except KeyboardInterrupt:
                exit(2)
            except SystemExit as e:
                raise e
            except BaseException as be:
                log.error(Fore.RED + config.OPEN_PADLOCK + ' Failed to check ' + f + Fore.RESET)
                log.error(repr(be))
        log.warning(Fore.YELLOW + str(unchecked) + ' file(s) could not be verified')

    def clearup():
        shutil.rmtree(piptmp, True)
        log.success('Cleaned temporary download directory')

    @log.element('Install Packages')
    def install():
        for f in os.listdir(piptmp):
            if f.endswith('.whl'):
                log.set_additional_info(f)
                call_pip('install ' + piptmp + os.path.sep + f)
                # log.success('Installed ' + f.split('-')[0])

    clearup()
    download()
    check_packages()
    install()
    clearup()

def match_gitignore(name, ignore):
    for pattern in ignore.split(','):
        if fnmatch.fnmatch(name, pattern):
            return True
    return False

def call_pip(args, verbose=log.get_verbose()):
    fh = PIPE if verbose else FNULL
    return call_python('pip', args, stdout=fh, stderr=fh)


@log.clear()
def call_pytest(args):
    o = pytest.main(args.split(' '))
    if o != 0:
        raise CalledProcessError(o, 'pytest ' + args)


@log.clear()
def call_git(args):
    if type(args) == str:
        args = 'git '+args
    else: # array
        args = ['git', *args]

    return call_with_stdout(args)


@log.element('Commiting', log_entry=True)
def call_commit(message, key=''):
    args = ['git', 'commit', '--no-edit']
    if key != '':
        args.append('-S' + key)
    args.append('-m')
    args.append(message)

    return call_with_stdout(args)


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def call_gpg(args, inp=None, verbose=log.get_verbose()):
    log.error('Call to gpg deprecated')
    fh = PIPE if verbose else FNULL
    return call_with_stdout('gpg ' + args, inp=inp, stdout=fh, stderr=fh)


def call_twine(args):
    return call_with_stdout('twine ' + args, stdout=None) # FIXME import and use


@log.element('Checking code', log_entry=False)
def call_check(args, ignore="", exclude=''):
    flakes = ''
    for dirname, _, files in os.walk(args):
        if os.path.ismount(dirname) or os.path.islink(dirname):
            log.warning('Ignored mounted/link directory: '+dirname)
            continue

        if match_gitignore(dirname, exclude):
            continue

        for f in files:
            if not f.endswith('.py'):
                continue
            log.debug('Check: '+f)
            log.set_additional_info(f)
            if match_gitignore(join(dirname, f), exclude):
                continue 
            
            flak = call_with_stdout('python -m pyflakes ' + join(dirname, f), ignore_err=True)
            if flak is not None:
                flakes += flak

    # flakes = call_with_stdout('python -m pyflakes ' + args, ignore_err=True)
    pep8 = call_with_stdout(
        'python -m pycodestyle --ignore=' +
        ignore +     
        ' ' +
        ('' if exclude == '' else '--exclude='+exclude) +
        ' ' +
        args,
        ignore_err=True)
    return flakes, pep8


@log.clear()
def input_with_default(prompt, default=None, rtype=str):
    assert type(rtype) == type
    if default is None:
        default = rtype()

    while True:
        res = input(f'{prompt} ({default}): ')
        if res == 'null' or res == 'none':
            return ''
        if res is '':
            return default

        try:
            return rtype(res)
        except ValueError:
            log.error('An input of type ' + rtype.__name__ + " is expected")


__all__ = [
    'input_with_default',
    'call_check',
    'call_git',
    'call_pytest',
    'call_pip',
    'copy',
    'call_python',
    'call_with_stdout']
