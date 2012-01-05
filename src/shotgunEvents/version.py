"""Provides the current shotgunEvents version number"""

import re
import os
from dtk import utils

def version():
    """Return the builtin version or calculates the current version."""
    for ver in (_builtin_version, _git_describe_version):
        try:
            return ver()
        except VersionUnavailable:
            pass
    return 'unknown'

def _builtin_version():
    """Return the builtin version or throw a VersionUnavailable exception"""
    try:
        import _version  # pylint: disable = W0403,F0401
        return _version.version
    except ImportError:
        raise VersionUnavailable()


def _git_describe_version():
    """Inspect the shotgunEvents git repository and return the current version"""
    if not os.path.isfile('shotgunEvents.spec.in') or not os.path.isdir('.git'):
        raise VersionUnavailable('no source tree available')

    try:
        ver = utils.run_cmd(['git', 'describe', '--abbrev=7', '--match=v*'])
        ver = ver.rstrip() # pylint: disable = E1103
    except Exception, e:
        raise VersionUnavailable(str(e))

    if not re.match(r'^v[0-9]', ver):
        raise VersionUnavailable('%s: bad version' % ver)

    try:
        dirty = utils.run_cmd(['git', 'diff-index', '--name-only', 'HEAD'])
    except Exception, e:
        raise VersionUnavailable(str(e))

    if dirty:
        ver += '+++'
    if ver.startswith('v'):
        ver = ver[1:]
    return ver.replace('-', '.')


class VersionUnavailable(StandardError):
    """Thrown when a version lookup fails"""
    pass
