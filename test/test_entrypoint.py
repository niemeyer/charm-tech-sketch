#!/usr/bin/python3

import unittest

import juju.entrypoint as ep

import charm

from unittest.mock import patch


class TestEntrypoint(unittest.TestCase):

    def setUp(self):
        self.event_name = 'config-changed'
        argv_patch = patch('sys.argv', [self.event_name])
        argv_patch.start()
        self.addCleanup(argv_patch.stop)

    def tearDown(self):
        pass

    @patch('juju.entrypoint.emit_charm_event')
    @patch('juju.entrypoint.get_juju_event_name')
    @patch('juju.entrypoint.setup_memory_state')
    @patch('juju.entrypoint.Framework')
    def test_entrypoint(self, _Framework, _setup_memory_state,
                        _get_juju_event_name, _emit_charm_event):
        _get_juju_event_name.return_value = self.event_name

        charm_instance = _setup_memory_state.return_value
        framework_instance = _Framework.return_value

        ep.entrypoint()

        _setup_memory_state.assert_called_once_with(framework_instance)
        framework_instance.reemit.assert_called_once()
        _get_juju_event_name.assert_called_once_with()
        _emit_charm_event.assert_called_once_with(charm_instance,
                                                  self.event_name)

        framework_instance.commit.assert_called_once()
        framework_instance.close.assert_called_once()

    @patch('juju.entrypoint.Charm')
    @patch('juju.entrypoint.Framework')
    def test_setup_memory_state(self, _Framework, _Charm):
        charm_instance = _Charm.return_value
        framework_instance = _Framework.return_value

        self.assertEqual(ep.setup_memory_state(framework_instance),
                         charm_instance)

    @patch('juju.entrypoint.Charm')
    @patch('juju.entrypoint.Framework')
    def test_emit_charm_event_has_handler(self, _Framework, _Charm):
        framework_instance = _Framework.return_value

        charm_instance = ep.setup_memory_state(framework_instance)

        event = getattr(charm_instance.on, self.event_name.replace('-', '_'))

        ep.emit_charm_event(charm_instance, self.event_name)

        event.emit.assert_called_once()

    @patch('juju.entrypoint.Charm')
    @patch('juju.entrypoint.Framework')
    def test_emit_charm_event_no_handler(self, _Framework, _Charm):
        framework_instance = _Framework.return_value

        charm_instance = charm.Charm(framework_instance)

        self.assertRaises(NotImplementedError, ep.emit_charm_event,
                          charm_instance, self.event_name)

    def test_get_juju_event_name(self):
        self.assertEqual(ep.get_juju_event_name(), self.event_name)

    def test_format_event_name(self):
        self.assertEqual(ep.format_event_name('start'),
                         'start')
        self.assertEqual(ep.format_event_name('config-changed'),
                         'config_changed')
        self.assertEqual(ep.format_event_name('leader-settings-changed'),
                         'leader_settings_changed')


if __name__ == "__main__":
    unittest.main()
