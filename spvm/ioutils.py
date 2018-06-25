import splogger as log
from subprocess import Popen, check_call, PIPE, CalledProcessError
import sys
import os


def call_with_stdout(args, ignore_err=False, stdout=PIPE):
    with Popen(args.split(' ') if type(args) == str else args, stdout=stdout) as proc:
        out, err = proc.communicate()
        if proc.poll() != 0 and not ignore_err:
            log.error('Error from subprocess')
            if err is not None and err != '':
                print('err: ' + str(err), file=sys.stderr)
            if out is not None and out != '':
                print('out: ' + str(out), file=sys.stderr)
            raise CalledProcessError(proc.poll(), args)
        if out is not None:
            return out.decode()


def call_python(module, args, stdout=None):
    mod = [] if module == '' else ['-m', module]
    return call_with_stdout(
        [sys.executable, *mod, *args.split(' ')], stdout=stdout)


def copy(a, b):
    assert os.path.isfile(a)
    with open(a, 'r') as ffh:
        with open(b, 'w+') as tfh:
            tfh.write(ffh.read())


@log.clear()
def call_pip(args):
    return call_python('pip', args)


@log.clear()
def call_pytest(args):
    return call_python('pytest', args)


@log.clear()
def call_git(args):
    return call_with_stdout('git ' + args)


@log.element('Commiting')
def call_commit(message):
    return call_with_stdout(
        ['git', 'commit', '--no-edit', '-m', message])


def call_gpg(args):
    return call_with_stdout('gpg ' + args)


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
        if res is 'null' or res is 'none':
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
