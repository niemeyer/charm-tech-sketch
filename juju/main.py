#!/usr/bin/env python3

import os
import sys
import yaml

# Use modules from the $JUJU_CHARM_DIR/lib directory. An absolute path
# is used as using a symlink like hooks/install -> ../lib/juju/main.py
# will result in $JUJU_CHARM_DIR/lib/juju being the first path stored
# in sys.path during hook execution which is undesirable.
# This happens because the directory containing a script is added to
# sys.path by the interpreter which gets resolved if it is a symlink.
del sys.path[0]
sys.path.insert(0, os.path.join(os.environ.get("JUJU_CHARM_DIR", ''), 'lib'))

import juju.framework # noqa

from juju.framework import ( # noqa
    Framework,
    Event,
    BoundEvent
)
from charm import Charm # noqa

# Reuse the same db file as used by charm-helpers.
DB_PATH = os.path.join(
    os.environ.get('CHARM_DIR', ''), '.unit-state.db')

try:
    from charmhelpers.core.hookenv import log
except (ImportError, ModuleNotFoundError):
    log = print


def load_metadata():
    with open('metadata.yaml') as f:
        metadata = yaml.load(f)
    return metadata


def get_charm_endpoints():
    """Get a list of endpoints from the charm metadata.
    """
    metadata = load_metadata()
    charm_endpoints = list()
    for endpoint_type in ['provides', 'requires', 'peers']:
        endpoints = metadata.get(endpoint_type)
        if endpoints:
            charm_endpoints.extend(endpoints)
    return charm_endpoints


def setup_hooks():
    """Set up hooks for supported events.

    Whether a charm can handle an event or not can be determined by
    introspecting which events are bound to it.
    """

    relation_events = list()
    for endpoint in get_charm_endpoints():
        relation_events.extend([
            f'{endpoint}_relation_{t}'
            for t in ['joined', 'changed', 'departed', 'broken']
        ])

    log(f'Discovered relation events from charm metadata: {relation_events}')

    # Get core event names that CharmBase knows about.
    core_events = [event_name for event_name, instance
                   in juju.charm.CharmEventsBase.__dict__.items()
                   if type(instance) == Event]

    log(f'Discovered core charm events: {core_events}')

    # Discover Juju events supported by the charm using reflection.
    supported_juju_events = [
        event_name for event_name in dir(Charm.on)
        if (type(getattr(Charm.on, event_name)) == BoundEvent
            and (event_name in relation_events or event_name in core_events))
    ]
    log('Discovered Juju events supported by the charm by'
        f' introspecting it: {supported_juju_events}')

    # Create symlinks to "install" which may be either a copy of main.py
    # (which calls the entrypoint function) or a symlink to it. Note
    # that it is important to avoid creating a recursive symlink.
    supported_juju_events.remove('install')

    for event_name in supported_juju_events:
        event_hook_path = f'hooks/{event_name.replace("_", "-")}'
        if os.path.exists(event_hook_path):
            log(f'Removing an old symlink named {event_hook_path}')
            os.unlink(event_hook_path)
        log(f'Creating a new symlink named {event_hook_path} to hooks/install')
        os.symlink('install', event_hook_path)


def emit_charm_event(charm, event_name):
    """Emits a charm event based on a Juju event name.

    charm -- A charm instance to emit an event from.
    event_name -- A Juju event name to emit on a charm.
    """
    formatted_event_name = event_name.replace('-', '_')
    try:
        event_to_emit = getattr(charm.on, formatted_event_name)
    except AttributeError as e:
        msg = f"event {formatted_event_name} not defined for {charm}"
        raise NotImplementedError(msg) from e

    log(f'Emitting Juju event {event_name}')
    event_to_emit.emit()


def main():
    """An entry point for a charm.

    Sets up in-memory state (object hierarchy and observation etc.).

    The expected hierarchy is a single charm object under the framework
    object with many child objects under the charm object:

    framework -> charm object -> member child objects (endpoints, components)

    The charm class should hold all necessary setup code for the modeled
    application such as object instantiation, setup of observation of events
    (which may also be done in child classes).

    """

    # TODO: If Juju unit agent crashes after exit(0) from the charm code
    # the framework will commit the snapshot but Juju will not commit its
    # operation.
    framework = None
    try:
        framework = Framework(data_path=DB_PATH)

        # Set up charm-specific in-memory state.
        charm = Charm(framework, 0)

        framework.reemit()

        juju_event_name = os.path.basename(sys.argv[0])

        # Set up hooks on initial install or charm upgrade. Note that if
        # a charm is force-upgraded this will only be called after
        # upgrade-charm is executed.
        if juju_event_name in ['install', 'upgrade-charm']:
            setup_hooks()

        # Process the Juju event relevant to the current hook execution
        # JUJU_HOOK_NAME or JUJU_ACTION_NAME are not used to support simulation
        # of events from debugging sessions.
        emit_charm_event(charm, juju_event_name)

        framework.commit()
    finally:
        if framework:
            framework.close()


if __name__ == '__main__':
    main()
