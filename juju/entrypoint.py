#!/usr/bin/env python3

import os
import sys

# use modules from the lib directory - works under an assumption that
# the current directory is the top-level charm directory ($JUJU_CHARM_DIR)
sys.path.append('lib')

from juju.framework import Framework # noqa
from charm import Charm # noqa


try:
    from charmhelpers.core.hookenv import log
except (ImportError, ModuleNotFoundError):
    log = print


def get_juju_event_name():
    """Get an event name that caused a hook execution to happen.

    JUJU_HOOK_NAME or JUJU_ACTION_NAME are not used to support simulation of
    events from debugging sessions

    :return: an event name that caused a hook execution to happen
    :rtype: str
    """
    return os.path.basename(sys.argv[0])


def format_event_name(juju_event_name):
    """Formats a juju event name for use in Python

    :param str event_name: A Juju event name to format (e.g. config-changed)
    :return: A formatted event name (e.g. config_changed)
    :rtype: str
    """
    return juju_event_name.replace('-', '_')


def emit_charm_event(charm, event_name):
    """Emits a charm event based on a Juju event name

    :param charm: A charm instance to emit an event from
    :type charm: py:class:`juju.charm.Charm`
    :param str event_name: A Juju event name to emit on a charm
    """
    formatted_event_name = format_event_name(event_name)
    try:
        event_to_emit = getattr(charm.on, formatted_event_name)
    except AttributeError as e:
        msg = f"Event {formatted_event_name} not defined for {charm}"
        raise NotImplementedError(msg) from e

    log(
        f'Emitting a charm event based on a Juju event {event_to_emit},'
        f' event type {event_to_emit.event_type},'
        f' event kind {event_to_emit.event_kind}'
    )
    event_to_emit.emit()


def setup_memory_state(framework):
    """Sets up in-memory state (object hierarchy and observation etc.)

    It is likely that in most cases the hierarchy will be as follows:

    framework -> charm object -> member child objects (endpoints, components)

    In other words: there is a single charm object under the framework object
    with many child objects under the charm object.

    The charm class should hold all necessary setup code for the modeled
    application such as object instantiation, setup of observation of events
    (which may also be done in child classes).

    :param framework: A charm instance to emit an event from
    :type framework: py:class:`juju.framework.Framework`

    :return: The top-level charm object which is ready to process new Juju
             events from the current hook execution.
    :rtype: py:class:`juju.charm.Charm`
    """
    return Charm(framework)


def entrypoint():
    """An entry point for a charm.
    """

    # reuse the same db file as used by charm-helpers
    # TODO: if Juju uniter agent crashes after exit(0) from the charm code
    # the framework will commit the snapshot but Juju will not commit its
    # operation
    db_path = os.path.join(
        os.environ.get('CHARM_DIR', ''), '.unit-state.db')

    framework = Framework(data_path=db_path)

    charm = setup_memory_state(framework)

    framework.reemit()

    # process the Juju event relevant to the current hook execution
    juju_event_name = get_juju_event_name()
    emit_charm_event(charm, juju_event_name)

    framework.commit()
    framework.close()
