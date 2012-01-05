#!/usr/bin/env python
"""Write the shotgunEvents/_version.py file

This script is used by the shotgunEvent Makefile.
It prints the version and writes shotgunEvents/_version.py

"""

import re
import os
import sys


# goto root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(1, os.getcwd())

from shotgunEvents import version


def main():
    try:
        delete_builtin_version()
        write_builtin_version()
    except Exception, e:
        sys.stderr.write(str(e) + '\n')
        return 1
    return 0


def _builtin_version_file(ext='py'):
    """Returns the path to shotgunEvents's builtin_version.py."""
    return os.path.join('src/shotgunEvents', '_version.%s' % ext)


def write_builtin_version():
    """Writes shotgunEvents/builtin_version.py

    There are two possible places from which we can get the version.

    First we check for the existence of a 'version' file at the
    root of the repository.  This file never exists in development
    sandboxes.  The 'version' file only exists in the tarballs
    created by 'git make-rpm' and contains nothing more than the
    output of 'git describe'.

    If the 'version' file does not exist, such as in a development
    sandbox, then the output of 'git describe' is parsed.

    """
    if os.path.exists('version'):
        fh = open('version', 'r')
        v = fh.read().strip()
        fh.close()

    elif os.path.isdir('.git'):
        v = version._git_describe_version()

    else:
        sys.stderr.write('error: cannot generate builtin_version.py\n'
                         'supply either a "version" file or a tagged git sandbox\n')
        v = '8.8.8' # +-INF

    # The Makefile uses the printed output
    print(v)

    # Write the file
    f = open(_builtin_version_file(), 'w')
    f.write("''' This file was generated automatically. Do not edit by hand.'''\n"
            'version = %r\n' % v)
    f.close()


def delete_builtin_version():
    """Deletes shotgunEvents/builtin_version.py."""
    for ext in ('py', 'pyc', 'pyo'):
        fn = _builtin_version_file(ext=ext)
        try:
            os.remove(fn)
        except OSError:
            pass



if __name__ == '__main__':
    sys.exit(main())
