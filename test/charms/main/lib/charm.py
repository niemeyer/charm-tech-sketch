#!/usr/bin/env python3

from juju.framework import (
    EventBase,
    Event,
)

from juju.charm import (
    CharmBase,
    CharmEventsBase,
)

import logging

logger = logging.getLogger()


class DBRelationJoinedEvent(EventBase):
    pass


class DBRelationChangedEvent(EventBase):
    pass


class DBRelationDepartedEvent(EventBase):
    pass


class DBRelationBrokenEvent(EventBase):
    pass


class MonRelationJoinedEvent(EventBase):
    pass


class MonRelationChangedEvent(EventBase):
    pass


class MonRelationDepartedEvent(EventBase):
    pass


class MonRelationBrokenEvent(EventBase):
    pass


class HARelationJoinedEvent(EventBase):
    pass


class HARelationChangedEvent(EventBase):
    pass


class HARelationDepartedEvent(EventBase):
    pass


class HARelationBrokenEvent(EventBase):
    pass


class CharmEvents(CharmEventsBase):
    db_relation_joined = Event(DBRelationJoinedEvent)
    db_relation_changed = Event(DBRelationChangedEvent)
    db_relation_departed = Event(DBRelationDepartedEvent)
    db_relation_broken = Event(DBRelationBrokenEvent)
    mon_relation_joined = Event(MonRelationJoinedEvent)
    mon_relation_changed = Event(MonRelationChangedEvent)
    mon_relation_departed = Event(MonRelationDepartedEvent)
    mon_relation_broken = Event(MonRelationBrokenEvent)
    ha_relation_joined = Event(HARelationJoinedEvent)
    ha_relation_changed = Event(HARelationChangedEvent)
    ha_relation_departed = Event(HARelationDepartedEvent)
    ha_relation_broken = Event(HARelationBrokenEvent)


class Charm(CharmBase):

    on = CharmEvents()

    events_types_observed = set()

    def __init__(self, framework, key):
        super().__init__(framework, key)

        # __init__ does not use reset_type because the goal is to
        # avoid those values being reset on every object instantiation.

        base_events = {event_name: instance for event_name, instance
                       in CharmEventsBase.__dict__.items()
                       if type(instance) == Event}

        event_names = base_events.keys()

        # Set up handlers default handlers for base events.
        for event_name in event_names:
            handler_name = f'on_{event_name}'
            try:
                getattr(self, handler_name)
            except AttributeError:
                setattr(self, handler_name, self._handler_core)
            self.framework.observe(getattr(self.on, event_name), self)

    @classmethod
    def reset_type(cls):
        to_del = [a for a in cls.__dict__.keys()
                  if any(substr in a for substr in [
                      'count_called',
                      'count_deferred',
                      'defer',
                  ])]
        for a in to_del:
            delattr(cls, a)

    def _handler_core(self, event):
        event_type_name = type(event).__name__
        logger.debug(f'Handling event {event_type_name}')

        count_called = None
        try:
            count_called = getattr(type(self),
                                   f'{event_type_name}_count_called')
        except AttributeError:
            pass
        finally:
            if count_called is None:
                count_called = 0

        count_called += 1
        setattr(type(self), f'{event_type_name}_count_called', count_called)

        defer = None
        try:
            defer = getattr(type(self), f'{event_type_name}_defer')
        except AttributeError:
            pass
        finally:
            if defer is None:
                defer = False

        setattr(type(self), f'{event_type_name}_defer', defer)

        count_deferred = None
        try:
            count_deferred = getattr(
                type(self), f'{event_type_name}_count_deferred')
        except AttributeError:
            pass
        finally:
            if count_deferred is None:
                count_deferred = 0

        if defer:
            event.defer()
            count_deferred += 1

        setattr(
            type(self), f'{event_type_name}_count_deferred', count_deferred)

        type(self).events_types_observed.add(type(event))

    def on_config_changed(self, event):
        # Class variables are modified because Charm instances
        # are not preserved across simulated hook executions.
        self._handler_core(event)
        if self.ConfigChangedEvent_defer:
            type(self).ConfigChangedEvent_defer = False
