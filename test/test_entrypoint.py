#!/usr/bin/python3

import unittest
import logging
import inspect
import tempfile
import os
import sys
import shutil
import types
import yaml

import juju.charm
from juju.framework import (
    Event,
    BoundEvent,
)

from unittest.mock import (
    patch,
    call,
)

from pathlib import Path


logger = logging.getLogger()
logger.level = logging.DEBUG
stream_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stream_handler)


def import_code(code, module_name):
    """Dynamically import code into a module with a given name.
    """
    dynamic_module = types.ModuleType(module_name)
    # Execute the provided code in the context of the
    # file-less module created dynamically in memory
    exec(code, dynamic_module.__dict__)
    sys.modules[module_name] = dynamic_module


# Import a dynamic module called "charm" with a Charm class stub
import_code('''
import juju.charm
class Charm(juju.charm.CharmBase): pass
''', 'charm')

# Import entrypoint code after the module called "charm" becomes importable
import juju.entrypoint as ep # noqa


def get_charm_event_names(charm_type):
    """Gets event names for a given charm class.

    charm_type - a charm class to get events for.
    """
    return [
        event_name for event_name
        in dir(charm_type.on)
        if type(getattr(charm_type.on, event_name)) == BoundEvent
    ]


class TestEntrypoint(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        db_path_patch = patch('juju.entrypoint.DB_PATH',
                              os.path.join(self.tmpdir, '.unit-state.db'))
        db_path_patch.start()
        self.addCleanup(db_path_patch.stop)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_event_reemitted(self):
        # note: class variables are modified because Charm instances
        # are not preserved across simulated hook executions
        class CharmConfigDeferrer(juju.charm.CharmBase):
            defer = True
            count_called = 0
            count_deferred = 0

            def __init__(self, framework, key):
                super().__init__(framework, key)
                self.framework.observe(self.on.config_changed, self)

            def on_config_changed(self, event):
                logger.debug(f'In {inspect.stack()[0].function}')
                if self.defer:
                    event.defer()
                    type(self).defer = False
                    type(self).count_deferred += 1
                type(self).count_called += 1

        with patch('juju.entrypoint.Charm', CharmConfigDeferrer):
            with patch('sys.argv', ['config-changed']):
                ep.entrypoint()
                self.assertEqual(CharmConfigDeferrer.count_called, 1)
                self.assertEqual(CharmConfigDeferrer.defer, False)

            # update-status does not have a handler but config-changed
            # should be handled because it was previously deferred
            with patch('sys.argv', ['update-status']):
                patch_update_status = patch('sys.argv', ['update-status'])
                patch_update_status.start()

                ep.entrypoint()
                # re-emit should pick the deferred config-changed
                self.assertEqual(CharmConfigDeferrer.count_called, 2)
                self.assertEqual(CharmConfigDeferrer.defer, False)

    @patch('juju.entrypoint.setup_hooks')
    def test_all_base_events_handled(self, _setup_hooks):
        # note: class variables are modified because Charm instances
        # are not preserved across simulated hook executions
        class Charm(juju.charm.CharmBase):
            count_called = 0

            events_to_observe = []
            events_types_observed = set()

            on = juju.charm.CharmEventsBase()

            def __init__(self, framework, key):
                super().__init__(framework, key)
                for event_name in self.events_to_observe:
                    self.framework.observe(getattr(self.on, event_name), self)

            def _handler_core(self, event):
                logger.debug(f'In {inspect.stack()[0].function},'
                             f' event {event}')
                type(self).count_called += 1
                type(self).events_types_observed.add(type(event))

        # infer supported "base" events from the base charm class
        base_events = {event_name: instance for event_name, instance
                       in juju.charm.CharmEventsBase.__dict__.items()
                       if type(instance) == juju.framework.Event}

        event_names = base_events.keys()
        event_types = {e.event_type for e in base_events.values()}

        logger.debug(f'Expected event types {event_types}')

        # make sure all of the base events are observed
        Charm.events_to_observe = event_names

        # set up handlers for all base events reusing one implementation
        for event_name in event_names:
            setattr(Charm, f'on_{event_name}', Charm._handler_core)

        # simulate hook executions for every event
        for event_name in event_names:
            with patch('sys.argv', [event_name]):
                with patch('juju.entrypoint.Charm', Charm):
                    ep.entrypoint()

        logger.debug(f'Events types observed {Charm.events_types_observed}')

        self.assertEqual(len(event_names), Charm.count_called)
        self.assertEqual(Charm.events_types_observed, event_types)

    def test_event_not_implemented(self):
        """Make sure Juju events are not silently skipped.
        """
        class Charm(juju.charm.CharmBase):
            on = juju.charm.CharmEventsBase()

        with patch('juju.entrypoint.Charm', Charm):
            with patch('sys.argv', ['not-implemented-event']):
                self.assertRaises(NotImplementedError, ep.entrypoint)

    @patch('juju.entrypoint.load_metadata')
    @patch('os.path.exists')
    @patch('os.unlink')
    @patch('os.symlink')
    def test_setup_hooks(self, _os_symlink, _os_unlink,
                         _os_path_exists, _load_metadata):
        _load_metadata.return_value = yaml.load(
            '''
            provides:
              db:
                interface: db
            requires:
              mon:
                interface: monitoring
            peers:
              ha:
                interface: cluster
            '''
        )

        class DBRelationJoined(juju.framework.EventBase):
            pass

        class DBRelationChanged(juju.framework.EventBase):
            pass

        class DBRelationDeparted(juju.framework.EventBase):
            pass

        class DBRelationBroken(juju.framework.EventBase):
            pass

        class MonRelationJoined(juju.framework.EventBase):
            pass

        class MonRelationChanged(juju.framework.EventBase):
            pass

        class MonRelationDeparted(juju.framework.EventBase):
            pass

        class MonRelationBroken(juju.framework.EventBase):
            pass

        class HARelationJoined(juju.framework.EventBase):
            pass

        class HARelationChanged(juju.framework.EventBase):
            pass

        class HARelationDeparted(juju.framework.EventBase):
            pass

        class HARelationBroken(juju.framework.EventBase):
            pass

        class CharmEvents(juju.charm.CharmEventsBase):
            db_relation_joined = Event(DBRelationJoined)
            db_relation_changed = Event(DBRelationChanged)
            db_relation_departed = Event(DBRelationDeparted)
            db_relation_broken = Event(DBRelationBroken)
            mon_relation_joined = Event(MonRelationJoined)
            mon_relation_changed = Event(MonRelationChanged)
            mon_relation_departed = Event(MonRelationDeparted)
            mon_relation_broken = Event(MonRelationBroken)
            ha_relation_joined = Event(HARelationJoined)
            ha_relation_changed = Event(HARelationChanged)
            ha_relation_departed = Event(HARelationDeparted)
            ha_relation_broken = Event(HARelationBroken)

        class Charm(juju.charm.CharmBase):
            on = CharmEvents()

        event_hooks = [f'hooks/{e.replace("_", "-")}'
                       for e in get_charm_event_names(Charm)
                       if e != 'install']

        def assess_setup_hooks(event_name, assume_path_exists):
            with patch('juju.entrypoint.Charm', Charm):
                with patch('sys.argv', [event_name]):
                    ep.setup_hooks()
                    _os_symlink.assert_has_calls(
                        [call('install', event_hook)
                         for event_hook in event_hooks],
                        any_order=True)

                    if _os_path_exists.return_value:
                        _os_unlink.assert_has_calls(
                            [call(event_hook)
                             for event_hook in event_hooks])

                    # avoid attempting to create
                    # a symlink pointing to itself
                    tried_recursion = None
                    try:
                        _os_symlink.assert_has_calls([
                            call('install', 'hooks/install')])
                        tried_recursion = True
                    except AssertionError:
                        tried_recursion = False

                    self.assertFalse(tried_recursion)

        for event_name in ['install', 'upgrade-charm']:
            _os_symlink.reset_mock()
            _os_path_exists.reset_mock()
            _os_path_exists.return_value = False
            _os_unlink.reset_mock()

            assess_setup_hooks(
                event_name,
                assume_path_exists=_os_path_exists.return_value)

        for event_name in ['install', 'upgrade-charm']:
            _os_symlink.reset_mock()
            _os_path_exists.reset_mock()
            _os_unlink.reset_mock()
            _os_path_exists.return_value = True
            assess_setup_hooks(
                event_name,
                assume_path_exists=_os_path_exists.return_value
            )


if __name__ == "__main__":
    unittest.main()
