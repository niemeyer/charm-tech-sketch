#!/usr/bin/env python3

import sys
import os

# Use modules from the $JUJU_CHARM_DIR/lib directory. An absolute path
# is used as using a symlink like hooks/install -> ../lib/juju/main.py
# will result in $JUJU_CHARM_DIR/lib/juju being the first path stored
# in sys.path during hook execution which is undesirable.
# This happens because the directory containing a script is added to
# sys.path by the interpreter which gets resolved if it is a symlink.
del sys.path[0]
sys.path.insert(0, os.path.join(os.environ.get("JUJU_CHARM_DIR", ''), 'lib'))

from juju.entrypoint import entrypoint # noqa

if __name__ == '__main__':
    entrypoint()
