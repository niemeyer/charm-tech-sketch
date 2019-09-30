#!/usr/bin/env python3

import unittest
import logging
import os
import sys
import subprocess

from unittest.mock import (
    patch,
)

JUJU_CHARM_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'charms/main'
)

# change cwd for the current process to the test charm directory
os.chdir(JUJU_CHARM_DIR)
os.environ['JUJU_CHARM_DIR'] = JUJU_CHARM_DIR

del sys.path[0]
sys.path.insert(0, os.path.join(JUJU_CHARM_DIR, 'lib'))

import juju.charm # noqa
import juju.main as main # noqa

import charm # noqa
from charm import Charm # noqa

from juju.framework import ( # noqa
    Event,
    BoundEvent,
)


logger = logging.getLogger()
logger.level = logging.DEBUG
stream_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stream_handler)


class SymlinkTargetError(Exception):
    pass


def get_charm_event_names(charm_type):
    """Gets event names for a given charm class.

    charm_type - a charm class to get events for.
    """
    return [
        event_name for event_name
        in dir(charm_type.on)
        if type(getattr(charm_type.on, event_name)) == BoundEvent
    ]


class TestMain(unittest.TestCase):

    MAIN_PY_RELPATH = '../lib/juju/main.py'

    @classmethod
    def _clear_symlinks(cls):
        r, _, files = next(os.walk(os.path.join(JUJU_CHARM_DIR, 'hooks')))
        for f in files:
            if f != 'install' or not os.path.islink(os.path.join(r, f)):
                os.unlink(os.path.join(r, f))
            else:
                install_link = os.path.join(r, f)
                if os.readlink(install_link) != cls.MAIN_PY_RELPATH:
                    raise SymlinkTargetError('"install" link does not point to'
                                             f' {cls.MAIN_PY_RELPATH}')

    @classmethod
    def _clear_unit_db(cls):
        if os.path.exists(main.DB_PATH):
            os.unlink(main.DB_PATH)

    def setUp(self):
        self._clear_unit_db()
        self._clear_symlinks()

    def tearDown(self):
        self._clear_unit_db()
        charm.Charm.reset_type()
        self._clear_symlinks()

    def test_event_reemitted(self):
        charm.Charm.ConfigChangedEvent_defer = True

        with patch('sys.argv', ['config-changed']):
            main.main()
            self.assertEqual(Charm.ConfigChangedEvent_count_called, 1)
            self.assertEqual(Charm.ConfigChangedEvent_count_deferred, 1)
            self.assertEqual(Charm.ConfigChangedEvent_defer, False)

        with patch('sys.argv', ['update-status']):
            main.main()
            # re-emit should pick the deferred config-changed
            self.assertEqual(Charm.ConfigChangedEvent_count_called, 2)
            self.assertEqual(Charm.ConfigChangedEvent_count_deferred, 1)
            self.assertEqual(Charm.ConfigChangedEvent_defer, False)

    def test_all_base_events_handled(self):
        # infer supported "base" events from the base charm class
        base_events = {event_name: instance for event_name, instance
                       in juju.charm.CharmEventsBase.__dict__.items()
                       if type(instance) == juju.framework.Event}

        logger.debug(f'Expected events {base_events.keys()}')

        # simulate hook executions for every event
        for event_name, event in base_events.items():
            with patch('sys.argv', [event_name]):
                main.main()
                print(f'Event type: {event.event_type.__name__}')

                event_type_name = event.event_type.__name__
                count_called = getattr(
                    charm.Charm, f'{event_type_name}_count_called')

                print(f'{event_type_name}_count_called: {count_called}')

                self.assertEqual(count_called, 1)

        logger.debug(f'Events types observed {Charm.events_types_observed}')

        event_types = {e.event_type for e in base_events.values()}
        self.assertEqual(Charm.events_types_observed, event_types)

    def test_event_not_implemented(self):
        """Make sure Juju events are not silently skipped.
        """
        with patch('sys.argv', ['not-implemented-event']):
            self.assertRaises(NotImplementedError, main.main)

    def test_setup_hooks(self):

        event_hooks = [f'hooks/{e.replace("_", "-")}'
                       for e in get_charm_event_names(Charm)
                       if e != 'install']

        install_link_path = os.path.join(JUJU_CHARM_DIR, 'hooks/install')

        # The symlink is expected to be present in the source tree.
        self.assertTrue(os.path.exists(install_link_path))
        # It has to point to main.py in the lib directory of the charm.
        self.assertEqual(os.readlink(install_link_path), self.MAIN_PY_RELPATH)

        def _assess_setup_hooks(event_name):
            event_hook = os.path.join(JUJU_CHARM_DIR, f'hooks/{event_name}')
            # Simulate a fork + exec of a hook from a unit agent.
            subprocess.check_call(event_hook,
                                  env={'JUJU_CHARM_DIR': JUJU_CHARM_DIR})

            r, _, files = next(os.walk(os.path.join(JUJU_CHARM_DIR, 'hooks')))

            self.assertTrue(event_name in files)

            for event_hook in event_hooks:
                print(f'event_hook: {event_hook}')
                self.assertTrue(os.path.exists(event_hook))
                self.assertEqual(os.readlink(event_hook), 'install')
                self.assertEqual(os.readlink('hooks/install'),
                                 self.MAIN_PY_RELPATH)

        # Assess 'install' first because upgrade-charm or other
        # events cannot be handled before install creates symlinks for them.
        events_to_assess = ['install', 'start', 'config-changed',
                            'leader-elected', 'upgrade-charm', 'update-status']

        for event_name in events_to_assess:
            _assess_setup_hooks(event_name)


if __name__ == "__main__":
    unittest.main()
