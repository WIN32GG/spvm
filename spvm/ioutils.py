import splogger as log
from subprocess import Popen, PIPE, CalledProcessError
import sys
import os
import shutil
import pytest
import requests
from colorama import Fore
import hashlib

from . import config

FNULL = open(os.devnull, 'w')


def call_with_stdout(args, ignore_err=False,
                     stdout=PIPE, inp=None, stderr=PIPE):
    with Popen(args.split(' ') if type(args) == str else args, stdout=stdout, stdin=PIPE if inp is not None else None, stderr=stderr) as proc:
        out, err = proc.communicate(input=inp)
        if proc.poll() != 0 and not ignore_err:
            log.error('Error from subprocess')
            if err is not None and err != '':
                print('err: ' + str(err), file=sys.stderr)
            if out is not None and out != '':
                print('out: ' + str(out), file=sys.stderr)
            raise CalledProcessError(proc.poll(), args)
        if log.get_verbose():
            if out is not None:
                print(out.decode())
            if err is not None:
                print(err.decode())

        if out is not None:
            return out.decode()


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
        call_pip('download -d ' + piptmp + ' ' + args)

    @log.element('Checking Packages')
    def check_packages(base_url='https://pypi.python.org/pypi/'):
        log.fine('Checking packages in: ' + piptmp)
        unchecked = 0
        for f in os.listdir(piptmp):
            try:
                f_ = piptmp + os.sep + f
                if not os.path.isfile(f_):
                    continue

                splited = f.split('-')
                log.debug('Checking ' + splited[0])
                package_info = query_get(
                    base_url + splited[0] + '/' + splited[1] + '/json')

                for f_info in package_info['releases'][splited[1]]:
                    if not os.path.isfile(os.path.join(
                            piptmp, f_info['filename'])):
                        continue

                    if md5(f_) != f_info['md5_digest']:
                        log.error('Hash do not match')
                        exit(1)
                    # log.success(Fore.GREEN+'Hash checked for '+f)

                    if not f_info['has_sig']:
                        log.debug(
                            Fore.YELLOW +
                            'No signature provided for ' +
                            f_info['filename'])  # FIXME throw?
                        unchecked += 1
                        continue

                    sig = query_get(f_info['url'] + '.asc', False)
                    log.debug(
                        'File: ' +
                        f_info['filename'] +
                        ' has signature:\n ' +
                        sig.decode())

                    # Check
                    q = '' if log.get_verbose() else ' --quiet'
                    try:
                        call_gpg(
                            '--no-default-keyring --keyring tmp.gpg' +
                            q +
                            ' --auto-key-retrieve --verify - ' +
                            f_,
                            inp=sig)  # FIXME Only use known keys?
                    except CalledProcessError as er:
                        if er.returncode == 1:
                            log.error(
                                Fore.RED +
                                config.OPEN_PADLOCK +
                                ' Invalid signature for ' +
                                f)
                            exit(1)
                        log.error(
                            'Could not check signature for ' + f + ' (' + repr(er) + ')')
                        unchecked += 1
                        continue

                    log.success(
                        Fore.GREEN +
                        config.PADLOCK +
                        ' File ' +
                        f +
                        ' is verified')

            except KeyboardInterrupt:
                exit(2)
            except SystemExit as e:
                raise e
            except BaseException as be:
                log.error(
                    Fore.RED +
                    config.OPEN_PADLOCK +
                    ' Failed to check ' +
                    f +
                    Fore.RESET)
                log.error(repr(be))
        log.warning(
            Fore.YELLOW +
            str(unchecked) +
            ' file(s) could not be verified')

    def clearup():
        shutil.rmtree(piptmp, True)
        log.success('Cleaned temporary download directory')

    @log.element('Install Packages')
    def install():
        for f in os.listdir(piptmp):
            if f.endswith('.whl'):
                call_pip('install ' + piptmp + os.path.sep + f)
                log.success('Installed ' + f.split('-')[0])

    clearup()
    download()
    check_packages()
    install()
    clearup()


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
    return call_with_stdout('git ' + args)


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
    fh = PIPE if verbose else FNULL
    return call_with_stdout('gpg ' + args, inp=inp, stdout=fh, stderr=fh)


def call_twine(args):
    return call_with_stdout('twine ' + args, stdout=None)


@log.element('Checking code...', log_entry=False)
def call_check(args, ignore=""):
    flakes = call_with_stdout('python -m pyflakes ' + args, ignore_err=True)
    pep8 = call_with_stdout(
        'python -m pycodestyle --ignore=' +
        ignore +
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
