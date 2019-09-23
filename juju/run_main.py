#!/usr/bin/env python3

import sys

# use modules from the lib directory - works under an assumption that
# the current directory is the top-level charm directory ($JUJU_CHARM_DIR)
sys.path.append('lib')

from juju.entrypoint import entrypoint # noqa

if __name__ == '__main__':
    entrypoint()
